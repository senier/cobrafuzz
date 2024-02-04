from __future__ import annotations

import hashlib
import io
import logging
import multiprocessing as mp
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from cobrafuzz import corpus, tracer

logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
logging.getLogger().setLevel(logging.DEBUG)


class Coverage:
    def __init__(self) -> None:
        self._covered: set[tuple[Optional[str], Optional[int], str, int]] = set()

    def store_and_check_improvement(
        self,
        data: set[tuple[Optional[str], Optional[int], str, int]],
    ) -> bool:
        covered = len(self._covered)
        self._covered |= data
        if len(self._covered) > covered:
            return True
        return False

    @property
    def total(self) -> int:
        return len(self._covered)


@dataclass
class Update:
    data: bytes
    covered: set[tuple[Optional[str], Optional[int], str, int]]


@dataclass
class Status:
    wid: int
    runs: int


@dataclass
class Result(Status):
    data: bytes


@dataclass
class Report(Result):
    covered: set[tuple[Optional[str], Optional[int], str, int]]


@dataclass
class Error(Report):
    pass


def covered(e: Exception) -> set[tuple[Optional[str], Optional[int], str, int]]:
    """Construct coverage information from exception."""

    prev_line: Optional[int] = None
    prev_file: Optional[str] = None
    tb = e.__traceback__
    covered = set()
    while tb:
        covered.add((prev_file, prev_line, tb.tb_frame.f_code.co_filename, tb.tb_lineno))
        prev_line = tb.tb_lineno
        prev_file = tb.tb_frame.f_code.co_filename
        tb = tb.tb_next
    return covered


def worker(  # noqa: PLR0913
    wid: int,
    target: Callable[[bytes], None],
    update_queue: mp.Queue[Update],
    result_queue: mp.Queue[Status],
    close_stdout: bool,
    close_stderr: bool,
    max_input_size: int,
    stat_frequency: int,
    seeds: list[Path],
) -> None:
    class NullFile(io.StringIO):
        """No-op to trash stdout away."""

        def write(self, arg: str) -> int:
            return len(arg)

    logging.captureWarnings(capture=True)
    logging.getLogger().setLevel(logging.ERROR)

    if close_stdout:
        sys.stdout = NullFile()
    if close_stderr:
        sys.stderr = NullFile()

    runs = 0
    last_status = time.time()
    corp = corpus.Corpus(seeds=seeds, max_input_size=max_input_size)
    cov = Coverage()

    tracer.initialize()

    while True:
        tracer.reset()

        while not update_queue.empty():
            update = update_queue.get()
            cov.store_and_check_improvement(update.covered)
            corp.put(bytearray(update.data))

        runs += 1
        data = corp.generate_input()

        try:
            target(data)
        except Exception as e:  # noqa: BLE001
            result_queue.put(Error(wid=wid, runs=runs, data=data, covered=covered(e)))
            runs = 0
            last_status = time.time()
        else:
            new_path = cov.store_and_check_improvement(data=tracer.get_covered())
            if new_path:
                result_queue.put(
                    Report(wid=wid, runs=runs, data=data, covered=tracer.get_covered()),
                )
                runs = 0
                last_status = time.time()
            elif time.time() - last_status > stat_frequency:
                result_queue.put(Status(wid=wid, runs=runs))
                runs = 0
                last_status = time.time()


class Fuzzer:
    def __init__(  # noqa: PLR0913, ref:#2
        self,
        crash_dir: Path,
        target: Callable[[bytes], None],
        artifact_name: Optional[str] = None,
        close_stderr: bool = False,
        close_stdout: bool = False,
        stat_frequency: int = 5,
        max_crashes: Optional[int] = None,
        max_input_size: int = 4096,
        max_runs: Optional[int] = None,
        max_time: Optional[int] = None,
        num_workers: Optional[int] = 1,
        regression: bool = False,
        seeds: Optional[list[Path]] = None,
    ):
        """
        Fuzz-test target and store crash artifacts into crash_dir.

        Arguments:
        ---------
        crash_dir:      Directory to store crash artifacts in. Will be created if missing.
        target:         Python function to fuzz-test. Must accept bytes.
                        Exceptions are considered crashes.
        artifact_name:  Store all artifacts under this name. Existing artifacts will get
                        overwritten (useful with max_crashes=1).
        close_stderr:   Close standard error when starting fuzzing process.
        close_stdout:   Close standard output when starting fuzzing process.
        stat_frequency: Frequency in which to produce a statistics if no other events are logged.
        max_crashes:    Number of crashes after which to exit the fuzzer.
        max_input_size: Maximum length of input to create.
        max_runs:       Number of target executions after which to exit the fuzzer.
        max_time:       Number of seconds after which to exit the fuzzer.
        num_workers:    Number of parallel workers.
                        Use None to spawn one fewer than CPUs available.
        regression:     Execute target on all samples found in crash_dir, print errors and exit.
        seeds:          List of files and directories to seed the fuzzer with.
        """

        self._current_crashes = 0
        self._current_runs = 0
        self._last_runs = 0
        self._last_stats_time = time.time()
        self._mp_ctx: mp.context.ForkContext = mp.get_context("fork")
        self._result_queue: mp.Queue[Result] = self._mp_ctx.Queue()
        self._workers: list[tuple[mp.context.ForkProcess, mp.Queue[Update]]] = []

        self._crash_dir = crash_dir
        self._target = target

        self._artifact_name = artifact_name
        self._close_stderr = close_stderr
        self._close_stdout = close_stdout
        self._stat_frequency = stat_frequency
        self._max_crashes = max_crashes
        self._max_input_size = max_input_size
        self._max_runs = max_runs
        self._max_time = max_time
        self._num_workers: int = num_workers or self._mp_ctx.cpu_count() - 1
        self._seeds = seeds or []

        if regression:
            for error_file in crash_dir.glob("*"):
                if not error_file.is_file():
                    continue
                with error_file.open("br") as f:
                    try:
                        target(f.read())
                    except Exception:
                        logging.exception(
                            "\n========================================================================\n"
                            "Testing %s:",
                            error_file,
                        )
                    else:
                        logging.error("No error when testing %s", error_file)
            sys.exit(0)

    def _log_stats(self, log_type: str, total_coverage: int, corpus_size: int) -> None:
        end_time = time.time()
        execs_per_second = int(
            (self._current_runs - self._last_runs) / (end_time - self._last_stats_time),
        )

        self._last_stats_time = end_time
        self._last_runs = self._current_runs

        logging.info(
            "#%d %s     cov: %d corp: %d exec/s: %d crashes: %d",
            self._current_runs,
            log_type,
            total_coverage,
            corpus_size,
            execs_per_second,
            self._current_crashes,
        )

    def _write_sample(self, buf: bytes, prefix: str = "crash-") -> None:
        m = hashlib.sha256()
        m.update(buf)

        if not self._crash_dir.exists():
            self._crash_dir.mkdir(parents=True)
            logging.info("Crash dir created (%s)", self._crash_dir)

        crash_path = self._crash_dir / (self._artifact_name or (prefix + m.hexdigest()))

        with crash_path.open("wb") as f:
            f.write(buf)
        logging.info("sample was written to %s", crash_path)
        if len(buf) < 200:
            logging.info("sample = %s", buf.hex())

    def _initialize_process(self, wid: int) -> tuple[mp.context.ForkProcess, mp.Queue[Update]]:
        queue: mp.Queue[Update] = self._mp_ctx.Queue()
        result = self._mp_ctx.Process(
            target=worker,
            args=(
                wid,
                self._target,
                queue,
                self._result_queue,
                self._close_stdout,
                self._close_stderr,
                self._max_input_size,
                self._stat_frequency,
                self._seeds,
            ),
        )
        result.start()
        return result, queue

    def start(self) -> None:  # noqa: PLR0912
        start_time = time.time()
        coverage = Coverage()
        corp = corpus.Corpus(self._seeds, self._max_input_size)

        self._workers = [self._initialize_process(wid) for wid in range(self._num_workers)]

        logging.info(
            "#0 READ units: %d workers: %d seeds: %d",
            corp.length,
            self._num_workers,
            corp.length,
        )

        while True:
            if self._max_runs is not None and self._current_runs >= self._max_runs:
                for p, _ in self._workers:
                    p.terminate()
                logging.info(
                    "Performed %d runs (%d/s), stopping.",
                    self._max_runs,
                    self._max_runs / (time.time() - start_time),
                )
                break

            if self._max_time is not None and (time.time() - start_time) > self._max_time:
                for p, _ in self._workers:
                    p.terminate()
                logging.info(
                    "Timeout after %d seconds, stopping.",
                    self._max_time,
                )
                break

            if self._max_crashes is not None and self._current_crashes >= self._max_crashes:
                for p, _ in self._workers:
                    p.terminate()
                logging.info("Found %d crashes, stopping.", self._current_crashes)
                break

            while not self._result_queue.empty():
                result = self._result_queue.get()
                self._current_runs += result.runs

                if isinstance(result, Error):
                    improvement = coverage.store_and_check_improvement(result.covered)
                    if improvement:
                        self._current_crashes += 1
                        self._write_sample(result.data)

                elif isinstance(result, Report):
                    improvement = coverage.store_and_check_improvement(result.covered)
                    if improvement:
                        self._log_stats("NEW", coverage.total, corp.length)
                        corp.put(bytearray(result.data))

                        for wid, (_, queue) in enumerate(self._workers):
                            if wid != result.wid:
                                queue.put(Update(data=result.data, covered=result.covered))

                elif isinstance(result, Status):
                    pass

                else:
                    assert False, f"Unhandled result type: {type(result)}"

            if (time.time() - self._last_stats_time) > self._stat_frequency:
                self._log_stats("PULSE", coverage.total, corp.length)

        for _, queue in self._workers:
            queue.cancel_join_thread()
        self._result_queue.cancel_join_thread()

        for p, _ in self._workers:
            p.join()
        sys.exit(0)

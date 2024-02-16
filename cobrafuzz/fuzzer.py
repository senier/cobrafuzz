from __future__ import annotations

import hashlib
import io
import logging
import multiprocessing as mp
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Union, cast

import dill as pickle  # type: ignore[import-untyped]

from cobrafuzz import state as st, tracer

logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
logging.getLogger().setLevel(logging.DEBUG)

MPContext = Union[mp.context.ForkContext, mp.context.ForkServerContext, mp.context.SpawnContext]
MPProcess = Union[mp.context.ForkProcess, mp.context.ForkServerProcess, mp.context.SpawnProcess]


@dataclass
class Update:
    data: bytes
    covered: set[tuple[Optional[str], Optional[int], str, int]]


@dataclass
class StatusBase:
    wid: int


@dataclass
class Bug(StatusBase):
    message: str


@dataclass
class Status(StatusBase):
    runs: int


@dataclass
class Result(Status):
    data: bytes


@dataclass
class Report(Result):
    covered: set[tuple[Optional[str], Optional[int], str, int]]


@dataclass
class Error(Report):
    message: str


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
    target_bytes: bytes,
    update_queue: mp.Queue[Update],
    result_queue: mp.Queue[StatusBase],
    close_stdout: bool,
    close_stderr: bool,
    stat_frequency: int,
    state: st.State,
) -> None:
    try:
        _worker_run(
            wid=wid,
            target_bytes=target_bytes,
            update_queue=update_queue,
            result_queue=result_queue,
            close_stdout=close_stdout,
            close_stderr=close_stderr,
            stat_frequency=stat_frequency,
            state=state,
        )
    except Exception:  # noqa: BLE001
        result_queue.put(Bug(wid=wid, message=traceback.format_exc()))


def _worker_run(  # noqa: PLR0913
    wid: int,
    target_bytes: bytes,
    update_queue: mp.Queue[Update],
    result_queue: mp.Queue[StatusBase],
    close_stdout: bool,
    close_stderr: bool,
    stat_frequency: int,
    state: st.State,
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
    target = cast(Callable[[bytes], None], pickle.loads(target_bytes))  # noqa: S301

    tracer.initialize()

    while True:
        tracer.reset()

        while not update_queue.empty():
            update = update_queue.get()
            state.store_coverage(update.covered)
            state.put_input(bytearray(update.data))

        runs += 1
        data = state.get_input()

        try:
            target(bytes(data))
        except Exception as e:  # noqa: BLE001
            result_queue.put(
                Error(
                    wid=wid,
                    runs=runs,
                    data=data,
                    covered=covered(e),
                    message=f"{e.__class__.__name__}: {e}",
                ),
            )
            runs = 0
            last_status = time.time()
        else:
            new_path = state.store_coverage(data=tracer.get_covered())
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
    def __init__(  # noqa: PLR0913
        self,
        crash_dir: Path,
        target: Callable[[bytes], None],
        close_stderr: Optional[bool] = None,
        close_stdout: Optional[bool] = None,
        stat_frequency: int = 5,
        max_crashes: Optional[int] = None,
        max_input_size: int = 4096,
        max_runs: Optional[int] = None,
        max_time: Optional[int] = None,
        num_workers: Optional[int] = 1,
        regression: bool = False,
        seeds: Optional[list[Path]] = None,
        start_method: Optional[str] = None,
        state_file: Optional[Path] = None,
        load_crashes: bool = True,
    ):
        """
        Fuzz-test target and store crash artifacts into crash_dir.

        Arguments:
        ---------
        crash_dir:      Directory to store crash artifacts in. Will be created if missing.
        target:         Python function to fuzz-test. Must accept bytes.
                        Exceptions are considered crashes.
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
        start_method:   Multiprocessing start method to use (spawn, forkserver or fork).
                        Defaults to "spawn". Do not use "fork" as it is unreliable and may lead
                        to deadlocks.
        state_file:     File to load state from. Will be updated periodically. If no file is
                        specified, the state will be held in memory and discarded on exit.
        load_crashes:   Load crashes from crash directory on startup.
        """

        self._current_crashes = 0
        self._current_runs = 0
        self._last_runs = 0
        self._last_stats_time = time.time()

        self._mp_ctx: MPContext = (
            mp.get_context("fork")
            if start_method == "fork"
            else mp.get_context("forkserver")
            if start_method == "forkserver"
            else mp.get_context("spawn")
        )

        self._result_queue: mp.Queue[Result] = self._mp_ctx.Queue()
        self._workers: list[tuple[MPProcess, mp.Queue[Update]]] = []

        self._crash_dir = crash_dir
        self._target_bytes = pickle.dumps(target)

        self._close_stderr = close_stderr or False
        self._close_stdout = close_stdout or False
        self._stat_frequency = stat_frequency
        self._max_crashes = max_crashes
        self._max_runs = max_runs
        self._max_time = max_time
        self._num_workers: int = num_workers or self._mp_ctx.cpu_count() - 1
        self._state = st.State(seeds=seeds, max_input_size=max_input_size, file=state_file)

        if load_crashes:
            self._load_crashes(regression=regression)

    def _load_crashes(self, regression: bool) -> None:
        """
        Load crash coverage from crash directory.

        Arguments:
        ---------
        regression: Output unique errors and then exit.
        """

        target = cast(Callable[[bytes], None], pickle.loads(self._target_bytes))  # noqa: S301
        local_state = st.State()

        for error_file in self._crash_dir.glob("*"):
            if not error_file.is_file():
                continue
            with error_file.open("br") as f:
                try:
                    target(f.read())
                except Exception as e:  # noqa: BLE001
                    if regression:
                        changed = local_state.store_coverage(covered(e))
                        if changed:
                            logging.exception(
                                "\n========================================================================\n"
                                "Testing %s:",
                                error_file,
                            )
                    else:
                        self._state.store_coverage(covered(e))
                else:
                    if regression:
                        logging.error("No error when testing %s", error_file)

        if regression:
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

        crash_path = self._crash_dir / (prefix + m.hexdigest())

        with crash_path.open("wb") as f:
            f.write(buf)
        logging.info("sample was written to %s", crash_path)
        if len(buf) < 200:
            logging.info("sample = %s", buf.hex())

    def _initialize_process(self, wid: int) -> tuple[MPProcess, mp.Queue[Update]]:
        queue: mp.Queue[Update] = self._mp_ctx.Queue()
        result = self._mp_ctx.Process(
            target=worker,
            args=(
                wid,
                self._target_bytes,
                queue,
                self._result_queue,
                self._close_stdout,
                self._close_stderr,
                self._stat_frequency,
                self._state,
            ),
        )
        result.start()
        return result, queue

    def start(self) -> None:  # noqa: PLR0912
        start_time = time.time()

        self._workers = [self._initialize_process(wid=wid) for wid in range(self._num_workers)]

        logging.info(
            "#0 READ units: %d workers: %d seeds: %d",
            self._state.size,
            self._num_workers,
            self._state.num_seeds,
        )

        while True:
            if self._max_runs is not None and self._current_runs >= self._max_runs:
                logging.info(
                    "Performed %d runs (%d/s), stopping.",
                    self._max_runs,
                    self._max_runs / (time.time() - start_time),
                )
                break

            if self._max_time is not None and (time.time() - start_time) > self._max_time:
                logging.info(
                    "Timeout after %d seconds, stopping.",
                    self._max_time,
                )
                break

            if self._max_crashes is not None and self._current_crashes >= self._max_crashes:
                logging.info("Found %d crashes, stopping.", self._current_crashes)
                break

            while not self._result_queue.empty():
                result = self._result_queue.get()

                if isinstance(result, Bug):
                    sys.exit(
                        "===================================================================\n"
                        "                          INTERNAL ERROR.                          \n"
                        "===================================================================\n"
                        " Please open a ticket:                                             \n"
                        "   https://github.com/senier/cobrafuzz/issues/new/choose           \n"
                        "===================================================================\n"
                        f"{result.message}                                                   \n"
                        "===================================================================\n",
                    )

                self._current_runs += result.runs

                if isinstance(result, Error):
                    improvement = self._state.store_coverage(result.covered)
                    if improvement:
                        logging.info(result.message)
                        self._current_crashes += 1
                        self._write_sample(result.data)

                elif isinstance(result, Report):
                    improvement = self._state.store_coverage(result.covered)
                    if improvement:
                        self._log_stats("NEW", self._state.total_coverage, self._state.size)
                        self._state.put_input(bytearray(result.data))
                        self._state.save()

                        for wid, (_, queue) in enumerate(self._workers):
                            if wid != result.wid:
                                queue.put(Update(data=result.data, covered=result.covered))

                elif isinstance(result, Status):
                    pass

                else:
                    assert False, f"Unhandled result type: {type(result)}"

            if (time.time() - self._last_stats_time) > self._stat_frequency:
                self._log_stats("PULSE", self._state.total_coverage, self._state.size)

        self._state.save()

        for _, queue in self._workers:
            queue.cancel_join_thread()
        self._result_queue.cancel_join_thread()

        for p, _ in self._workers:
            p.terminate()

        for p, _ in self._workers:
            p.join()
        sys.exit(0 if self._current_crashes == 0 else 1)

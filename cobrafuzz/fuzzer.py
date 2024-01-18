from __future__ import annotations

import hashlib
import io
import logging
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path
from typing import Callable, Optional

import psutil

# TODO(senier): #1
mp.set_start_method("fork")

from cobrafuzz import corpus, tracer  # noqa: E402, ref:#1

logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
logging.getLogger().setLevel(logging.DEBUG)

SAMPLING_WINDOW = 5  # IN SECONDS


def worker(
    target: Callable[[bytes], None],
    child_conn: mp.connection.Connection,
    close_fd_mask: int,
) -> None:
    # Silence the fuzzee's noise
    class DummyFile(io.StringIO):
        """No-op to trash stdout away."""

        def write(self, arg: str) -> int:
            return len(arg)

    logging.captureWarnings(capture=True)
    logging.getLogger().setLevel(logging.ERROR)
    if close_fd_mask & 1:
        sys.stdout = DummyFile()
    if close_fd_mask & 2:
        sys.stderr = DummyFile()

    sys.settrace(tracer.trace)
    while True:
        buf = child_conn.recv_bytes()
        try:
            target(buf)
        except Exception as e:
            logging.exception(buf)
            child_conn.send(e)
            break
        else:
            child_conn.send_bytes(b"%d" % tracer.get_coverage())


class Fuzzer:
    def __init__(  # noqa: PLR0913, ref:#2
        self,
        target: Callable[[bytes], None],
        dirs: Optional[list[Path]] = None,
        exact_artifact_path: Optional[Path] = None,
        rss_limit_mb: int = 2048,
        timeout: int = 120,
        regression: bool = False,
        max_input_size: int = 4096,
        close_fd_mask: int = 0,
        runs: int = -1,
        dict_path: Optional[Path] = None,
    ):
        self._target = target
        self._dirs = [] if dirs is None else dirs
        self._exact_artifact_path = exact_artifact_path
        self._rss_limit_mb = rss_limit_mb
        self._timeout = timeout
        self._regression = regression
        self._close_fd_mask = close_fd_mask
        self._corpus = corpus.Corpus(self._dirs, max_input_size, dict_path)
        self._total_executions = 0
        self._executions_in_sample = 0
        self._last_sample_time = time.time()
        self._total_coverage = 0
        self._p: Optional[mp.Process] = None
        self.runs = runs

    def log_stats(self, log_type: str) -> int:
        assert self._p is not None
        rss: int = (
            (
                psutil.Process(self._p.pid).memory_info().rss
                + psutil.Process(os.getpid()).memory_info().rss
            )
            / 1024
            / 1024
        )

        end_time = time.time()
        execs_per_second = int(self._executions_in_sample / (end_time - self._last_sample_time))
        self._last_sample_time = time.time()
        self._executions_in_sample = 0
        logging.info(
            "#%d %s     cov: %d corp: %d exec/s: %d rss: %d MB",
            self._total_executions,
            log_type,
            self._total_coverage,
            self._corpus.length,
            execs_per_second,
            rss,
        )
        return rss

    def write_sample(self, buf: bytes, prefix: str = "crash-") -> None:
        m = hashlib.sha256()
        m.update(buf)
        if self._exact_artifact_path:
            crash_path = self._exact_artifact_path
        else:
            dir_path = Path("crashes")
            if not dir_path.exists():
                dir_path.mkdir(parents=True)
                logging.info("The crashes directory is created")

            crash_path = dir_path / (prefix + m.hexdigest())
        with crash_path.open("wb") as f:
            f.write(buf)
        logging.info("sample was written to %s", crash_path)
        if len(buf) < 200:
            logging.info("sample = %s", buf.hex())

    def start(self) -> None:
        logging.info("#0 READ units: %d", self._corpus.length)
        exit_code = 0
        parent_conn, child_conn = mp.Pipe()
        self._p = mp.Process(target=worker, args=(self._target, child_conn, self._close_fd_mask))
        self._p.start()

        while True:
            if self.runs != -1 and self._total_executions >= self.runs:
                self._p.terminate()
                logging.info("did %d runs, stopping now.", self.runs)
                break

            buf = self._corpus.generate_input()
            parent_conn.send_bytes(buf)
            if not parent_conn.poll(self._timeout):
                self._p.kill()
                logging.info("=================================================================")
                logging.info("timeout reached. testcase took: %d", self._timeout)
                self.write_sample(buf, prefix="timeout-")
                break

            try:
                total_coverage = int(parent_conn.recv_bytes())
            except ValueError:
                self.write_sample(buf)
                exit_code = 76
                break

            self._total_executions += 1
            self._executions_in_sample += 1
            rss = 0
            if total_coverage > self._total_coverage:
                rss = self.log_stats("NEW")
                self._total_coverage = total_coverage
                self._corpus.put(buf)
            else:
                if (time.time() - self._last_sample_time) > SAMPLING_WINDOW:
                    rss = self.log_stats("PULSE")

            if rss > self._rss_limit_mb:
                logging.info("MEMORY OOM: exceeded %d MB. Killing worker", self._rss_limit_mb)
                self.write_sample(buf)
                self._p.kill()
                break

        self._p.join()
        sys.exit(exit_code)

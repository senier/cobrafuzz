from __future__ import annotations

import logging
import multiprocessing as mp
import re
import sys
import time
from pathlib import Path
from typing import Callable, Optional

import dill  # type: ignore[import-untyped]
import pytest

import tests.utils
from cobrafuzz import fuzzer, state as st


class State(st.State):
    def __init__(self, data: bytes, report_new_path: bool = False) -> None:
        super().__init__()
        self.count = 0
        self.last_success: Optional[bool] = None
        self.input = bytearray(data)
        self.report_new_paths = report_new_path
        self.data: set[tuple[Optional[str], Optional[int], str, int]] = set()

    def get_input(self) -> bytearray:
        return self.input

    def update(self, success: bool = False) -> None:
        self.last_success = success

    def store_coverage(
        self,
        data: set[tuple[Optional[str], Optional[int], str, int]],
    ) -> bool:
        self.data |= data
        return self.report_new_paths


class DoneError(Exception):
    pass


def worker_crash(
    wid: int,
    _target_bytes: bytes,
    _update_queue: mp.Queue[fuzzer.Update],
    result_queue: mp.Queue[fuzzer.StatusBase],
    _close_stdout: bool,
    _close_stderr: bool,
    _stat_frequency: int,
    _state: st.State,
) -> None:
    print("worker on stdout")  # noqa: T201
    print("worker on stderr", file=sys.stderr)  # noqa: T201
    result_queue.put(
        fuzzer.Error(
            wid=wid,
            runs=1000,
            data=b"deadbeef",
            covered={("a", 1, "b", 2)},
            message="worker crashed",
        ),
    )


def test_stats(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data = b"deadbeef"
    covered: set[tuple[Optional[str], Optional[int], str, int]] = {("a", 1, "b", 2)}
    state = State(data=b"deadbeef", report_new_path=True)
    result_queue: mp.Queue[fuzzer.Result] = mp.Queue()
    result_queue.put(fuzzer.Report(wid=0, runs=1, data=data, covered=covered))
    with monkeypatch.context() as p:
        p.setattr(time, "time", tests.utils.mock_time())
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=tmp_path,
            max_runs=1,
        )
        p.setattr(f, "_state", state)
        p.setattr(f, "_initialize_process", lambda wid: (None, None))  # noqa: ARG005
        p.setattr(f, "_terminate_workers", lambda: None)
        p.setattr(f, "_result_queue", result_queue)
        with pytest.raises(SystemExit, match="^0$"):
            f.start()
        f._log_stats("CUSTOM", total_coverage=123, corpus_size=5)  # noqa: SLF001
    assert re.match(
        r".*CUSTOM\s+cov: 123 corp: 5 exec/s: \d+ crashes: 0\n.*",
        caplog.text,
        flags=re.DOTALL,
    )


def test_write_sample(tmp_path: Path) -> None:
    sample = 1000 * b"x"
    f = fuzzer.Fuzzer(  # pragma: no cover
        target=lambda _: None,
        crash_dir=tmp_path,
    )
    f._write_sample(sample)  # noqa: SLF001
    artifact = next(tmp_path.glob("*"))
    assert artifact.is_file()
    with artifact.open("rb") as af:
        assert af.read() == sample


def test_regression(tmp_path: Path) -> None:
    with (tmp_path / "crash1").open("wb") as cf:
        cf.write(b"*foo")
    with (tmp_path / "crash2").open("wb") as cf:
        cf.write(b"*bar")
    with (tmp_path / "crash3").open("wb") as cf:
        cf.write(b"*bar")
    with (tmp_path / "crash4").open("wb") as cf:
        cf.write(b"baz")
    (tmp_path / "subdir").mkdir()

    with pytest.raises(SystemExit, match="^0$"):
        fuzzer.Fuzzer(
            target=lambda data: tests.utils.do_raise(ValueError, cond=data.startswith(b"*")),
            crash_dir=tmp_path,
            regression=True,
        )


def test_load_crashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = State(data=b"deadbeef", report_new_path=False)
    with (tmp_path / "crash").open("wb") as cf:
        cf.write(b"*foo")
    f = fuzzer.Fuzzer(
        target=lambda data: tests.utils.do_raise(ValueError, cond=data.startswith(b"*")),
        crash_dir=tmp_path,
        regression=False,
        load_crashes=False,
    )
    assert not state.data
    with monkeypatch.context() as mp:
        mp.setattr(f, "_state", state)
        f._load_crashes(regression=False)  # noqa: SLF001
    assert state.data


def test_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    assert not state_file.exists()
    with monkeypatch.context() as mp:
        mp.setattr(fuzzer, "worker", worker_crash)
        for i in range(2):
            f = fuzzer.Fuzzer(
                target=lambda _: None,
                crash_dir=tmp_path,
                max_runs=1,
                state_file=state_file,
                close_stderr=True,
                close_stdout=True,
            )
            with pytest.raises(SystemExit, match="^1$" if i == 0 else "^0$"):
                f.start()
        assert state_file.exists()


def test_crash_simple(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    with monkeypatch.context() as mp:
        mp.setattr(fuzzer, "worker", worker_crash)
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=crash_dir,
            max_crashes=1,
        )
        with pytest.raises(SystemExit, match="^1$"):
            f.start()
        assert crash_dir.is_dir()


def test_crash_hard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    with monkeypatch.context() as mp:
        mp.setattr(fuzzer, "worker", worker_crash)
        f = fuzzer.Fuzzer(  # pragma: no cover
            crash_dir=crash_dir,
            target=lambda _: None,
            max_crashes=1,
            num_workers=2,
            stat_frequency=1,
        )
        with pytest.raises(SystemExit, match="^1$"):
            f.start()
        assert crash_dir.is_dir()


def test_crash_hard_non_adaptive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    with monkeypatch.context() as mp:
        mp.setattr(fuzzer, "worker", worker_crash)
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            adaptive=False,
            crash_dir=crash_dir,
            max_crashes=1,
        )
        with pytest.raises(SystemExit, match="^1$"):
            f.start()
        assert crash_dir.is_dir()


def test_crash_with_crash_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    with monkeypatch.context() as mp:
        mp.setattr(fuzzer, "worker", worker_crash)
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=crash_dir,
            max_crashes=1,
        )
        with pytest.raises(SystemExit, match="^1$"):
            f.start()
        assert crash_dir.is_dir()


def test_internal_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with monkeypatch.context() as mp:
        # Letting dill.loads fail in the worker by injecting an invalid result to dill.dumps
        # is our only way to trigger an error. Child processes are freshly spawned and hence we
        # cannot monkeypatch them.
        mp.setattr(dill, "dumps", lambda _: b"0")
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=tmp_path,
            max_runs=1,
            num_workers=1,
            load_crashes=False,
        )
        with pytest.raises(SystemExit, match="INTERNAL ERROR"):
            f.start()


def test_worker_loop_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def worker_run(
        wid: int,
        target: Callable[[bytes], None],  # noqa: ARG001
        state: st.State,
        runs: int,
    ) -> fuzzer.StatusBase:
        assert isinstance(state, State)
        if state.count > 1:
            raise DoneError("Test done")
        state.count += 1

        print(f"Worker {wid}, {runs} runs")  # noqa: T201
        print(f"Worker {wid}, {runs} runs", file=sys.stderr)  # noqa: T201
        return fuzzer.Error(
            wid=wid,
            runs=runs,
            data=bytearray(b"deadbeef"),
            covered=state._covered,  # noqa: SLF001
            message="Test Error",
        )

    update_queue: mp.Queue[fuzzer.Update] = mp.Queue()
    result_queue: mp.Queue[fuzzer.StatusBase] = mp.Queue()

    update_queue.put(fuzzer.Update(b"update", covered=set()))

    with monkeypatch.context() as c:
        c.setattr(fuzzer, "_worker_run", worker_run)
        with pytest.raises(DoneError, match="^Test done$"):
            fuzzer.worker_loop(  # pragma: no cover
                wid=1,
                target_bytes=dill.dumps(lambda _: None),
                update_queue=update_queue,
                result_queue=result_queue,
                close_stdout=True,
                close_stderr=True,
                stat_frequency=1,
                state=State(b"deadbeef"),
            )
        result = result_queue.get(block=False)
        assert isinstance(result, fuzzer.Error)
        assert result.wid == 1
        assert result.runs == 1
        assert result.data == bytearray(b"deadbeef")
        assert "Test Error" in result.message, result.message


def test_worker_loop_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def worker_run(
        wid: int,
        target: Callable[[bytes], None],  # noqa: ARG001
        state: st.State,
        runs: int,
    ) -> fuzzer.StatusBase:
        assert isinstance(state, State)
        if state.count > 1:
            raise DoneError("Test done")
        state.count += 1

        return fuzzer.Status(
            wid=wid,
            runs=runs,
        )

    update_queue: mp.Queue[fuzzer.Update] = mp.Queue()
    result_queue: mp.Queue[fuzzer.StatusBase] = mp.Queue()

    update_queue.put(fuzzer.Update(b"update", covered=set()))

    with monkeypatch.context() as c:
        c.setattr(fuzzer, "_worker_run", worker_run)
        c.setattr(time, "time", tests.utils.mock_time())
        with pytest.raises(DoneError, match="^Test done$"):
            fuzzer.worker_loop(  # pragma: no cover
                wid=1,
                target_bytes=dill.dumps(lambda _: None),
                update_queue=update_queue,
                result_queue=result_queue,
                close_stdout=True,
                close_stderr=True,
                stat_frequency=1,
                state=State(data=b"deadbeef"),
            )
        assert result_queue.empty()


def test_worker_run_error_result() -> None:
    state = State(data=b"deadbeef")
    result = fuzzer._worker_run(  # noqa: SLF001
        wid=1,
        target=lambda _: tests.utils.do_raise(DoneError, message="Test done"),
        state=state,
        runs=1,
    )
    assert isinstance(result, fuzzer.Error)
    assert result.wid == 1
    assert result.runs == 1
    assert result.data == b"deadbeef"
    assert "Test done" in result.message


def test_worker_run_report_result() -> None:
    state = State(data=b"deadbeef", report_new_path=True)
    result = fuzzer._worker_run(  # noqa: SLF001
        wid=1,
        target=lambda _: None,
        state=state,
        runs=1,
    )

    assert isinstance(result, fuzzer.Report)
    assert result.wid == 1
    assert result.runs == 1
    assert result.data == b"deadbeef"
    assert state.last_success


def test_worker_run_status_result() -> None:
    state = State(data=b"deadbeef")
    result = fuzzer._worker_run(  # noqa: SLF001
        wid=1,
        target=lambda _: None,
        state=state,
        runs=1,
    )

    assert isinstance(result, fuzzer.Status)
    assert result.wid == 1
    assert result.runs == 1


def test_timeout(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f = fuzzer.Fuzzer(crash_dir=tmp_path, target=lambda _: None, max_time=10)  # pragma: no cover
    with monkeypatch.context() as p:
        p.setattr(time, "time", tests.utils.mock_time())
        p.setattr(f, "_initialize_process", lambda wid: (None, None))  # noqa: ARG005
        p.setattr(f, "_terminate_workers", lambda: None)
        with pytest.raises(SystemExit, match="^0$"), caplog.at_level(logging.INFO):
            f.start()
    assert caplog.record_tuples == [
        ("root", logging.INFO, "#0 READ units: 1 workers: 1 seeds: 0"),
        ("root", logging.INFO, "Timeout after 10 seconds, stopping."),
    ]


def test_start_no_progress(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = State(data=b"deadbeef", report_new_path=False)
    result_queue: mp.Queue[fuzzer.Result] = mp.Queue()
    result_queue.put(fuzzer.Report(wid=1, runs=1, data=b"deadbeef", covered=set()))
    with monkeypatch.context() as p:
        p.setattr(time, "time", tests.utils.mock_time())
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=tmp_path,
            max_runs=1,
        )
        p.setattr(f, "_state", state)
        p.setattr(f, "_initialize_process", lambda wid: (None, None))  # noqa: ARG005
        p.setattr(f, "_terminate_workers", lambda: None)
        p.setattr(f, "_result_queue", result_queue)
        with pytest.raises(SystemExit, match="^0$"), caplog.at_level(logging.INFO):
            f.start()
    assert caplog.record_tuples == [
        ("root", logging.INFO, "#0 READ units: 1 workers: 1 seeds: 0"),
        ("root", logging.INFO, "Performed 1 runs (0/s), stopping."),
    ]


def test_start_status(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = State(data=b"deadbeef", report_new_path=False)
    result_queue: mp.Queue[fuzzer.StatusBase] = mp.Queue()
    result_queue.put(fuzzer.Status(wid=1, runs=1))
    with monkeypatch.context() as p:
        p.setattr(time, "time", tests.utils.mock_time())
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=tmp_path,
            max_runs=1,
            num_workers=2,
        )
        p.setattr(f, "_state", state)
        p.setattr(f, "_initialize_process", lambda wid: (None, None))  # noqa: ARG005
        p.setattr(f, "_terminate_workers", lambda: None)
        p.setattr(f, "_result_queue", result_queue)
        with pytest.raises(SystemExit, match="^0$"), caplog.at_level(logging.INFO):
            f.start()
    assert caplog.record_tuples == [
        ("root", logging.INFO, "#0 READ units: 1 workers: 2 seeds: 0"),
        ("root", logging.INFO, "Performed 1 runs (0/s), stopping."),
    ]


def test_start_progress_with_update(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data = b"deadbeef"
    covered: set[tuple[Optional[str], Optional[int], str, int]] = {("a", 1, "b", 2)}
    state = State(data=b"deadbeef", report_new_path=True)
    result_queue: mp.Queue[fuzzer.Result] = mp.Queue()
    result_queue.put(fuzzer.Report(wid=1, runs=1, data=data, covered=covered))
    with monkeypatch.context() as p:
        p.setattr(time, "time", tests.utils.mock_time())
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=tmp_path,
            max_runs=1,
            num_workers=2,
        )
        p.setattr(f, "_state", state)
        p.setattr(f, "_initialize_process", lambda wid: (None, mp.Queue()))  # noqa: ARG005
        p.setattr(f, "_terminate_workers", lambda: None)
        p.setattr(f, "_result_queue", result_queue)
        with pytest.raises(SystemExit, match="^0$"), caplog.at_level(logging.INFO):
            f.start()

        queue = f._workers[0][1]  # noqa: SLF001
        assert not queue.empty()
        update = queue.get()
        assert queue.empty()
        assert update.data == data
        assert update.covered == covered

    assert caplog.record_tuples == [
        ("root", logging.INFO, "#0 READ units: 1 workers: 2 seeds: 0"),
        ("root", logging.INFO, "#1 NEW     cov: 0 corp: 1 exec/s: 0 crashes: 0"),
        ("root", logging.INFO, "Performed 1 runs (0/s), stopping."),
    ]


def test_start_pulse(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = State(data=b"deadbeef", report_new_path=False)
    result_queue: mp.Queue[fuzzer.StatusBase] = mp.Queue()
    result_queue.put(fuzzer.Status(wid=1, runs=1))
    with monkeypatch.context() as p:
        p.setattr(time, "time", tests.utils.mock_time())
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=tmp_path,
            max_time=10,
            stat_frequency=9,
        )
        p.setattr(f, "_state", state)
        p.setattr(f, "_initialize_process", lambda wid: (None, None))  # noqa: ARG005
        p.setattr(f, "_terminate_workers", lambda: None)
        p.setattr(f, "_result_queue", result_queue)
        with pytest.raises(SystemExit, match="^0$"), caplog.at_level(logging.INFO):
            f.start()
    assert caplog.record_tuples == [
        ("root", logging.INFO, "#0 READ units: 1 workers: 1 seeds: 0"),
        ("root", logging.INFO, "#1 PULSE     cov: 0 corp: 1 exec/s: 0 crashes: 0"),
        ("root", logging.INFO, "Timeout after 10 seconds, stopping."),
    ]

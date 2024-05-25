from __future__ import annotations

import hashlib
import logging
import multiprocessing
import re
import sys
import time
from pathlib import Path
from typing import Callable, Optional, Tuple, Union, cast

import dill  # type: ignore[import-untyped]
import pytest

from cobrafuzz import fuzzer, simplifier, state as st
from tests import utils


class DummyState(st.State):
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


def test_stats(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data = b"deadbeef"
    covered: set[tuple[Optional[str], Optional[int], str, int]] = {("a", 1, "b", 2)}
    state = DummyState(data=b"deadbeef", report_new_path=True)
    result_queue: utils.DummyQueue[fuzzer.Result] = utils.DummyQueue()
    result_queue.put(fuzzer.Report(wid=0, runs=1, data=data, covered=covered))
    with monkeypatch.context() as p:
        p.setattr(time, "time", utils.mock_time())
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
        r".*CUSTOM\s+cov: 123, corp: 5, exec/s: \d+, crashes: 0\n.*",
        caplog.text,
        flags=re.DOTALL,
    )


@pytest.mark.parametrize(
    ("subdir", "length"),
    [
        ("crashes", 100),
        ("crashes", 1000),
        ("", 50),
        ("", 2000),
    ],
)
def test_write_sample(
    subdir: str,
    length: int,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    crash_dir = tmp_path / subdir
    sample = length * b"x"
    f = fuzzer.Fuzzer(  # pragma: no cover
        target=lambda _: None,
        crash_dir=crash_dir,
    )
    with caplog.at_level(logging.INFO):
        f._write_sample(sample)  # noqa: SLF001
    artifact = next(crash_dir.glob("*"))
    assert artifact.is_file()
    with artifact.open("rb") as af:
        assert af.read() == sample
    assert length >= 200 or f"sample = {sample.hex()}" in caplog.text


def test_regression_valid(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    with (tmp_path / "crash1").open("wb") as cf:
        cf.write(b"*foo")
    with (tmp_path / "crash2").open("wb") as cf:
        cf.write(b"*bar")
    with (tmp_path / "crash3").open("wb") as cf:
        cf.write(b"*bar")
    with (tmp_path / "crash4").open("wb") as cf:
        cf.write(b"baz")
    (tmp_path / "subdir").mkdir()

    with pytest.raises(SystemExit, match="^0$"), caplog.at_level(logging.INFO):
        fuzzer.Fuzzer(
            target=lambda data: utils.do_raise(ValueError, cond=data.startswith(b"*")),
            crash_dir=tmp_path,
            regression=True,
        )
    assert f"Testing {tmp_path / 'crash1'}:" in caplog.text
    assert f"No error when testing {tmp_path / 'crash4'}" in caplog.text


def test_load_crashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = DummyState(data=b"deadbeef", report_new_path=False)
    with (tmp_path / "crash1").open("wb") as cf:
        cf.write(b"*foo")
    with (tmp_path / "crash2").open("wb") as cf:
        cf.write(b"foo")
    f = fuzzer.Fuzzer(
        target=lambda data: utils.do_raise(ValueError, cond=data.startswith(b"*")),
        crash_dir=tmp_path,
        regression=False,
        load_crashes=False,
    )
    assert not state.data
    with monkeypatch.context() as p:
        p.setattr(f, "_state", state)
        f._load_crashes(regression=False)  # noqa: SLF001
    assert state.data


def test_worker_loop_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def worker_run(
        wid: int,
        target: Callable[[bytes], None],  # noqa: ARG001
        state: st.State,
        runs: int,
    ) -> fuzzer.StatusBase:
        assert isinstance(state, DummyState)
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

    update_queue: utils.DummyQueue[fuzzer.Update] = utils.DummyQueue()
    result_queue: utils.DummyQueue[fuzzer.StatusBase] = utils.DummyQueue()

    update_queue.put(fuzzer.Update(b"update", covered=set()))

    with monkeypatch.context() as c:
        c.setattr(fuzzer, "_worker_run", worker_run)
        with pytest.raises(DoneError, match="^Test done$"):
            fuzzer.worker_loop(  # pragma: no cover
                wid=1,
                target_bytes=dill.dumps(lambda _: None),
                update_queue=update_queue,  # type: ignore[arg-type]
                result_queue=result_queue,  # type: ignore[arg-type]
                close_stdout=True,
                close_stderr=True,
                stat_frequency=1,
                state=DummyState(b"deadbeef"),
            )
        result = result_queue.get()
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
        assert isinstance(state, DummyState)
        if state.count > 1:
            raise DoneError("Test done")
        state.count += 1

        return fuzzer.Status(
            wid=wid,
            runs=runs,
        )

    update_queue: utils.DummyQueue[fuzzer.Update] = utils.DummyQueue()
    result_queue: utils.DummyQueue[fuzzer.StatusBase] = utils.DummyQueue()

    update_queue.put(fuzzer.Update(b"update", covered=set()))

    with monkeypatch.context() as p:
        p.setattr(fuzzer, "_worker_run", worker_run)
        p.setattr(time, "time", utils.mock_time())
        with pytest.raises(DoneError, match="^Test done$"):
            fuzzer.worker_loop(  # pragma: no cover
                wid=1,
                target_bytes=dill.dumps(lambda _: None),
                update_queue=update_queue,  # type: ignore[arg-type]
                result_queue=result_queue,  # type: ignore[arg-type]
                close_stdout=False,
                close_stderr=False,
                stat_frequency=1,
                state=DummyState(data=b"deadbeef"),
            )
        assert not result_queue.empty()
        result = result_queue.get()
        assert isinstance(result, fuzzer.Status)
        assert result.wid == 1
        assert result.runs == 2


def test_worker_run_error_result() -> None:
    state = DummyState(data=b"deadbeef")
    result = fuzzer._worker_run(  # noqa: SLF001
        wid=1,
        target=lambda _: utils.do_raise(DoneError, message="Test done"),
        state=state,
        runs=1,
    )
    assert isinstance(result, fuzzer.Error)
    assert result.wid == 1
    assert result.runs == 1
    assert result.data == b"deadbeef"
    assert "Test done" in result.message


def test_worker_run_report_result() -> None:
    state = DummyState(data=b"deadbeef", report_new_path=True)
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
    state = DummyState(data=b"deadbeef")
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
        p.setattr(time, "time", utils.mock_time())
        p.setattr(f, "_initialize_process", lambda wid: (None, None))  # noqa: ARG005
        p.setattr(f, "_terminate_workers", lambda: None)
        with pytest.raises(SystemExit, match="^0$"), caplog.at_level(logging.INFO):
            f.start()
    assert caplog.record_tuples == [
        ("root", logging.INFO, "START units: 1, workers: 1, seeds: 0"),
        ("root", logging.INFO, "Timeout after 10 seconds, stopping."),
    ]


def test_start_no_progress(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = DummyState(data=b"deadbeef", report_new_path=False)
    result_queue: utils.DummyQueue[fuzzer.Result] = utils.DummyQueue()
    result_queue.put(fuzzer.Report(wid=1, runs=1, data=b"deadbeef", covered=set()))
    with monkeypatch.context() as p:
        p.setattr(time, "time", utils.mock_time())
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
    assert caplog.record_tuples[0] == ("root", logging.INFO, "START units: 1, workers: 1, seeds: 0")
    assert caplog.record_tuples[-1] == ("root", logging.INFO, "Performed 1 runs (0/s), stopping.")


def test_start_status(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = DummyState(data=b"deadbeef", report_new_path=False)
    result_queue: utils.DummyQueue[fuzzer.StatusBase] = utils.DummyQueue()
    result_queue.put(fuzzer.Status(wid=1, runs=1))
    with monkeypatch.context() as p:
        p.setattr(time, "time", utils.mock_time())
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
        ("root", logging.INFO, "START units: 1, workers: 2, seeds: 0"),
        ("root", logging.INFO, "Performed 1 runs (0/s), stopping."),
    ]


def test_start_progress_with_update(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data = b"deadbeef"
    covered: set[tuple[Optional[str], Optional[int], str, int]] = {("a", 1, "b", 2)}
    state = DummyState(data=b"deadbeef", report_new_path=True)
    result_queue: utils.DummyQueue[fuzzer.Result] = utils.DummyQueue()
    result_queue.put(fuzzer.Report(wid=1, runs=1, data=data, covered=covered))
    with monkeypatch.context() as p:
        p.setattr(time, "time", utils.mock_time())
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=tmp_path,
            max_runs=1,
            num_workers=2,
        )
        p.setattr(f, "_state", state)
        p.setattr(f, "_initialize_process", lambda wid: (None, utils.DummyQueue()))  # noqa: ARG005
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
        ("root", logging.INFO, "START units: 1, workers: 2, seeds: 0"),
        ("root", logging.INFO, "#000000001   NEW cov: 0, corp: 1, exec/s: 0, crashes: 0"),
        ("root", logging.INFO, "Performed 1 runs (0/s), stopping."),
    ]


def test_start_pulse(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = DummyState(data=b"deadbeef", report_new_path=False)
    result_queue: utils.DummyQueue[fuzzer.StatusBase] = utils.DummyQueue()
    result_queue.put(fuzzer.Status(wid=1, runs=1))
    result_queue.put(
        fuzzer.Error(
            wid=1,
            runs=1,
            data=b"deadbeef",
            covered=set(),
            message="Test error message",
        ),
    )
    with monkeypatch.context() as p:
        p.setattr(time, "time", utils.mock_time())
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
        ("root", logging.INFO, "START units: 1, workers: 1, seeds: 0"),
        ("root", logging.INFO, "#000000002 PULSE cov: 0, corp: 1, exec/s: 0, crashes: 0"),
        ("root", logging.INFO, "Timeout after 10 seconds, stopping."),
    ]


def test_start_error(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = DummyState(data=b"deadbeef", report_new_path=True)
    result_queue: utils.DummyQueue[fuzzer.StatusBase] = utils.DummyQueue()
    data = b"deadbeef"
    m = hashlib.sha256()
    m.update(data)
    digest = m.hexdigest()
    error = fuzzer.Error(
        wid=1,
        runs=1,
        data=data,
        covered=set(),
        message="Test error message",
    )
    result_queue.put(error)
    with monkeypatch.context() as p:
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=tmp_path,
            max_crashes=1,
        )
        p.setattr(f, "_state", state)
        p.setattr(f, "_initialize_process", lambda wid: (None, None))  # noqa: ARG005
        p.setattr(f, "_terminate_workers", lambda: None)
        p.setattr(f, "_result_queue", result_queue)
        with pytest.raises(SystemExit, match="^1$"), caplog.at_level(logging.INFO):
            f.start()
    filename = f"crash-{digest}"
    assert caplog.record_tuples == [
        ("root", logging.INFO, "START units: 1, workers: 1, seeds: 0"),
        ("root", logging.INFO, "Test error message"),
        ("root", logging.INFO, f"sample was written to {tmp_path / filename}"),
        ("root", logging.INFO, "sample = 6465616462656566"),
        ("root", logging.INFO, "Found 1 crashes, stopping."),
    ]


def test_start_simplify(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    args: Optional[dict[str, Union[Path, Callable[[bytes], None]]]] = None
    simplify_called: bool = False
    state = DummyState(data=b"deadbeef", report_new_path=True)
    result_queue: utils.DummyQueue[fuzzer.StatusBase] = utils.DummyQueue()
    crash_path = tmp_path / "crash"
    data = b"deadbeef"
    m = hashlib.sha256()
    m.update(data)
    digest = m.hexdigest()
    error = fuzzer.Error(
        wid=1,
        runs=1,
        data=data,
        covered=set(),
        message="Test error message",
    )

    class Simp:
        def __init__(self, **a: Union[Path, Callable[[bytes], None]]) -> None:
            nonlocal args
            args = a

        def simplify(self) -> None:
            nonlocal simplify_called
            simplify_called = True

    result_queue.put(error)
    with monkeypatch.context() as p:
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=crash_path,
            max_crashes=1,
            simplify=tmp_path / "simp",
        )
        p.setattr(f, "_state", state)
        p.setattr(f, "_initialize_process", lambda wid: (None, None))  # noqa: ARG005
        p.setattr(f, "_terminate_workers", lambda: None)
        p.setattr(f, "_result_queue", result_queue)
        p.setattr(simplifier, "Simp", Simp)
        with pytest.raises(SystemExit, match="^1$"), caplog.at_level(logging.INFO):
            f.start()

    filename = f"crash-{digest}"
    assert caplog.record_tuples == [
        ("root", logging.INFO, "START units: 1, workers: 1, seeds: 0"),
        ("root", logging.INFO, "Test error message"),
        ("root", logging.INFO, f"Crash dir created ({crash_path})"),
        ("root", logging.INFO, f"sample was written to {crash_path / filename}"),
        ("root", logging.INFO, "sample = 6465616462656566"),
        ("root", logging.INFO, "Found 1 crashes, stopping."),
    ]

    assert simplify_called
    assert args is not None
    assert args["crash_dir"] == crash_path
    assert args["output_dir"] == tmp_path / "simp"
    assert args["target"] is not None


def test_start_bug(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = DummyState(data=b"deadbeef", report_new_path=False)
    result_queue: utils.DummyQueue[fuzzer.StatusBase] = utils.DummyQueue()
    result_queue.put(fuzzer.Bug(wid=1, message="Test bug"))
    with monkeypatch.context() as p:
        f = fuzzer.Fuzzer(  # pragma: no cover
            target=lambda _: None,
            crash_dir=tmp_path,
            max_crashes=1,
        )
        p.setattr(f, "_state", state)
        p.setattr(f, "_initialize_process", lambda wid: (None, None))  # noqa: ARG005
        p.setattr(f, "_terminate_workers", lambda: None)
        p.setattr(f, "_result_queue", result_queue)
        with pytest.raises(SystemExit, match=r"INTERNAL ERROR"):
            f.start()


def test_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    update_queue: utils.DummyQueue[fuzzer.Update] = utils.DummyQueue()
    result_queue: utils.DummyQueue[fuzzer.StatusBase] = utils.DummyQueue()

    with monkeypatch.context() as p:
        p.setattr(
            "cobrafuzz.fuzzer.worker_loop",
            lambda **_: utils.do_raise(DoneError, message="Test done"),
        )
        fuzzer.worker(  # pragma: no cover
            wid=0,
            target_bytes=dill.dumps(lambda _: None),
            update_queue=update_queue,  # type: ignore[arg-type]
            result_queue=result_queue,  # type: ignore[arg-type]
            close_stdout=False,
            close_stderr=False,
            stat_frequency=1,
            state=DummyState(data=b"deadbeef"),
        )
        assert not result_queue.empty()
        result = result_queue.get()
        assert isinstance(result, fuzzer.Bug)
        assert result.wid == 0
        assert "Test done" in result.message


ArgsType = Tuple[
    int,
    bytes,
    utils.DummyQueue[fuzzer.Update],
    utils.DummyQueue[fuzzer.Result],
    bool,
    bool,
    int,
    DummyState,
]


def test_initialize_process(monkeypatch: pytest.MonkeyPatch) -> None:
    result_queue: utils.DummyQueue[fuzzer.Result] = utils.DummyQueue()

    def target(_: bytes) -> None:
        pass  # pragma: no cover

    with monkeypatch.context() as p:
        p.setattr(multiprocessing, "get_context", lambda _: utils.DummyContext(wid=0))
        f = fuzzer.Fuzzer(crash_dir=Path("/"), target=target, stat_frequency=10)
        s = DummyState(data=b"deadbeef")
        p.setattr(f, "_state", s)
        p.setattr(f, "_result_queue", result_queue)
        result, _ = cast(
            Tuple[utils.DummyProcess[ArgsType], utils.DummyQueue[fuzzer.Update]],
            f._initialize_process(wid=0),  # noqa: SLF001
        )
        assert result.args[0] == 0
        assert result.args[1] == dill.dumps(target)
        assert not result.args[4]
        assert not result.args[5]
        assert result.args[6] == 10
        assert result.args[7] == s


def test_terminate_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    def target(_: bytes) -> None:
        pass  # pragma: no cover

    args: ArgsType = (
        0,
        b"deadbeef",
        utils.DummyQueue(),
        utils.DummyQueue(),
        False,
        False,
        10,
        DummyState(b"deadbeef"),
    )

    workers: list[tuple[utils.DummyProcess[ArgsType], utils.DummyQueue[fuzzer.Result]]] = [
        (utils.DummyProcess(target=target, args=args), utils.DummyQueue()),
        (utils.DummyProcess(target=target, args=args), utils.DummyQueue()),
    ]

    with monkeypatch.context() as p:
        p.setattr(multiprocessing, "get_context", lambda _: utils.DummyContext(wid=0))
        f = fuzzer.Fuzzer(crash_dir=Path("/"), target=target)
        p.setattr(f, "_workers", workers)
        assert not cast(utils.DummyQueue[fuzzer.Result], f._result_queue).canceled  # noqa: SLF001
        assert all(
            not w[0].terminated and not w[0].joined and w[0].timeout is None and not w[1].canceled
            for w in workers
        )
        f._terminate_workers()  # noqa: SLF001
        assert cast(utils.DummyQueue[fuzzer.Result], f._result_queue).canceled  # noqa: SLF001
        assert all(
            w[0].terminated and w[0].joined and w[0].timeout == 1 and w[1].canceled for w in workers
        )


def test_worker_run_ignored_exception() -> None:
    class Error:
        def __del__(self) -> None:
            raise DoneError("Exception in __del__")

    def target(_: bytes) -> None:
        Error()

    result = fuzzer._worker_run(  # noqa: SLF001
        wid=1,
        target=target,
        state=DummyState(data=b"deadbeef"),
        runs=1,
    )

    assert isinstance(result, fuzzer.Error)
    assert result.wid == 1
    assert result.runs == 1
    assert result.data == b"deadbeef"
    assert result.message == "Exception in __del__"
    assert result.covered

import re
import sys
from pathlib import Path

import dill  # type: ignore[import-untyped]
import pytest

from cobrafuzz import fuzzer


class DummyError(Exception):
    pass


def non_crashing_target(data: bytes) -> None:
    if data[0] == 42:
        return  # pragma: no cover


def crashing_target_simple(data: bytes) -> None:
    print("Failing Target\n", flush=True)  # noqa: T201
    print("Failing Target\n", file=sys.stderr, flush=True)  # noqa: T201
    if len(data) > 0 and data[0] == 42:
        raise DummyError


def crashing_target_hard(data: bytes) -> None:
    if len(data) > 0 and data[0] > 128:  # noqa: SIM102
        if len(data) > 1 and data[1] > 200:
            raise DummyError


def test_no_crash(tmp_path: Path) -> None:
    f = fuzzer.Fuzzer(target=non_crashing_target, crash_dir=tmp_path, stat_frequency=1, max_time=3)
    with pytest.raises(SystemExit, match="^0$"):
        f.start()


def test_stats(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    f = fuzzer.Fuzzer(target=non_crashing_target, crash_dir=tmp_path, max_runs=1)
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
    f = fuzzer.Fuzzer(target=non_crashing_target, crash_dir=tmp_path)
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
        fuzzer.Fuzzer(target=crashing_target_simple, crash_dir=tmp_path, regression=True)


def test_load_crashes(tmp_path: Path) -> None:
    with (tmp_path / "crash").open("wb") as cf:
        cf.write(b"*foo")
    with pytest.raises(SystemExit, match="^0$"):
        fuzzer.Fuzzer(target=crashing_target_simple, crash_dir=tmp_path, regression=True)


def test_state(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    assert not state_file.exists()
    for i in range(2):
        f = fuzzer.Fuzzer(
            target=crashing_target_simple,
            crash_dir=tmp_path,
            max_runs=1000,
            state_file=state_file,
            close_stderr=True,
            close_stdout=True,
        )
        with pytest.raises(SystemExit, match="^1$" if i == 0 else "^0$"):
            f.start()
        assert state_file.exists()


def test_crash_simple(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(target=crashing_target_simple, crash_dir=crash_dir, max_crashes=1)
    with pytest.raises(SystemExit, match="^1$"):
        f.start()
    assert crash_dir.is_dir()


def test_crash_hard(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(
        crash_dir=crash_dir,
        target=crashing_target_hard,
        max_time=5,
        num_workers=2,
        stat_frequency=1,
    )
    with pytest.raises(SystemExit, match="^1$"):
        f.start()
    assert crash_dir.is_dir()


def test_crash_with_crash_dir(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(
        target=crashing_target_simple,
        crash_dir=crash_dir,
        max_crashes=1,
    )
    with pytest.raises(SystemExit, match="^1$"):
        f.start()
    assert crash_dir.is_dir()


def test_crash_stderr_stdout_closed(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(
        target=crashing_target_simple,
        close_stderr=True,
        close_stdout=True,
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
        f = fuzzer.Fuzzer(
            target=non_crashing_target,
            crash_dir=tmp_path,
            max_runs=1,
            num_workers=1,
            load_crashes=False,
        )
        with pytest.raises(SystemExit, match="INTERNAL ERROR"):
            f.start()

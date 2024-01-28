import re
import sys
from pathlib import Path

import pytest

from cobrafuzz import fuzzer


class DummyError(Exception):
    pass


def non_crashing_target(data: bytes) -> None:
    if len(data) > 0:  # noqa: SIM102
        if data[0] == 42:
            return  # pragma: no cover


def crashing_target(data: bytes) -> None:
    print("Failing Target\n", flush=True)  # noqa: T201
    print("Failing Target\n", file=sys.stderr, flush=True)  # noqa: T201
    if len(data) > 0 and data[0] == 42:
        raise DummyError


def crashing_target_hard(data: bytes) -> None:
    if len(data) > 0 and data[0] > 128:  # noqa: SIM102
        if len(data) > 1 and data[1] > 200:
            raise DummyError


orig_exit = sys.exit


def test_no_crash(tmp_path: Path) -> None:
    f = fuzzer.Fuzzer(target=non_crashing_target, crash_dir=tmp_path, stat_frequency=1, max_time=3)
    with pytest.raises(SystemExit, match="^0$"):
        f.start()


def test_fail(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(target=crashing_target, crash_dir=crash_dir, max_crashes=2)
    with pytest.raises(SystemExit, match="^0$"):
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
    with pytest.raises(SystemExit, match="^0$"):
        f.start()
    assert crash_dir.is_dir()


def test_fail_with_artifact_path(tmp_path: Path) -> None:
    f = fuzzer.Fuzzer(
        target=crashing_target,
        crash_dir=tmp_path,
        artifact_name="artifact",
        max_crashes=1,
    )
    with pytest.raises(SystemExit, match="^0$"):
        f.start()
    assert (tmp_path / "artifact").is_file()


def test_fail_with_crash_dir(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(
        target=crashing_target,
        crash_dir=crash_dir,
        max_crashes=1,
    )
    with pytest.raises(SystemExit, match="^0$"):
        f.start()
    assert crash_dir.is_dir()


def test_stderr_stdout_closed(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(
        target=crashing_target,
        close_stderr=True,
        close_stdout=True,
        crash_dir=crash_dir,
        max_crashes=1,
    )
    with pytest.raises(SystemExit, match="^0$"):
        f.start()
    assert crash_dir.is_dir()


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
    f = fuzzer.Fuzzer(target=non_crashing_target, crash_dir=tmp_path, artifact_name="artifact")
    f._write_sample(1000 * b"x")  # noqa: SLF001
    assert (tmp_path / "artifact").is_file()


def test_regression(tmp_path: Path) -> None:
    with (tmp_path / "crash1").open("wb") as cf:
        cf.write(b"*foo")
    with (tmp_path / "crash2").open("wb") as cf:
        cf.write(b"*bar")
    with (tmp_path / "crash2").open("wb") as cf:
        cf.write(b"baz")
    (tmp_path / "subdir").mkdir()
    with pytest.raises(SystemExit, match="^0$"):
        fuzzer.Fuzzer(target=crashing_target, crash_dir=tmp_path, regression=True)

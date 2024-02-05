import sys
from pathlib import Path

import pytest

from cobrafuzz import fuzzer


class DummyError(Exception):
    pass


def crashing_target_simple(data: bytes) -> None:
    print("Failing Target\n", flush=True)  # noqa: T201
    print("Failing Target\n", file=sys.stderr, flush=True)  # noqa: T201
    if len(data) > 0 and data[0] == 42:
        raise DummyError


def crashing_target_hard(data: bytes) -> None:
    if len(data) > 0 and data[0] > 128:  # noqa: SIM102
        if len(data) > 1 and data[1] > 200:
            raise DummyError


def test_crash_simple(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(target=crashing_target_simple, crash_dir=crash_dir, max_crashes=1)
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


def test_crash_with_crash_dir(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(
        target=crashing_target_simple,
        crash_dir=crash_dir,
        max_crashes=1,
    )
    with pytest.raises(SystemExit, match="^0$"):
        f.start()
    assert crash_dir.is_dir()


def test_crash_with_artifact_path(tmp_path: Path) -> None:
    f = fuzzer.Fuzzer(
        target=crashing_target_simple,
        crash_dir=tmp_path,
        artifact_name="artifact",
        max_crashes=1,
    )
    with pytest.raises(SystemExit, match="^0$"):
        f.start()
    assert (tmp_path / "artifact").is_file()


def test_crash_stderr_stdout_closed(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(
        target=crashing_target_simple,
        close_stderr=True,
        close_stdout=True,
        crash_dir=crash_dir,
        max_crashes=1,
    )
    with pytest.raises(SystemExit, match="^0$"):
        f.start()
    assert crash_dir.is_dir()

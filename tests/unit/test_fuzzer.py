import re
import sys
import time
from pathlib import Path

import psutil
import pytest

from cobrafuzz import fuzzer, tracer


class DummyError(Exception):
    pass


class DummyResult:
    @property
    def rss(self) -> int:
        return 1024 * 1024


class DummyProcess:
    def __init__(self, _: int):
        pass

    def memory_info(self) -> DummyResult:
        return DummyResult()


def succeeding_target(_: bytes) -> None:
    pass


def failing_target(data: bytes) -> None:
    print("Failing Target\n", flush=True)  # noqa: T201
    print("Failing Target\n", file=sys.stderr, flush=True)  # noqa: T201
    if len(data) > 0 and data[0] == 42:
        raise DummyError


def failing_target_hard(data: bytes) -> None:  # pragma: no cover
    if len(data) > 1 and data[0:1] == b"de":  # noqa: SIM102
        if len(data) > 3 and data[2:3] == b"ad":
            raise DummyError


def timeout_target(_: bytes) -> None:
    time.sleep(100)  # pragma: no cover


orig_exit = sys.exit


def test_success(tmp_path: Path) -> None:
    f = fuzzer.Fuzzer(target=succeeding_target, crash_dir=tmp_path, runs=100)
    with pytest.raises(SystemExit, match="^0$"):
        f.start()


def test_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(target=failing_target, crash_dir=crash_dir)
    with monkeypatch.context() as mp:
        mp.setattr(tracer, "get_coverage", lambda: 1000)
        with pytest.raises(SystemExit, match="^76$"):
            f.start()
    assert crash_dir.is_dir()


def test_fail_with_artifact_path(tmp_path: Path) -> None:
    f = fuzzer.Fuzzer(target=failing_target, crash_dir=tmp_path, artifact_name="artifact")
    with pytest.raises(SystemExit, match="^76$"):
        f.start()
    assert (tmp_path / "artifact").is_file()


def test_fail_with_crash_dir(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(target=failing_target, crash_dir=crash_dir)
    with pytest.raises(SystemExit, match="^76$"):
        f.start()
    assert crash_dir.is_dir()


def test_stderr_stdout_closed(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(target=failing_target, close_fd_mask=3, crash_dir=crash_dir)
    with pytest.raises(SystemExit, match="^76$"):
        f.start()
    assert crash_dir.is_dir()


def test_stats(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f = fuzzer.Fuzzer(target=succeeding_target, crash_dir=tmp_path, runs=1)
    with pytest.raises(SystemExit, match="^0$"):
        f.start()
    with monkeypatch.context() as mp:
        mp.setattr(psutil, "Process", DummyProcess)
        assert f.log_stats("CUSTOM") == 2
    assert re.match(
        r".*CUSTOM\s+cov: 0 corp: 1 exec/s: \d+ rss: 2 MB\n.*",
        caplog.text,
        flags=re.DOTALL,
    )


def test_oom(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f = fuzzer.Fuzzer(target=failing_target_hard, crash_dir=tmp_path, rss_limit_mb=1)
    with monkeypatch.context() as mp:
        mp.setattr(psutil, "Process", DummyProcess)
        with pytest.raises(SystemExit, match="^0$"):
            f.start()
    assert "MEMORY OOM: exceeded 1 MB. Killing worker" in caplog.text


def test_timeout(tmp_path: Path) -> None:
    crash_dir = tmp_path / "crashes"
    f = fuzzer.Fuzzer(target=timeout_target, crash_dir=crash_dir, timeout=5)
    with pytest.raises(SystemExit, match="^0$"):
        f.start()
    assert crash_dir.is_dir()


def test_write_sample(tmp_path: Path) -> None:
    f = fuzzer.Fuzzer(target=succeeding_target, crash_dir=tmp_path, artifact_name="artifact")
    f.write_sample(1000 * b"x")
    assert (tmp_path / "artifact").is_file()

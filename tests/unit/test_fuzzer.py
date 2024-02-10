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
    with (tmp_path / "crash2").open("wb") as cf:
        cf.write(b"baz")
    (tmp_path / "subdir").mkdir()
    with pytest.raises(SystemExit, match="^0$"):
        fuzzer.Fuzzer(target=crashing_target, crash_dir=tmp_path, regression=True)

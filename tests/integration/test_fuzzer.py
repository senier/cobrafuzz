from pathlib import Path

import pytest

from cobrafuzz import fuzzer


def non_crashing_target(data: bytes) -> None:
    if len(data) > 0 and data[0] == 42:
        return  # pragma: no cover


def test_no_crash(tmp_path: Path) -> None:
    f = fuzzer.Fuzzer(target=non_crashing_target, crash_dir=tmp_path, stat_frequency=1, max_time=3)
    with pytest.raises(SystemExit, match="^0$"):
        f.start()

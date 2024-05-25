import logging
from pathlib import Path

import pytest

from cobrafuzz.prune import prune


def test_prune(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    def target(data: bytes) -> None:
        assert b"crash" not in data

    (tmp_path / "f1").write_bytes(b"crash 1")
    (tmp_path / "f2").write_bytes(b"crash 2")
    (tmp_path / "f3").write_bytes(b"invalid 1")
    (tmp_path / "f4").write_bytes(b"invalid 2")
    (tmp_path / "d").mkdir()

    with caplog.at_level(logging.INFO):
        prune(crash_dir=tmp_path, target=target)

    assert (tmp_path / "f1").read_bytes() == b"crash 1"
    assert (tmp_path / "f2").read_bytes() == b"crash 2"
    assert (tmp_path / "d").is_dir()
    assert not (tmp_path / "f3").exists()
    assert not (tmp_path / "f4").exists()

    assert caplog.record_tuples == [
        ("root", logging.INFO, "No crash, deleting f3"),
        ("root", logging.INFO, "No crash, deleting f4"),
    ]

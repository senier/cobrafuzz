import sys
from pathlib import Path

import pytest

from cobrafuzz.main import CobraFuzz


def test_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def target(_: bytes) -> None:
        pass

    with monkeypatch.context() as mp:
        mp.setattr(
            sys,
            "argv",
            [
                "main",
                "--crash-dir",
                str(tmp_path),
                "fuzz",
                "--max-runs",
                "500",
                "--max-crashes",
                "1",
            ],
        )
        c = CobraFuzz(target)
        with pytest.raises(SystemExit, match="^0$"):
            c()

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Union

import pytest

from cobrafuzz import fuzzer
from cobrafuzz.main import CobraFuzz


def test_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args: Optional[dict[str, Union[bool, int, Path]]] = None

    class Fuzzer:
        def __init__(self, **a: Union[bool, int, Path]) -> None:
            nonlocal args
            args = a

        def start(self) -> None:
            pass

    with monkeypatch.context() as mp:
        mp.setattr(
            sys,
            "argv",
            [
                "main",
                "--crash-dir",
                str(tmp_path),
                "--max-runs",
                "500",
                "--max-crashes",
                "1",
            ],
        )
        mp.setattr(fuzzer, "Fuzzer", Fuzzer)
        c = CobraFuzz(lambda _: None)  # pragma: no cover
        c()
        assert args is not None
        assert args["crash_dir"] == tmp_path
        assert args["max_runs"] == 500
        assert args["max_crashes"] == 1


def test_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Fuzzer:
        def __init__(self, **_: dict[str, Union[bool, int, Path]]) -> None:
            pass

        def start(self) -> None:
            raise KeyboardInterrupt

    with monkeypatch.context() as mp:
        mp.setattr(
            sys,
            "argv",
            [
                "main",
                "--crash-dir",
                str(tmp_path),
                "--max-runs",
                "500",
                "--max-crashes",
                "1",
            ],
        )
        mp.setattr(fuzzer, "Fuzzer", Fuzzer)
        c = CobraFuzz(func=lambda _: None)  # pragma: no cover
        with pytest.raises(SystemExit, match=r"^\nUser cancellation\. Exiting\.\n$"):
            c()

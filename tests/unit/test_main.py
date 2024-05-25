from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional, Union

import pytest

from cobrafuzz import fuzzer, prune, simplifier
from cobrafuzz.main import CobraFuzz


def test_main_fuzz(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
                "fuzz",
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


def test_main_show(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args: Optional[dict[str, Union[bool, int, Path]]] = None

    class Fuzzer:
        def __init__(self, **a: Union[bool, int, Path]) -> None:
            nonlocal args
            args = a

    with monkeypatch.context() as mp:
        mp.setattr(
            sys,
            "argv",
            [
                "main",
                "--crash-dir",
                str(tmp_path),
                "show",
            ],
        )
        mp.setattr(fuzzer, "Fuzzer", Fuzzer)
        c = CobraFuzz(lambda _: None)  # pragma: no cover
        c()
        assert args is not None
        assert args["crash_dir"] == tmp_path


def test_main_simp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args: Optional[dict[str, Union[Path, Callable[[bytes], None]]]] = None
    simplify_called: bool = False

    class Simp:
        def __init__(self, **a: Union[Path, Callable[[bytes], None]]) -> None:
            nonlocal args
            args = a

        def simplify(self) -> None:
            nonlocal simplify_called
            simplify_called = True

    with monkeypatch.context() as mp:
        mp.setattr(
            sys,
            "argv",
            [
                "main",
                "--crash-dir",
                str(tmp_path / "crash"),
                "simp",
                "--output-dir",
                str(tmp_path / "output"),
            ],
        )
        mp.setattr(simplifier, "Simp", Simp)
        c = CobraFuzz(lambda _: None)  # pragma: no cover
        c()
        assert simplify_called
        assert args is not None
        assert args["crash_dir"] == tmp_path / "crash"
        assert args["output_dir"] == tmp_path / "output"
        assert args["target"] is not None


def test_main_prune(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args: Optional[dict[str, Union[Path, Callable[[bytes], None]]]] = None

    def dummy_prune(**a: Union[Path, Callable[[bytes], None]]) -> None:
        nonlocal args
        args = a

    with monkeypatch.context() as mp:
        mp.setattr(
            sys,
            "argv",
            [
                "main",
                "--crash-dir",
                str(tmp_path),
                "prune",
            ],
        )
        mp.setattr(prune, "prune", dummy_prune)
        c = CobraFuzz(lambda _: None)  # pragma: no cover
        c()
        assert args is not None
        assert args["crash_dir"] == tmp_path


def test_main_no_subcommand(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with monkeypatch.context() as mp:
        mp.setattr(
            sys,
            "argv",
            [
                "main",
                "--crash-dir",
                str(tmp_path),
            ],
        )
        c = CobraFuzz(lambda _: None)  # pragma: no cover
        with pytest.raises(SystemExit, match="^3$"):
            c()


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
                "fuzz",
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

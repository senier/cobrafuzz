import importlib
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test",
    [
        "aifc",
        "beautifulsoup",
        "codeop",
        "furl",
        "fuzzit",
        "htmlparser",
        "isort",
        "purl",
        "xml",
        "zipfile",
        "zlib",
    ],
)
def test_example(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    test: str,
) -> None:
    with monkeypatch.context() as mp:
        mp.setattr(sys, "argv", ["fuzz", "--crash-dir", str(tmp_path), "--runs", "100"])
        fuzz = importlib.import_module(f"examples.{test}.fuzz")
        with pytest.raises(SystemExit, match="^0$"):
            fuzz.fuzz()

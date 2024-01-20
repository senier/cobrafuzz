import importlib
import sys

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
def test_example(monkeypatch: pytest.MonkeyPatch, test: str) -> None:
    with monkeypatch.context() as mp:
        mp.setattr(sys, "argv", ["fuzz", "--runs", "100"])
        fuzz = importlib.import_module(f"examples.{test}.fuzz")
        with pytest.raises(SystemExit, match="^0$"):
            fuzz.fuzz()

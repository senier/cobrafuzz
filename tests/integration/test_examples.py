import importlib
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test",
    [
        "aifc",
        "bs",
        "charset_normalizer",
        "cobrafuzz",
        "codeop",
        "furl",
        "htmlparser",
        "idna",
        "isort",
        "purl",
        "requests",
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
        mp.setattr(
            sys,
            "argv",
            [
                "fuzz",
                "--crash-dir",
                str(tmp_path),
                "fuzz",
                "--max-runs",
                "100",
                "examples/fuzz_{test}/seeds",
            ],
        )
        fuzz = importlib.import_module(f"examples.fuzz_{test}.fuzz")
        with pytest.raises(SystemExit, match="^0$"):
            fuzz.fuzz()

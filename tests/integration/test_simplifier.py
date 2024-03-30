from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest

from cobrafuzz import simplifier


def target(data: bytes) -> None:
    if not data.startswith(b"START"):
        return
    if not data.endswith(b"END"):
        return
    if b"CRASH" in data:
        raise AttributeError
    if b"BOOM" in data:
        raise AttributeError


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            b"""START
            UNRELATED
            CRASH
            END""",
            b"""START
            CRASH
            END""",
        ),
        (
            b"""START
            CRASH
            END""",
            b"""START
            CRASH
            END""",
        ),
        (
            b"""START

            CRASH

            END""",
            b"""START
            CRASH
            END""",
        ),
        (
            b"""START
            CRASH
            BOOM
            END""",
            b"""START
            CRASH
            END""",
        ),
    ],
    ids=range(1, 5),
)
def test_simplify(
    tmp_path: Path,
    data: bytes,
    expected: Optional[bytes],
) -> None:
    s = simplifier.Simp(  # pragma: no cover
        crash_dir=tmp_path / "crash",
        output_dir=tmp_path / "output",
        target=target,
        steps=10000,
    )
    assert s._simplify(data) == expected  # noqa: SLF001

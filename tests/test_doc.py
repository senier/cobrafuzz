from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional, Sequence

import pytest


def _extract_code_from_readme() -> Sequence[Any]:  # type: ignore[misc]
    result: list[Any] = []  # type: ignore[misc]
    code: list[str] = []
    file: Optional[Path] = None
    with Path("README.md").open() as f:
        inside = False
        for line in f.readlines():
            match = re.match(r"^```python,(.*)$", line)
            if match:
                file = Path(match.group(1))
                inside = True
            else:
                match = re.match(r"^```$", line)
                if inside:
                    if match:
                        assert file is not None
                        result.append(pytest.param("".join(code), file, id=str(file)))
                        code = []
                        inside = False
                        file = None
                    else:
                        code.append(line)
    return result


@pytest.mark.parametrize(("code", "path"), _extract_code_from_readme())
def test_readme(code: str, path: Path) -> None:
    assert path.read_text() == code

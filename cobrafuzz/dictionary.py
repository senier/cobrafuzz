from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Optional


class Dictionary:
    line_re = re.compile('"(.+)"$')

    def __init__(self, dict_path: Optional[Path] = None) -> None:
        if not dict_path or not dict_path.exists():
            self._dict = []
            return

        _dict: set[str] = set()
        with dict_path.open() as f:
            for l in f:
                line = l.lstrip()
                if line.startswith("#"):
                    continue
                word = self.line_re.search(line)
                if word:
                    _dict.add(word.group(1))
        self._dict = list(_dict)

    def get_word(self) -> Optional[str]:
        if not self._dict:
            return None
        return random.choice(self._dict)  # noqa: S311

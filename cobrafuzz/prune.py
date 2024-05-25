import logging
from pathlib import Path
from typing import Callable

from cobrafuzz import util


def prune(crash_dir: Path, target: Callable[[bytes], None]) -> None:
    for f in sorted(crash_dir.glob(pattern="*")):
        assert isinstance(f, Path)
        if not f.is_file():
            continue

        try:
            with util.disable_logging():
                target(f.read_bytes())
        except Exception:  # noqa: BLE001, S110
            pass
        else:
            logging.info("No crash, deleting %s", f.name)
            f.unlink()

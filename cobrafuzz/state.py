from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from cobrafuzz import mutator


class LoadError(Exception):
    pass


class State:
    def __init__(  # noqa: PLR0913
        self,
        seeds: Optional[list[Path]] = None,
        max_input_size: int = 4096,
        max_modifications: int = 10,
        max_insert_length: int = 10,
        adaptive: bool = True,
        file: Optional[Path] = None,
    ):
        seeds = seeds or []

        self._VERSION = 1
        self._max_input_size = max_input_size
        self._covered: set[tuple[Optional[str], Optional[int], str, int]] = set()
        self._file = file
        self._mutator = mutator.Mutator(
            max_input_size=max_input_size,
            max_modifications=max_modifications,
            max_insert_length=max_insert_length,
            adaptive=adaptive,
        )

        for path in [p for p in seeds if p.is_file()] + [
            f for p in seeds if p.is_dir() for f in p.glob("*") if f.is_file()
        ]:
            with path.open("rb") as f:
                self._mutator.put_input(bytearray(f.read()))

        self._num_seeds = self._mutator.input_length()
        if not self._num_seeds:
            self._mutator.put_input(bytearray(0))
        self._load()

    def _load(self) -> None:
        if not self._file:
            return

        try:
            with self._file.open() as sf:
                data = json.load(sf)
                if "version" not in data or data["version"] != self._VERSION:
                    raise LoadError(
                        f"Invalid version in state file {self._file} (expected {self._VERSION})",
                    )
                self._covered |= {tuple(e) for e in data["coverage"]}
                self._mutator.restore(data["population"])
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, TypeError):
            self._file.unlink()
            logging.info("Malformed state file: %s", self._file)
        except OSError as e:
            logging.info("Error opening state file: %s", e)
            self._file = None

    @property
    def num_seeds(self) -> int:
        return self._num_seeds

    def save(self) -> None:
        if not self._file:
            return
        with self._file.open(mode="w+") as sf:
            json.dump(
                obj={
                    "version": self._VERSION,
                    "coverage": list(self._covered),
                    "population": self._mutator.dump(),
                },
                fp=sf,
                ensure_ascii=True,
            )

    def store_coverage(
        self,
        data: set[tuple[Optional[str], Optional[int], str, int]],
    ) -> bool:
        """
        Store coverage information. Return true if coverage has increased.

        Arguments:
        ---------
        data: coverage information to store.
        """

        covered = len(self._covered)
        self._covered |= data
        if len(self._covered) > covered:
            return True
        return False

    @property
    def total_coverage(self) -> int:
        return len(self._covered)

    @property
    def size(self) -> int:
        return self._mutator.input_length()

    def put_input(self, buf: bytearray) -> None:
        self._mutator.put_input(buf)

    def get_input(self) -> bytearray:
        return self._mutator.get_input()

    def update(self, success: bool = False) -> None:
        self._mutator.update(success=success)

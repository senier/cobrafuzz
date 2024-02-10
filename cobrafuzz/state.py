from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Optional

from cobrafuzz import mutator, util


class LoadError(Exception):
    pass


class State:
    def __init__(
        self,
        seeds: Optional[list[Path]] = None,
        max_input_size: int = 4096,
        file: Optional[Path] = None,
    ):
        seeds = seeds or []

        self._VERSION = 1
        self._max_input_size = max_input_size
        self._covered: set[tuple[Optional[str], Optional[int], str, int]] = set()
        self._inputs: list[bytearray] = []
        self._file = file

        for path in [p for p in seeds if p.is_file()] + [
            f for p in seeds if p.is_dir() for f in p.glob("*") if f.is_file()
        ]:
            with path.open("rb") as f:
                self._inputs.append(bytearray(f.read()))

        self._num_seeds = len(self._inputs)
        if not self._inputs:
            self._inputs.append(bytearray(0))
        self._load()

    @property
    def num_seeds(self) -> int:
        return self._num_seeds

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
                self._inputs.extend(bytearray(ast.literal_eval(i)) for i in data["population"])
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, TypeError):
            self._file.unlink()
            logging.info("Malformed state file: %s", self._file)
        except OSError as e:
            logging.info("Error opening state file: %s", e)
            self._file = None

    def save(self) -> None:
        if not self._file:
            return
        with self._file.open(mode="w+") as sf:
            json.dump(
                obj={
                    "version": self._VERSION,
                    "coverage": list(self._covered),
                    "population": [str(bytes(i)) for i in self._inputs],
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
        return len(self._inputs)

    def put_input(self, buf: bytearray) -> None:
        self._inputs.append(buf)

    def get_input(self) -> bytearray:
        return mutator.mutate(
            buf=list(self._inputs)[util.rand(len(self._inputs))],
            max_input_size=self._max_input_size,
        )

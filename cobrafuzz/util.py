from __future__ import annotations

import random
from abc import abstractmethod
from typing import Generator, Generic, Optional, TypeVar

from . import common

PopulationType = TypeVar("PopulationType")


class ParamBase(Generic[PopulationType]):
    @abstractmethod
    def update(self, success: bool = False) -> None:
        raise NotImplementedError


class Param(ParamBase[int]):
    def __init__(self, value: int) -> None:
        self._value = value

    def __call__(self) -> int:
        return self._value

    def update(self, success: bool = False) -> None:
        pass


class AdaptiveRandBase(ParamBase[PopulationType]):
    def _succeed(self) -> None:
        raise NotImplementedError

    def _fail(self) -> None:
        raise NotImplementedError

    def update(self, success: bool = False) -> None:
        if success:
            self._succeed()
        else:
            self._fail()


class AdaptiveRange(AdaptiveRandBase[int]):
    def __init__(self, adaptive: bool = True) -> None:
        self._adaptive = adaptive
        self._population: list[Optional[int]] = [None]
        self._distribution: list[int] = [1]
        self._last_value: Optional[int] = None
        self._last_index: int = 0

    def _succeed(self) -> None:
        if not self._adaptive:
            return
        if self._last_index:
            self._distribution[self._last_index] += 1
        else:
            self._population.append(self._last_value)
            self._distribution.append(1)

        self._distribution[0] += 1
        self._last_index = 1

    def _fail(self) -> None:
        if not self._adaptive or not self._last_index:
            return

        if self._distribution[self._last_index] <= 1:
            del self._distribution[self._last_index]
            del self._population[self._last_index]
        else:
            self._distribution[self._last_index] -= 1

        self._distribution[0] -= 1
        self._last_index = 0

    def sample(self, lower: int, upper: int) -> int:
        if lower > upper:
            raise common.OutOfBoundsError(
                f"Lower bound must be lower than upper bound ({lower} > {upper})",
            )
        if not self._adaptive:
            return random.randint(lower, upper)  # noqa: S311
        self._last_value = random.choices(self._population, self._distribution)[0]  # noqa: S311
        if self._last_value is None or self._last_value < lower or self._last_value > upper:
            self._last_value = random.randint(lower, upper)  # noqa: S311
        else:
            self._last_index = self._population.index(self._last_value)  # pragma: no cover
        return self._last_value


class AdaptiveChoiceBase(AdaptiveRandBase[PopulationType]):
    def __init__(self, population: Optional[list[PopulationType]], adaptive: bool = True) -> None:
        self._population = population or []
        self._distribution = [1 for _ in self._population] if adaptive else None
        self._last: Optional[PopulationType] = None

    def __len__(self) -> int:
        return len(self._population)

    def __iter__(self) -> Generator[PopulationType, None, None]:
        yield from self._population

    def _succeed(self) -> None:
        if self._distribution is None or self._last is None:
            return
        self._distribution[self._population.index(self._last)] += 1

    def _fail(self) -> None:
        if self._distribution is None or self._last is None:
            return
        if self._distribution[self._population.index(self._last)] > 1:
            self._distribution[self._population.index(self._last)] -= 1

    def append(self, element: PopulationType) -> None:
        self._population.append(element)
        if self._distribution is not None:
            self._distribution.append(1)

    def sample(self) -> PopulationType:
        if self._distribution is None:
            return random.choice(self._population)  # noqa: S311
        self._last = random.choices(self._population, self._distribution, k=1)[0]  # noqa: S311
        return self._last


def copy(
    data: bytearray,
    source: int,
    dest: int,
    length: Optional[int] = None,
) -> None:
    """
    Copy bytes from source to destination array.

    Arguments:
    ---------
    data: Source array.
    source: Start offset in source array.
    dest: Start offset in destination array.
    length: Number of bytes to copy (default: all source offset to end)
    """
    length = len(data) - source if length is None else length

    if source >= len(data):
        raise common.OutOfBoundsError(f"Source out of range ({source=}, length={len(data)})")
    if source + length > len(data):
        raise common.OutOfBoundsError(
            f"Source end out of range (end={source + length - 1}, length={len(data)})",
        )
    if dest >= len(data):
        raise common.OutOfBoundsError(f"Destination out of range ({dest=}, length={len(data)})")
    if dest + length > len(data):
        raise common.OutOfBoundsError(
            f"Destination end out of range (end={dest + length - 1}, length={len(data)})",
        )
    data[dest : dest + length] = data[source : source + length]


def remove(data: bytearray, start: int, length: int) -> None:
    """
    Remove part of a bytearray.

    Arguments:
    ---------
    data: bytearray to modify.
    start: Start position of chunk to remove (inclusive).
    length: Number of bytes to remove.
    """
    if start >= len(data):
        raise common.OutOfBoundsError(f"Start out of range ({start=}, length={len(data)})")
    if start + length > len(data):
        raise common.OutOfBoundsError(
            f"End out of range (end={start + length - 1}, length={len(data)})",
        )
    data[:] = data[:start] + data[start + length :]


def insert(data: bytearray, start: int, data_to_insert: bytes) -> None:
    """
    Insert data into bytearray.

    Arguments:
    ---------
    data: bytearray to modify.
    start: Position where to insert new data.
    data_to_insert: bytearray to insert.
    """
    if start > len(data):
        raise common.OutOfBoundsError("Start out of range")
    data[:] = data[:start] + data_to_insert + data[start:]

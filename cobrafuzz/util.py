from __future__ import annotations

import random
from typing import Generic, Optional, TypeVar


class OutOfBoundsError(Exception):
    pass


PopulationType = TypeVar("PopulationType")


class AdaptiveRandBase(Generic[PopulationType]):
    def sample(self) -> PopulationType:
        raise NotImplementedError

    def success(self) -> None:
        raise NotImplementedError

    def fail(self) -> None:
        raise NotImplementedError


class AdaptiveLargeRange(AdaptiveRandBase[int]):
    def __init__(self, lower: int, upper: int) -> None:
        self._lower = lower
        self._upper = upper
        self._population: list[Optional[int]] = [None]
        self._distribution: list[int] = [1]
        self._last: Optional[int] = None

    def sample(self) -> int:
        self._last = random.choices(self._population, self._distribution, k=1)[0]  # noqa: S311
        if self._last is None:
            self._last = random.randint(self._lower, self._upper)  # noqa: S311
        return self._last

    def succeed(self) -> None:
        if self._last in self._population:
            self._distribution[self._population.index(self._last)] += 1
        else:
            self._population.append(self._last)
            self._distribution.append(0)

        self._distribution[0] += 1

    def fail(self) -> None:
        if self._last not in self._population:
            return

        index = self._population.index(self._last)
        if self._distribution[index] <= 1:
            del self._distribution[index]
            del self._population[index]
        else:
            self._distribution[index] -= 1
        self._distribution[0] -= 1


class AdaptiveChoiceBase(AdaptiveRandBase[PopulationType]):
    def __init__(self, population: list[PopulationType]) -> None:
        self._population = population
        self._distribution = [1.0 for _ in self._population]
        self._last: Optional[PopulationType] = None

    def _normalize_distribution(self) -> None:
        total = sum(self._distribution)
        self._distribution = [p / total for p in self._distribution]

    def sample(self) -> PopulationType:
        self._last = random.choices(self._population, self._distribution, k=1)[0]  # noqa: S311
        return self._last

    def success(self) -> None:
        if self._last is None:
            raise OutOfBoundsError("Update without previous sample")
        self._distribution[self._population.index(self._last)] *= 1.1
        self._normalize_distribution()

    def fail(self) -> None:
        if self._last is None:
            raise OutOfBoundsError("Update without previous sample")
        self._distribution[self._population.index(self._last)] *= 0.9
        self._normalize_distribution()


class AdaptiveIntChoice(AdaptiveChoiceBase[int]):
    pass


class AdaptiveRange(AdaptiveIntChoice):
    def __init__(self, lower: int, upper: int) -> None:
        if lower > upper:
            raise OutOfBoundsError(
                f"Lower bound must be lower than upper bound ({lower} > {upper})",
            )
        super().__init__(list(range(lower, upper + 1)))
        self._lower = lower
        self._upper = upper

    def sample_max(self, maximum: int) -> int:
        if maximum < self._lower:
            raise OutOfBoundsError(
                f"Maximum must be greater than lower bound ({maximum} < {self._lower})",
            )
        if maximum > self._upper:
            raise OutOfBoundsError(
                f"Maximum must be smaller or equal to upper bound ({maximum} > {self._upper})",
            )
        if maximum == self._lower:
            return self._lower

        self._last = random.choices(  # noqa: S311
            population=self._population[: maximum - self._lower],
            weights=self._distribution[: maximum - self._lower],
            k=1,
        )[0]

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
        raise OutOfBoundsError(f"Source out of range ({source=}, length={len(data)})")
    if source + length > len(data):
        raise OutOfBoundsError(
            f"Source end out of range (end={source + length - 1}, length={len(data)})",
        )
    if dest >= len(data):
        raise OutOfBoundsError(f"Destination out of range ({dest=}, length={len(data)})")
    if dest + length > len(data):
        raise OutOfBoundsError(
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
        raise OutOfBoundsError(f"Start out of range ({start=}, length={len(data)})")
    if start + length > len(data):
        raise OutOfBoundsError(f"End out of range (end={start + length - 1}, length={len(data)})")
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
        raise OutOfBoundsError("Start out of range")
    data[:] = data[:start] + data_to_insert + data[start:]

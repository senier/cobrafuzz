from __future__ import annotations

from secrets import choice, randbelow, randbits
from typing import Optional


class OutOfBoundsError(Exception):
    pass


def rand(n: int) -> int:
    if n < 1:
        return 0
    return randbelow(n)


def rand_bool() -> bool:
    return choice([True, False])


def rand_exp() -> int:
    """Generate random value with distribution 1/2^(n+1)."""
    return f"{randbits(32):032b}1".index("1")


def choose_len(n: int) -> int:
    """
    Choose a length based on input value.

    With 90% probability, choose a random value in [1, n] (if n <=  8, otherwise [1, 8])
    With  9% probability, choose a random value in [1, n] (if n <= 32, otherwise [1, 32])
    With  1% probability, choose a random value in [1, n]
    """
    x = rand(100)
    if x < 90:
        return rand(min(8, n)) + 1
    if x < 99:
        return rand(min(32, n)) + 1
    return rand(n) + 1


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

# ruff: noqa: SLF001

import random
from copy import deepcopy

import pytest

from cobrafuzz import common, util


@pytest.mark.parametrize(
    ("data", "source", "dest", "length", "error"),
    [
        (b"0123456789", 20, 3, 3, r"Source out of range \(source=20, length=10\)"),
        (b"0123456789", 5, 0, 20, r"Source end out of range \(end=24, length=10\)"),
        (b"0123456789", 4, 20, 3, r"Destination out of range \(dest=20, length=10\)"),
        (b"0123456789", 4, 9, 5, r"Destination end out of range \(end=13, length=10\)"),
    ],
)
def test_copy_invalid(data: bytes, source: int, dest: int, length: int, error: str) -> None:
    tmp = bytearray(data)
    with pytest.raises(common.OutOfBoundsError, match=rf"^{error}$"):
        util.copy(tmp, source, dest, length)


@pytest.mark.parametrize(
    ("data", "source", "dest", "length", "expected"),
    [
        (b"0123456789", 0, 3, 3, b"0120126789"),
        (b"0123456789", 5, 0, 5, b"5678956789"),
        (b"0123456789", 4, 0, 6, b"4567896789"),
        (b"0123456789", 4, 4, 0, b"0123456789"),
    ],
)
def test_copy_valid(data: bytes, source: int, dest: int, length: int, expected: bytes) -> None:
    tmp = bytearray(data)
    util.copy(tmp, source, dest, length)
    assert tmp == bytearray(expected)


@pytest.mark.parametrize(
    ("data", "start", "length", "error"),
    [
        (b"", 1, 2, r"^Start out of range \(start=1, length=0\)$"),
        (b"deadbeef", 8, 5, r"^Start out of range \(start=8, length=8\)$"),
        (b"deadbeef", 2, 10, r"^End out of range \(end=11, length=8\)$"),
    ],
)
def test_remove_invalid(data: bytes, start: int, length: int, error: str) -> None:
    tmp = bytearray(data)
    with pytest.raises(common.OutOfBoundsError, match=error):
        util.remove(tmp, start, length)


@pytest.mark.parametrize(
    ("data", "start", "length", "expected"),
    [
        (b"deadbeef", 1, 4, b"deef"),
        (b"deadbeef", 0, 2, b"adbeef"),
        (b"deadbeef", 6, 2, b"deadbe"),
        (b"deadbeef", 7, 1, b"deadbee"),
        (b"deadbeef", 0, 8, b""),
    ],
)
def test_remove_valid(data: bytes, start: int, length: int, expected: bytes) -> None:
    tmp = bytearray(data)
    util.remove(tmp, start, length)
    assert tmp == bytearray(expected)


@pytest.mark.parametrize(
    ("data", "start", "data_to_insert", "error"),
    [
        (b"", 1, b"data", r"^Start out of range$"),
        (b"deadbeef", 9, b"data", r"^Start out of range$"),
    ],
)
def test_insert_invalid(data: bytes, start: int, data_to_insert: bytes, error: str) -> None:
    tmp = bytearray(data)
    with pytest.raises(common.OutOfBoundsError, match=error):
        util.insert(tmp, start, data_to_insert)


@pytest.mark.parametrize(
    ("data", "start", "data_to_insert", "expected"),
    [
        (b"", 0, b"data", b"data"),
        (b"deadbeef", 4, b"data", b"deaddatabeef"),
        (b"deadbeef", 8, b"data", b"deadbeefdata"),
    ],
)
def test_insert_valid(data: bytes, start: int, data_to_insert: bytes, expected: bytes) -> None:
    tmp = bytearray(data)
    util.insert(tmp, start, data_to_insert)
    assert tmp == expected


def test_adaptive_range_invalid_bounds() -> None:
    r = util.AdaptiveRange()
    with pytest.raises(
        common.OutOfBoundsError,
        match=r"^Lower bound must be lower than upper bound \(10 > 0\)$",
    ):
        r.sample(10, 0)


def test_adaptive_range_update() -> None:
    r = util.AdaptiveRange()
    v = r.sample(lower=1, upper=1)
    assert v == 1
    assert r._population == [None]
    assert r._distribution == [1]

    r.update(success=True)
    assert r._population == [None, 1]
    assert r._distribution == [2, 1]

    v = r.sample(lower=1, upper=1)
    assert v == 1
    assert r._population == [None, 1]
    assert r._distribution == [2, 1]

    r.update(success=True)
    assert r._population == [None, 1]
    assert r._distribution == [3, 2]

    v = r.sample(lower=1, upper=1)
    assert v == 1
    assert r._population == [None, 1]
    assert r._distribution == [3, 2]

    v = r.sample(lower=1, upper=1)
    assert v == 1
    assert r._population == [None, 1]
    assert r._distribution == [3, 2]

    r.update(success=False)
    assert r._population == [None, 1]
    assert r._distribution == [2, 1]


def test_adaptive_range_in_range() -> None:
    for _ in range(1, 1000):
        lower = random.randint(0, 1000)  # noqa: S311
        upper = random.randint(lower, 1000)  # noqa: S311
        r = util.AdaptiveRange()
        sample = r.sample(lower=lower, upper=upper)
        assert lower <= sample <= upper


@pytest.mark.parametrize("success", [True, False])
def test_non_adaptive_range(success: bool) -> None:
    def eq(l: util.AdaptiveRange, r: util.AdaptiveRange) -> bool:
        return (
            l._adaptive == r._adaptive
            and l._population == r._population
            and l._distribution == r._distribution
            and l._last_index == r._last_index
            and l._last_value == r._last_value
        )

    r = util.AdaptiveRange(adaptive=False)
    v = r.sample(lower=1, upper=1)
    assert v == 1
    c = deepcopy(r)
    assert eq(r, c)
    r.update(success=success)
    assert eq(r, c)


def test_adaptive_range_drop_entry() -> None:
    r = util.AdaptiveRange()
    v = r.sample(upper=1, lower=1)
    assert v == 1
    r.update(success=True)
    assert r._population == [None, 1]
    v = r.sample(upper=1, lower=1)
    assert v == 1
    r.update(success=False)
    assert r._population == [None]


def test_param() -> None:
    p = util.Param(5)
    assert p() == 5
    p.update()
    assert p() == 5


def test_adaptive_choice() -> None:
    c = util.AdaptiveChoiceBase(population=[1], adaptive=True)
    assert c._population == [1]
    assert c._distribution == [1]
    v = c.sample()
    assert v == 1
    c.update(success=True)
    assert c._population == [1]
    assert c._distribution == [2]
    c.update(success=False)
    assert c._population == [1]
    assert c._distribution == [1]
    c.update(success=False)
    assert c._population == [1]
    assert c._distribution == [1]
    c.append(2)
    assert c._population == [1, 2]
    assert c._distribution == [1, 1]


def test_non_adaptive_choice() -> None:
    c = util.AdaptiveChoiceBase(population=[1], adaptive=False)
    assert c._population == [1]
    assert c._distribution is None
    v = c.sample()
    assert v == 1
    c.update(success=True)
    assert c._population == [1]
    assert c._distribution is None
    c.update(success=False)
    assert c._population == [1]
    assert c._distribution is None
    c.append(2)
    assert c._population == [1, 2]
    assert c._distribution is None

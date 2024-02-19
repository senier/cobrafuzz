import random

import numpy as np
import pytest
from scipy.stats import chisquare

from cobrafuzz import util


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
    with pytest.raises(util.OutOfBoundsError, match=rf"^{error}$"):
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
    with pytest.raises(util.OutOfBoundsError, match=error):
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
    with pytest.raises(util.OutOfBoundsError, match=error):
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


def test_adaptive_rand_invalid_bounds() -> None:
    with pytest.raises(
        util.OutOfBoundsError,
        match=r"^Lower bound must be lower than upper bound \(10 > 0\)$",
    ):
        util.AdaptiveRange(lower=10, upper=0)


def test_adaptive_rand_sample_below_invalid_bounds() -> None:
    r = util.AdaptiveRange(lower=2, upper=10)
    with pytest.raises(
        util.OutOfBoundsError,
        match=r"^Maximum must be greater than lower bound \(1 < 2\)$",
    ):
        r.sample_max(1)

    with pytest.raises(
        util.OutOfBoundsError,
        match=r"^Maximum must be smaller or equal to upper bound \(11 > 10\)$",
    ):
        r.sample_max(11)


@pytest.mark.parametrize("success", [True, False])
def test_adaptive_rand_invalid_update_without_sample(success: bool) -> None:
    r = util.AdaptiveRange(lower=0, upper=10)
    with pytest.raises(
        util.OutOfBoundsError,
        match=r"^Update without previous sample$",
    ):
        r.update(success=success)


def test_adaptive_rand_in_range() -> None:
    for _ in range(1, 1000):
        lower = random.randint(0, 1000)  # noqa: S311
        upper = random.randint(lower, 1000)  # noqa: S311
        r = util.AdaptiveRange(lower=lower, upper=upper)
        sample = r.sample()
        assert lower <= sample <= upper


def test_adaptive_rand_uniform() -> None:
    r = util.AdaptiveRange(lower=0, upper=1000)
    data = [r.sample() for _ in range(1, 100000)]
    result = chisquare(f_obs=list(np.bincount(data)))
    assert result.pvalue > 0.05


def test_adaptive_rand_update() -> None:
    r = util.AdaptiveRange(lower=0, upper=10)
    for _ in range(100000):
        r.update(success=r.sample() > 5)
    data = [r.sample() for _ in range(1, 100000)]
    assert all(d > 5 for d in data)


def test_adaptive_choice_update() -> None:
    r = util.AdaptiveChoiceBase(population=["a", "b", "c"])
    for _ in range(100000):
        r.update(success=r.sample() != "a")
    data = [r.sample() for _ in range(1, 100000)]
    assert all(d != "a" for d in data)


def test_large_adaptive_range_uniform() -> None:
    r = util.AdaptiveLargeRange(0, 2**16 - 1)
    data = [r.sample() for _ in range(1, 10000)]
    result = chisquare(f_obs=list(np.bincount(data)))
    assert result.pvalue > 0.05


def test_large_adaptive_range_update() -> None:
    upper = 100
    r = util.AdaptiveLargeRange(1, upper)
    for _ in range(1, 100000):
        r.update(success=r.sample() < upper / 2)
    data = [r.sample() for _ in range(1, upper)]
    assert len([d for d in data if d < upper / 2]) / len(data) >= 2 / 3


def test_large_adaptive_range_preferred_value() -> None:
    r = util.AdaptiveLargeRange(1, 10)
    for _ in range(1, 100000):
        r.update(success=r.sample() == 5)
    assert len([d for d in [r.sample() for _ in range(1, 10000)] if d == 5]) > 5000

    for _ in range(1, 1000000):
        r.update(success=r.sample() != 5)
    assert len([d for d in [r.sample() for _ in range(1, 10000)] if d == 5]) < 2000

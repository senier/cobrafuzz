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


def test_rand_uniform() -> None:
    assert util.rand(0) == 0
    assert util.rand(1) == 0

    data = [util.rand(10) for _ in range(1, 1000000)]
    result = chisquare(f_obs=list(np.bincount(data)))
    assert result.pvalue > 0.05


def test_rand_exponential() -> None:
    expected = [round(200000 / 2 ** (n + 1)) for n in range(32)]
    data = list(
        np.bincount(
            [util.rand_exp() for _ in range(sum(expected))],
            minlength=32,
        ),
    )

    # There should be more than 13 samples in each bin,
    # c.f. https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chisquare.html
    # Starting at the position *before* the element that is <= 13, bin all remaining elements.
    data_valid_samples = [i for i, v in enumerate(data) if v < 13]
    assert len(data_valid_samples) > 0

    expected_valid_samples = [i for i, v in enumerate(expected) if v < 13]
    assert len(expected_valid_samples) > 0

    index = min(data_valid_samples[0], expected_valid_samples[0]) - 1
    data = data[:index] + [sum(data[index:])]
    expected = expected[:index] + [sum(expected[index:])]

    result = chisquare(f_obs=data, f_exp=expected)
    assert result.pvalue > 0.05, result


def test_choose_length() -> None:
    n = 1000
    lengths = [util.choose_len(n) for _ in range(10000)]

    assert n > 32
    assert len([v for v in lengths if v < 1]) == 0
    assert len([v for v in lengths if v > n]) == 0

    data = [
        len([v for v in lengths if 1 <= v <= 8]),
        len([v for v in lengths if 9 <= v <= 32]),
        len([v for v in lengths if 33 <= v <= n]),
    ]

    # Expected distribution for range 1..8, 9..32 and 33..n
    expected = [
        round((0.9 + 0.0225 + (8 / (100 * n))) * sum(data)),
        round((0.0675 + (24 / (100 * n))) * sum(data)),
        round(((n - 32) / (100 * n)) * sum(data)),
    ]

    result = chisquare(f_obs=data, f_exp=expected)
    assert result.pvalue > 0.05, result

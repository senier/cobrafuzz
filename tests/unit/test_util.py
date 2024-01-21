import pytest

from cobrafuzz import util


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

from __future__ import annotations

import secrets

import pytest

from cobrafuzz import mutator, util


def test_mutate(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as mp:
        mp.setattr(util, "rand_exp", lambda: 2)
        mp.setattr(util, "rand", lambda _: 5)
        mp.setattr(secrets, "token_bytes", lambda _: bytearray(b"inserted"))
        mp.setattr(
            secrets,
            "choice",
            lambda _: mutator._mutate_insert_range_of_bytes,  # noqa: SLF001
        )
        assert mutator.mutate(bytearray(b"0123456789")) == bytearray(b"01234insertedinserted56789")


def test_mutate_unmodified(monkeypatch: pytest.MonkeyPatch) -> None:
    def modify(res: bytearray, _: mutator.Config) -> bool:
        if res[0] != 0:
            res[0] = 0
            return False
        return True

    with monkeypatch.context() as mp:
        mp.setattr(util, "rand_exp", lambda: 2)
        mp.setattr(secrets, "choice", lambda _, _c=None: modify)
        assert mutator.mutate(bytearray(b"0123456789")) == bytearray(b"\x00123456789")


def test_mutate_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as mp:
        mp.setattr(util, "rand_exp", lambda: 1)
        mp.setattr(secrets, "choice", lambda _: lambda x, _: x)
        assert mutator.mutate(bytearray(b"0123456789"), max_input_size=4) == bytearray(b"0123")


def test_mutate_remove_range_of_bytes_fail() -> None:
    res = bytearray()
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_remove_range_of_bytes(res)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "start", "length", "expected"),
    [
        (b"0123456789", 0, 1, b"123456789"),
    ],
)
def test_mutate_remove_range_of_bytes_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    start: int,
    length: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:
        mp.setattr(util, "rand", lambda _: start)
        mp.setattr(util, "choose_len", lambda _: length)
        mutator._mutate_remove_range_of_bytes(tmp)  # noqa: SLF001
        assert tmp == expected


@pytest.mark.parametrize(
    ("data", "start", "length", "expected"),
    [
        (b"0123456789", 0, 5, b"XXXXX0123456789"),
        (b"0123456789", 10, 5, b"0123456789XXXXX"),
        (b"0123456789", 5, 5, b"01234XXXXX56789"),
    ],
)
def test_mutate_insert_range_of_bytes_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    start: int,
    length: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:
        mp.setattr(secrets, "token_bytes", lambda n: n * b"X")
        mp.setattr(util, "rand", lambda _: start)
        mp.setattr(util, "choose_len", lambda _: length)
        mutator._mutate_insert_range_of_bytes(  # noqa: SLF001
            tmp,
            mutator.Config(max_random_bytes=10),
        )
        assert tmp == expected


def test_mutate_duplicate_range_of_bytes_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_duplicate_range_of_bytes(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "start", "length", "dest", "expected"),
    [
        (b"0123456789", 0, 5, 10, b"012345678901234"),
        (b"0123456789", 0, 5, 0, b"012340123456789"),
        (b"0123456789", 0, 5, 5, b"012340123456789"),
        (b"0123456789", 4, 3, 10, b"0123456789456"),
        (b"0123456789", 4, 3, 0, b"4560123456789"),
        (b"0123456789", 4, 3, 5, b"0123445656789"),
    ],
)
def test_mutate_duplicate_range_of_bytes_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    start: int,
    length: int,
    dest: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:

        def rand(_: int) -> int:
            if not rand.second:  # type: ignore[attr-defined]
                rand.second = True  # type: ignore[attr-defined]
                return start
            rand.second = None  # type: ignore[attr-defined]
            return dest

        rand.second = None  # type: ignore[attr-defined]

        mp.setattr(util, "rand", rand)
        mp.setattr(util, "choose_len", lambda _: length)
        mutator._mutate_duplicate_range_of_bytes(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_copy_range_of_bytes_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_copy_range_of_bytes(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "start", "length", "dest", "expected"),
    [
        (b"0123456789", 0, 3, 5, b"0123401289"),
        (b"0123456789", 0, 1, 9, b"0123456780"),
        (b"0123456789", 4, 3, 0, b"4563456789"),
        (b"0123456789", 4, 3, 5, b"0123445689"),
        (b"0123456789", 4, 0, 5, b"0123456789"),
    ],
)
def test_mutate_copy_range_of_bytes_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    start: int,
    length: int,
    dest: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:

        def rand(_: int) -> int:
            if not rand.second:  # type: ignore[attr-defined]
                rand.second = True  # type: ignore[attr-defined]
                return start
            rand.second = None  # type: ignore[attr-defined]
            return dest

        rand.second = None  # type: ignore[attr-defined]

        mp.setattr(util, "rand", rand)
        mp.setattr(util, "choose_len", lambda _: length)
        mutator._mutate_copy_range_of_bytes(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_bit_flip_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_bit_flip(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "byte", "bit", "expected"),
    [
        (b"0123456789", 0, 0, b"1123456789"),
        (b"0123456789", 0, 4, b" 123456789"),
        (b"0123456789", 9, 0, b"0123456788"),
        (b"0123456789", 9, 6, b"012345678y"),
    ],
)
def test_mutate_bit_flip_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    byte: int,
    bit: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    # This would confuse our mocked _rand function below
    assert len(data) != 8, "data length must not be 8 in this test"

    with monkeypatch.context() as mp:
        mp.setattr(util, "rand", lambda n: bit if n == 8 else byte)
        mutator._mutate_bit_flip(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_flip_random_bits_of_random_byte_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_flip_random_bits_of_random_byte(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "byte", "value", "expected"),
    [
        (b"0123456789", 0, 124, b"M123456789"),
        (b"0123456789", 5, 117, b"01234C6789"),
        (b"0123456789", 9, 121, b"012345678C"),
    ],
)
def test_mutate_flip_random_bits_of_random_byte_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    byte: int,
    value: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    # This would confuse our mocked _rand function below
    assert len(data) != 255, "data length must not be 255 in this test"

    with monkeypatch.context() as mp:
        mp.setattr(util, "rand", lambda n: value if n == 255 else byte)
        mutator._mutate_flip_random_bits_of_random_byte(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_swap_two_bytes_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_swap_two_bytes(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "source", "dest", "expected"),
    [
        (b"0123456789", 0, 9, b"9123456780"),
        (b"0123456789", 9, 0, b"9123456780"),
        (b"0123456789", 0, 5, b"5123406789"),
        (b"0123456789", 5, 9, b"0123496785"),
        (b"0123456789", 0, 0, b"0123456789"),
        (b"0123456789", 5, 5, b"0123456789"),
        (b"0123456789", 9, 9, b"0123456789"),
    ],
)
def test_mutate_swap_two_bytes(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    source: int,
    dest: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:

        def rand(_: int) -> int:
            if not rand.second:  # type: ignore[attr-defined]
                rand.second = True  # type: ignore[attr-defined]
                return source
            rand.second = None  # type: ignore[attr-defined]
            return dest

        rand.second = None  # type: ignore[attr-defined]

        mp.setattr(util, "rand", rand)
        mutator._mutate_swap_two_bytes(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_add_subtract_from_a_byte_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_add_subtract_from_a_byte(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "position", "value", "expected"),
    [
        (b"0123456789", 0, 0, b"0123456789"),
        (b"0123456789", 0, 1, b"1123456789"),
        (b"0123456789", 0, 255, b"/123456789"),
        (b"0123456789", 5, 2, b"0123476789"),
        (b"0123456789", 5, 254, b"0123436789"),
        (b"0123456789", 9, 20, b"012345678M"),
        (b"0123456789", 9, 236, b"012345678%"),
    ],
)
def test_mutate_add_subtract_from_a_byte_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    position: int,
    value: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    # This would confuse our mocked _rand function below
    assert len(data) != 2**8, "data length must not be 2**8 in this test"

    with monkeypatch.context() as mp:
        mp.setattr(util, "rand", lambda n: value if n == 2**8 else position)
        mutator._mutate_add_subtract_from_a_byte(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_add_subtract_from_a_uint16_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_add_subtract_from_a_uint16(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "position", "value", "little_endian", "expected"),
    [
        (b"0123456789", 0, 0x0102, False, b"1323456789"),
        (b"0123456789", 0, 0x0102, True, b"2223456789"),
        (b"0123456789", 8, 0x0102, False, b"012345679;"),
        (b"0123456789", 8, 0x0102, True, b"01234567::"),
    ],
)
def test_mutate_add_subtract_from_a_uint16_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    position: int,
    value: int,
    little_endian: bool,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    # This would confuse our mocked _rand function below
    assert len(data) != 2**16, "data length must not be 2**16 in this test"

    with monkeypatch.context() as mp:
        mp.setattr(util, "rand", lambda n: value if n == 2**16 else position)
        mp.setattr(util, "rand_bool", lambda: not little_endian)
        mutator._mutate_add_subtract_from_a_uint16(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_add_subtract_from_a_uint32_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_add_subtract_from_a_uint32(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "position", "value", "little_endian", "expected"),
    [
        (b"0123456789", 0, 0x01020304, False, b"1357456789"),
        (b"0123456789", 0, 0x01020304, True, b"4444456789"),
        (b"0123456789", 6, 0x01020304, False, b"01234579;="),
        (b"0123456789", 6, 0x01020304, True, b"012345::::"),
    ],
)
def test_mutate_add_subtract_from_a_uint32_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    position: int,
    value: int,
    little_endian: bool,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    # This would confuse our mocked _rand function below
    assert len(data) != 2**32, "data length must not be 2**32 in this test"

    with monkeypatch.context() as mp:
        mp.setattr(util, "rand", lambda n: value if n == 2**32 else position)
        mp.setattr(util, "rand_bool", lambda: not little_endian)
        mutator._mutate_add_subtract_from_a_uint32(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_add_subtract_from_a_uint64_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_add_subtract_from_a_uint64(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "position", "value", "little_endian", "expected"),
    [
        (b"0123456789", 0, 0x0102030405060708, False, b"13579;=?89"),
        (b"0123456789", 0, 0x0102030405060708, True, b"8888888889"),
        (b"0123456789", 2, 0x0102030405060708, False, b"013579;=?A"),
        (b"0123456789", 2, 0x0102030405060708, True, b"01::::::::"),
    ],
)
def test_mutate_add_subtract_from_a_uint64_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    position: int,
    value: int,
    little_endian: bool,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    # This would confuse our mocked _rand function below
    assert len(data) != 2**64, "data length must not be 2**64 in this test"

    with monkeypatch.context() as mp:
        mp.setattr(util, "rand", lambda n: value if n == 2**64 else position)
        mp.setattr(util, "rand_bool", lambda: not little_endian)
        mutator._mutate_add_subtract_from_a_uint64(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_replace_a_byte_with_an_interesting_value_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_replace_a_byte_with_an_interesting_value(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "position", "value", "expected"),
    [
        (b"0123456789", 0, 1, b"\x01123456789"),
        (b"0123456789", 0, 255, b"\xff123456789"),
        (b"0123456789", 5, 2, b"01234\x026789"),
        (b"0123456789", 5, 254, b"01234\xfe6789"),
        (b"0123456789", 9, 3, b"012345678\x03"),
        (b"0123456789", 9, 253, b"012345678\xfd"),
    ],
)
def test_mutate_replace_a_byte_with_an_interesting_value_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    position: int,
    value: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:
        mp.setattr(util, "rand", lambda _: position)
        mp.setattr(mutator, "INTERESTING8", [value])
        mutator._mutate_replace_a_byte_with_an_interesting_value(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_replace_an_uint16_with_an_interesting_value_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_replace_an_uint16_with_an_interesting_value(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "position", "value", "little_endian", "expected"),
    [
        (b"0123456789", 0, 0x0102, False, b"\x01\x0223456789"),
        (b"0123456789", 0, 0x0102, True, b"\x02\x0123456789"),
        (b"0123456789", 5, 0x0102, False, b"01234\x01\x02789"),
        (b"0123456789", 5, 0x0102, True, b"01234\x02\x01789"),
        (b"0123456789", 8, 0x0102, False, b"01234567\x01\x02"),
        (b"0123456789", 8, 0x0102, True, b"01234567\x02\x01"),
    ],
)
def test_mutate_replace_an_uint16_with_an_interesting_value_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    position: int,
    value: int,
    little_endian: bool,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:
        mp.setattr(util, "rand", lambda _: position)
        mp.setattr(mutator, "INTERESTING16", [value])
        mp.setattr(util, "rand_bool", lambda: not little_endian)
        mutator._mutate_replace_an_uint16_with_an_interesting_value(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_replace_an_uint32_with_an_interesting_value_fail() -> None:
    data = bytearray(b"")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_replace_an_uint32_with_an_interesting_value(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "position", "value", "little_endian", "expected"),
    [
        (b"0123456789", 0, 0x01020304, False, b"\x01\x02\x03\x04456789"),
        (b"0123456789", 0, 0x01020304, True, b"\x04\x03\x02\x01456789"),
        (b"0123456789", 5, 0x01020304, False, b"01234\x01\x02\x03\x049"),
        (b"0123456789", 5, 0x01020304, True, b"01234\x04\x03\x02\x019"),
        (b"0123456789", 6, 0x01020304, False, b"012345\x01\x02\x03\x04"),
        (b"0123456789", 6, 0x01020304, True, b"012345\x04\x03\x02\x01"),
    ],
)
def test_mutate_replace_an_uint32_with_an_interesting_value_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    position: int,
    value: int,
    little_endian: bool,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:
        mp.setattr(util, "rand", lambda _: position)
        mp.setattr(mutator, "INTERESTING32", [value])
        mp.setattr(util, "rand_bool", lambda: not little_endian)
        mutator._mutate_replace_an_uint32_with_an_interesting_value(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_replace_an_ascii_digit_with_another_digit_fail() -> None:
    data = bytearray(b"no digits present")
    with pytest.raises(mutator.OutOfDataError):
        mutator._mutate_replace_an_ascii_digit_with_another_digit(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "position", "value", "expected"),
    [
        (b"0123456789", 0, 4, b"4123456789"),
        (b"0123456789", 0, 5, b"5123456789"),
        (b"0123456789", 5, 4, b"0123446789"),
        (b"0123456789", 9, 4, b"0123456784"),
        (b"0123456789", 9, 5, b"0123456785"),
    ],
)
def test_mutate_replace_an_ascii_digit_with_another_digit_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    position: int,
    value: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:
        mp.setattr(secrets, "choice", lambda d: (position, tmp[position]) if len(d) > 1 else d[0])
        mp.setattr(mutator, "DIGITS", {ord("0") + value})
        mutator._mutate_replace_an_ascii_digit_with_another_digit(tmp)  # noqa: SLF001
        assert tmp == expected

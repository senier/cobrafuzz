# ruff: noqa: SLF001

from __future__ import annotations

from typing import Optional

import pytest

from cobrafuzz import common, mutator, util


class StaticRand(util.AdaptiveRange):
    def __init__(self, value: int) -> None:
        super().__init__()
        self._value = value

    def sample(self, _lower: int, _upper: int) -> int:
        return self._value


class Param(util.Param):
    def __init__(self, value: int):
        self.success: Optional[bool] = None
        super().__init__(value)

    def update(self, success: bool = False) -> None:
        self.success = success


class StaticIntChoice(util.AdaptiveChoiceBase[int]):
    def __init__(self, value: int) -> None:
        super().__init__(population=[value])
        self._value = value

    def sample(self) -> int:
        return self._value


def test_mutate(monkeypatch: pytest.MonkeyPatch) -> None:
    def modify(data: bytearray, _m: mutator.Params, _i: util.AdaptiveChoiceBase[bytearray]) -> None:
        data.insert(0, ord("a"))
        data.append(ord("b"))

    m = mutator.Mutator()
    with monkeypatch.context() as mp:
        mp.setattr(m, "_mutators", util.AdaptiveChoiceBase([(modify, None)]))
        mp.setattr(m, "_modifications", StaticRand(1))
        assert m._mutate(bytearray(b"0123456789")) == bytearray(b"a0123456789b")


def test_mutate_unmodified(monkeypatch: pytest.MonkeyPatch) -> None:
    m = mutator.Mutator()

    def modify(data: bytearray, _m: mutator.Params, _i: util.AdaptiveChoiceBase[bytearray]) -> None:
        if data[0] != 0:
            data[0] = 0

    with monkeypatch.context() as mp:
        mp.setattr(m, "_mutators", util.AdaptiveChoiceBase([(modify, None)]))
        assert m._mutate(bytearray(b"0123456789")) == bytearray(b"\x00123456789")
        assert m._mutate(bytearray(b"\x00123456789")) == bytearray(b"\x00123456789")


def test_mutate_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    m = mutator.Mutator(max_input_size=4)
    with monkeypatch.context() as mp:
        mp.setattr(
            m,
            "_mutators",
            util.AdaptiveChoiceBase([(lambda _data, _m, _i: (None, None, None), None)]),
        )
        assert m._mutate(bytearray(b"0123456789")) == bytearray(b"0123")


def test_mutate_remove_range_of_bytes_fail() -> None:
    res = bytearray()
    with pytest.raises(common.OutOfDataError):
        mutator._mutate_remove_range_of_bytes(res, mutator.Params())


@pytest.mark.parametrize(
    ("data", "start", "length", "expected"),
    [
        (b"0123456789", 0, 1, b"123456789"),
        (b"0123456789", 5, 2, b"01234789"),
        (b"0123456789", 7, 3, b"0123456"),
    ],
)
def test_mutate_remove_range_of_bytes_success(
    data: bytes,
    start: int,
    length: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_remove_range_of_bytes(
        tmp,
        mutator.Params(
            start=StaticRand(start),
            length=StaticRand(length),
        ),
    )
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
    data: bytes,
    start: int,
    length: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_insert_range_of_bytes(
        tmp,
        mutator.Params(
            start=StaticRand(start),
            length=StaticRand(length),
            data=StaticRand(ord("X")),
            max_length=util.Param(2),
        ),
    )
    assert tmp == expected


def test_mutate_duplicate_range_of_bytes_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_duplicate_range_of_bytes(data, mutator.Params())


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
    data: bytes,
    start: int,
    length: int,
    dest: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_duplicate_range_of_bytes(
        tmp,
        mutator.Params(
            src_pos=StaticRand(start),
            dst_pos=StaticRand(dest),
            length=StaticRand(length),
        ),
    )
    assert tmp == expected


def test_mutate_copy_range_of_bytes_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_copy_range_of_bytes(data, mutator.Params())


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
    data: bytes,
    start: int,
    length: int,
    dest: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_copy_range_of_bytes(
        tmp,
        mutator.Params(
            src_pos=StaticRand(start),
            dst_pos=StaticRand(dest),
            length=StaticRand(length),
        ),
    )
    assert tmp == expected


def test_mutate_bit_flip_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_bit_flip(data, mutator.Params())


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
    data: bytes,
    byte: int,
    bit: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_bit_flip(
        tmp,
        mutator.Params(
            bit_pos=StaticRand(bit),
            byte_pos=StaticRand(byte),
        ),
    )
    assert tmp == expected


def test_mutate_flip_random_bits_of_random_byte_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_flip_random_bits_of_random_byte(data, mutator.Params())


@pytest.mark.parametrize(
    ("data", "byte", "value", "expected"),
    [
        (b"0123456789", 0, 124, b"L123456789"),
        (b"0123456789", 5, 117, b"01234@6789"),
        (b"0123456789", 9, 121, b"012345678@"),
    ],
)
def test_mutate_flip_random_bits_of_random_byte_success(
    data: bytes,
    byte: int,
    value: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_flip_random_bits_of_random_byte(
        tmp,
        mutator.Params(
            pos=StaticRand(byte),
            value=StaticRand(value),
        ),
    )
    assert tmp == expected


def test_mutate_swap_two_bytes_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_swap_two_bytes(data, mutator.Params())


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
    data: bytes,
    source: int,
    dest: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_swap_two_bytes(
        tmp,
        mutator.Params(
            first_pos=StaticRand(source),
            second_pos=StaticRand(dest),
        ),
    )
    assert tmp == expected


def test_mutate_add_subtract_from_a_byte_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_add_subtract_from_a_byte(data, mutator.Params())


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
    data: bytes,
    position: int,
    value: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_add_subtract_from_a_byte(
        tmp,
        mutator.Params(
            value=StaticRand(value),
            pos=StaticRand(position),
        ),
    )
    assert tmp == expected


def test_mutate_add_subtract_from_a_uint16_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_add_subtract_from_a_uint16(data, mutator.Params())


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
    data: bytes,
    position: int,
    value: int,
    little_endian: bool,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_add_subtract_from_a_uint16(
        tmp,
        mutator.Params(
            value=StaticRand(value),
            pos=StaticRand(position),
            big_endian=StaticRand(0 if little_endian else 1),
        ),
    )
    assert tmp == expected


def test_mutate_add_subtract_from_a_uint32_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_add_subtract_from_a_uint32(data, mutator.Params())


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
    data: bytes,
    position: int,
    value: int,
    little_endian: bool,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_add_subtract_from_a_uint32(
        tmp,
        mutator.Params(
            value=StaticRand(value),
            pos=StaticRand(position),
            big_endian=StaticRand(0 if little_endian else 1),
        ),
    )
    assert tmp == expected


def test_mutate_add_subtract_from_a_uint64_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_add_subtract_from_a_uint64(data, mutator.Params())


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
    data: bytes,
    position: int,
    value: int,
    little_endian: bool,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_add_subtract_from_a_uint64(
        tmp,
        mutator.Params(
            value=StaticRand(value),
            pos=StaticRand(position),
            big_endian=StaticRand(0 if little_endian else 1),
        ),
    )
    assert tmp == expected


def test_mutate_replace_a_byte_with_an_interesting_value_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_replace_a_byte_with_an_interesting_value(
            data,
            mutator.Params(),
        )


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
    data: bytes,
    position: int,
    value: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_replace_a_byte_with_an_interesting_value(
        tmp,
        mutator.Params(
            interesting_8=StaticIntChoice(value),
            pos=StaticRand(position),
        ),
    )
    assert tmp == expected


def test_mutate_replace_an_uint16_with_an_interesting_value_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_replace_an_uint16_with_an_interesting_value(
            data,
            mutator.Params(),
        )


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
    data: bytes,
    position: int,
    value: int,
    little_endian: bool,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_replace_an_uint16_with_an_interesting_value(
        tmp,
        mutator.Params(
            interesting_16=StaticIntChoice(value),
            pos=StaticRand(position),
            big_endian=StaticRand(0 if little_endian else 1),
        ),
    )
    assert tmp == expected


def test_mutate_replace_an_uint32_with_an_interesting_value_fail() -> None:
    data = bytearray(b"")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_replace_an_uint32_with_an_interesting_value(
            data,
            mutator.Params(),
        )


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
    data: bytes,
    position: int,
    value: int,
    little_endian: bool,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_replace_an_uint32_with_an_interesting_value(
        tmp,
        mutator.Params(
            interesting_32=StaticIntChoice(value),
            pos=StaticRand(position),
            big_endian=StaticRand(0 if little_endian else 1),
        ),
    )
    assert tmp == expected


def test_mutate_replace_an_ascii_digit_with_another_digit_fail() -> None:
    data = bytearray(b"no digits present")

    with pytest.raises(common.OutOfDataError):
        mutator._mutate_replace_an_ascii_digit_with_another_digit(
            data,
            mutator.Params(),
        )


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
    data: bytes,
    position: int,
    value: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    mutator._mutate_replace_an_ascii_digit_with_another_digit(
        tmp,
        mutator.Params(
            pos=StaticRand(position),
            digits=StaticIntChoice(ord("0") + value),
        ),
    )
    assert tmp == expected


def test_mutate_splice_fail_left() -> None:
    res = bytearray()
    with pytest.raises(common.OutOfDataError):
        mutator._mutate_splice(res, mutator.Params())


def test_mutate_splice_fail_right() -> None:
    res = bytearray(b"deadbeef")
    with pytest.raises(common.OutOfDataError):
        mutator._mutate_splice(
            res,
            mutator.Params(),
            util.AdaptiveChoiceBase(population=[bytearray()]),
        )


@pytest.mark.parametrize(
    ("left", "left_pos", "right", "right_pos", "expected"),
    [
        (b"0123456789", 9, b"ABCDEFGHIJ", 0, b"0123456789ABCDEFGHIJ"),
        (b"0123456789", 5, b"ABCDEFGHIJ", 5, b"012345FGHIJ"),
        (b"0123456789", 0, b"ABCDEFGHIJ", 9, b"0J"),
    ],
)
def test_mutate_splice(
    left: bytes,
    left_pos: int,
    right: bytes,
    right_pos: int,
    expected: bytes,
) -> None:
    tmp = bytearray(left)

    mutator._mutate_splice(
        tmp,
        mutator.Params(
            left_pos=StaticRand(left_pos),
            right_pos=StaticRand(right_pos),
        ),
        util.AdaptiveChoiceBase(population=[bytearray(right)]),
    )
    assert tmp == bytearray(expected)


def test_params_invalid() -> None:
    p = mutator.Params()
    with pytest.raises(AttributeError, match="^'Params' object has no attribute '_invalid'$"):
        _x = p._invalid


def test_params_update() -> None:
    p1 = Param(1)
    p2 = Param(2)
    p = mutator.Params(p1=p1, p2=p2)

    assert p1.success is None
    assert p2.success is None

    p.update(success=True)
    assert p1.success
    assert p2.success  # type: ignore[unreachable]

    p.update(success=False)
    assert not p1.success
    assert not p2.success


def test_mutator_detect_out_of_data_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fail = True

    def raise_out_of_data(
        _res: bytearray,
        _params: mutator.Params,
        _i: util.AdaptiveChoiceBase[bytearray],
    ) -> None:
        nonlocal fail
        if fail:
            fail = False
            raise common.OutOfDataError

    with monkeypatch.context() as mp:
        m = mutator.Mutator()
        mp.setattr(
            m,
            "_mutators",
            util.AdaptiveChoiceBase(
                population=[(raise_out_of_data, mutator.Params())],
            ),
        )
        mp.setattr(m, "_modifications", StaticRand(2))
        m._mutate(bytearray(b"deadbeef"))


def test_mutator_update(monkeypatch: pytest.MonkeyPatch) -> None:
    def mutate_noop(
        _res: bytearray,
        _params: mutator.Params,
        _i: util.AdaptiveChoiceBase[bytearray],
    ) -> None:
        pass

    with monkeypatch.context() as mp:
        p1 = Param(1)
        m = mutator.Mutator()
        mp.setattr(
            m,
            "_mutators",
            util.AdaptiveChoiceBase(
                population=[(mutate_noop, mutator.Params(p1=p1))],
            ),
        )
        mp.setattr(m, "_modifications", StaticRand(1))
        m._mutate(bytearray(b"deadbeef"))

        assert p1.success is None
        m.update(success=True)
        assert p1.success

    with monkeypatch.context() as mp:  # type: ignore[unreachable]
        m = mutator.Mutator()
        m.update(success=True)

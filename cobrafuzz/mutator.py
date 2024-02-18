from __future__ import annotations

import struct
from typing import Callable, Optional

from . import util


class OutOfDataError(Exception):
    pass


class Rands:
    def __init__(self, **kwargs: util.AdaptiveRandBase[int]):
        self._data: dict[str, util.AdaptiveRandBase[int]] = kwargs

    def __getattr__(self, attr: str) -> util.AdaptiveRandBase[int]:
        if attr.startswith("_") or attr not in self._data:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")
        return self._data[attr]


def _mutate_remove_range_of_bytes(res: bytearray, rand: Rands) -> None:
    if len(res) < 2:
        raise OutOfDataError
    assert isinstance(rand.length, util.AdaptiveRange)
    assert isinstance(rand.start, util.AdaptiveRange)
    length = rand.length.sample_max(len(res))
    util.remove(data=res, start=rand.start.sample_max(len(res) - length), length=length)


def _mutate_insert_range_of_bytes(res: bytearray, rand: Rands) -> None:
    assert isinstance(rand.length, util.AdaptiveRange)
    assert isinstance(rand.start, util.AdaptiveRange)
    assert isinstance(rand.data, util.AdaptiveRange)
    data = bytes(rand.data.sample() for _ in range(rand.length.sample()))
    util.insert(data=res, start=rand.start.sample_max(len(res) + 1), data_to_insert=data)


def _mutate_duplicate_range_of_bytes(res: bytearray, rand: Rands) -> None:
    if len(res) < 2:
        raise OutOfDataError
    assert isinstance(rand.src_pos, util.AdaptiveRange)
    assert isinstance(rand.dst_pos, util.AdaptiveRange)
    assert isinstance(rand.length, util.AdaptiveRange)
    dst_pos = rand.dst_pos.sample_max(len(res))
    src_pos = rand.src_pos.sample_max(dst_pos)
    length = rand.length.sample_max(len(res) - src_pos)
    util.insert(res, dst_pos, res[src_pos : src_pos + length])


def _mutate_copy_range_of_bytes(res: bytearray, rand: Rands) -> None:
    if len(res) < 2:
        raise OutOfDataError
    assert isinstance(rand.src_pos, util.AdaptiveRange)
    assert isinstance(rand.dst_pos, util.AdaptiveRange)
    assert isinstance(rand.length, util.AdaptiveRange)
    dst_pos = rand.dst_pos.sample_max(len(res))
    src_pos = rand.src_pos.sample_max(dst_pos)
    length = rand.length.sample_max(min(len(res) - src_pos, len(res) - dst_pos))
    util.copy(res, src_pos, dst_pos, length)


def _mutate_bit_flip(res: bytearray, rand: Rands) -> None:
    if len(res) < 1:
        raise OutOfDataError
    assert isinstance(rand.byte_pos, util.AdaptiveRange)
    assert isinstance(rand.bit_pos, util.AdaptiveRange)
    byte_pos = rand.byte_pos.sample_max(len(res))
    bit_pos = rand.bit_pos.sample()
    res[byte_pos] ^= 1 << bit_pos


def _mutate_flip_random_bits_of_random_byte(res: bytearray, rand: Rands) -> None:
    if len(res) < 1:
        raise OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.value, util.AdaptiveRange)
    pos = rand.pos.sample_max(len(res))
    res[pos] ^= rand.value.sample()


def _mutate_swap_two_bytes(res: bytearray, rand: Rands) -> None:
    if len(res) < 2:
        raise OutOfDataError
    assert isinstance(rand.first_pos, util.AdaptiveRange)
    assert isinstance(rand.second_pos, util.AdaptiveRange)
    first_pos = rand.first_pos.sample_max(len(res))
    second_pos = rand.second_pos.sample_max(len(res))
    res[first_pos], res[second_pos] = res[second_pos], res[first_pos]


def _mutate_add_subtract_from_a_byte(res: bytearray, rand: Rands) -> None:
    if len(res) < 1:
        raise OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.value, util.AdaptiveRange)
    pos = rand.pos.sample_max(len(res))
    v_int = rand.value.sample()
    res[pos] = (res[pos] + v_int) % 256


def _mutate_add_subtract_from_a_uint16(res: bytearray, rand: Rands) -> None:
    if len(res) < 2:
        raise OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    pos = rand.pos.sample_max(len(res) - 1)
    v_int = rand.value.sample()
    v = struct.pack(">H", v_int) if rand.big_endian.sample() else struct.pack("<H", v_int)
    # TODO(#18): Implement version performing 16-bit addition
    res[pos] = (res[pos] + v[0]) % 256
    res[pos + 1] = (res[pos + 1] + v[1]) % 256


def _mutate_add_subtract_from_a_uint32(res: bytearray, rand: Rands) -> None:
    if len(res) < 4:
        raise OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    pos = rand.pos.sample_max(len(res) - 3)
    v_int = rand.value.sample()
    v = struct.pack(">I", v_int) if rand.big_endian.sample() else struct.pack("<I", v_int)
    res[pos] = (res[pos] + v[0]) % 256
    res[pos + 1] = (res[pos + 1] + v[1]) % 256
    res[pos + 2] = (res[pos + 2] + v[2]) % 256
    res[pos + 3] = (res[pos + 3] + v[3]) % 256


def _mutate_add_subtract_from_a_uint64(res: bytearray, rand: Rands) -> None:
    if len(res) < 8:
        raise OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    pos = rand.pos.sample_max(len(res) - 7)
    v_int = rand.value.sample()
    v = struct.pack(">Q", v_int) if rand.big_endian.sample() else struct.pack("<Q", v_int)
    res[pos] = (res[pos] + v[0]) % 256
    res[pos + 1] = (res[pos + 1] + v[1]) % 256
    res[pos + 2] = (res[pos + 2] + v[2]) % 256
    res[pos + 3] = (res[pos + 3] + v[3]) % 256
    res[pos + 4] = (res[pos + 4] + v[4]) % 256
    res[pos + 5] = (res[pos + 5] + v[5]) % 256
    res[pos + 6] = (res[pos + 6] + v[6]) % 256
    res[pos + 7] = (res[pos + 7] + v[7]) % 256


def _mutate_replace_a_byte_with_an_interesting_value(res: bytearray, rand: Rands) -> None:
    if len(res) < 1:
        raise OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    pos = rand.pos.sample_max(len(res))
    res[pos] = rand.interesting_8.sample()


def _mutate_replace_an_uint16_with_an_interesting_value(res: bytearray, rand: Rands) -> None:
    if len(res) < 2:
        raise OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    pos = rand.pos.sample_max(len(res) - 1)
    v_int = rand.interesting_16.sample()
    v = struct.pack(">H", v_int) if rand.big_endian.sample() else struct.pack("<H", v_int)
    res[pos] = v[0] % 256
    res[pos + 1] = v[1] % 256


def _mutate_replace_an_uint32_with_an_interesting_value(res: bytearray, rand: Rands) -> None:
    if len(res) < 4:
        raise OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    pos = rand.pos.sample_max(len(res) - 3)
    v_int = rand.interesting_32.sample()
    v = struct.pack(">I", v_int) if rand.big_endian.sample() else struct.pack("<I", v_int)
    res[pos] = v[0] % 256
    res[pos + 1] = v[1] % 256
    res[pos + 2] = v[2] % 256
    res[pos + 3] = v[3] % 256


def _mutate_replace_an_ascii_digit_with_another_digit(res: bytearray, rand: Rands) -> None:
    digits_present = [i for i in range(len(res)) if ord("0") <= res[i] <= ord("9")]
    if len(digits_present) < 1:
        raise OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    pos = rand.pos.sample_max(len(res))
    res[pos] = rand.digits.sample()


class Mutator:
    def __init__(self, max_input_size: int = 1024, max_modifications: int = 10):
        self._max_input_size = max_input_size
        self._modifications = util.AdaptiveRange(1, max_modifications)
        self._mutators: util.AdaptiveChoiceBase[
            tuple[Callable[[bytearray, Rands], None], Rands]
        ] = util.AdaptiveChoiceBase(
            population=[
                (
                    _mutate_remove_range_of_bytes,
                    Rands(
                        length=util.AdaptiveRange(1, max_input_size),
                        start=util.AdaptiveRange(0, max_input_size),
                    ),
                ),
                (
                    _mutate_insert_range_of_bytes,
                    Rands(
                        length=util.AdaptiveRange(1, 10),
                        start=util.AdaptiveRange(0, max_input_size),
                        data=util.AdaptiveRange(0, 255),
                    ),
                ),
                (
                    _mutate_duplicate_range_of_bytes,
                    Rands(
                        src_pos=util.AdaptiveRange(0, max_input_size),
                        dst_pos=util.AdaptiveRange(1, max_input_size),
                        length=util.AdaptiveRange(1, max_input_size),
                    ),
                ),
                (
                    _mutate_copy_range_of_bytes,
                    Rands(
                        src_pos=util.AdaptiveRange(0, max_input_size),
                        dst_pos=util.AdaptiveRange(1, max_input_size),
                        length=util.AdaptiveRange(1, max_input_size),
                    ),
                ),
                (
                    _mutate_bit_flip,
                    Rands(
                        byte_pos=util.AdaptiveRange(0, max_input_size),
                        bit_pos=util.AdaptiveRange(0, 7),
                    ),
                ),
                (
                    _mutate_flip_random_bits_of_random_byte,
                    Rands(
                        pos=util.AdaptiveRange(0, max_input_size),
                        value=util.AdaptiveRange(0, 255),
                    ),
                ),
                (
                    _mutate_swap_two_bytes,
                    Rands(
                        first_pos=util.AdaptiveRange(0, max_input_size),
                        second_pos=util.AdaptiveRange(0, max_input_size),
                    ),
                ),
                (
                    _mutate_add_subtract_from_a_byte,
                    Rands(
                        pos=util.AdaptiveRange(0, max_input_size),
                        value=util.AdaptiveRange(0, 255),
                    ),
                ),
                (
                    _mutate_add_subtract_from_a_uint16,
                    Rands(
                        pos=util.AdaptiveRange(0, max_input_size),
                        value=util.AdaptiveLargeRange(0, 2**16 - 1),
                        big_endian=util.AdaptiveRange(0, 1),
                    ),
                ),
                (
                    _mutate_add_subtract_from_a_uint32,
                    Rands(
                        pos=util.AdaptiveRange(0, max_input_size),
                        value=util.AdaptiveLargeRange(0, 2**32 - 1),
                        big_endian=util.AdaptiveRange(0, 1),
                    ),
                ),
                (
                    _mutate_add_subtract_from_a_uint64,
                    Rands(
                        pos=util.AdaptiveRange(0, max_input_size),
                        value=util.AdaptiveLargeRange(0, 2**64 - 1),
                        big_endian=util.AdaptiveRange(0, 1),
                    ),
                ),
                (
                    _mutate_replace_a_byte_with_an_interesting_value,
                    Rands(
                        pos=util.AdaptiveRange(0, max_input_size),
                        interesting_8=util.AdaptiveIntChoice(
                            population=[1, 1, 16, 32, 64, 100, 127, 128, 129, 255],
                        ),
                    ),
                ),
                (
                    _mutate_replace_an_uint16_with_an_interesting_value,
                    Rands(
                        pos=util.AdaptiveRange(0, max_input_size),
                        interesting_16=util.AdaptiveIntChoice(
                            population=[0, 128, 255, 256, 512, 1000, 1024, 4096, 32767, 65535],
                        ),
                        big_endian=util.AdaptiveRange(0, 1),
                    ),
                ),
                (
                    _mutate_replace_an_uint32_with_an_interesting_value,
                    Rands(
                        pos=util.AdaptiveRange(0, max_input_size),
                        interesting_32=util.AdaptiveIntChoice(
                            population=[
                                0,
                                1,
                                32768,
                                65535,
                                65536,
                                100663045,
                                2147483647,
                                4294967295,
                            ],
                        ),
                        big_endian=util.AdaptiveRange(0, 1),
                    ),
                ),
                (
                    _mutate_replace_an_ascii_digit_with_another_digit,
                    Rands(
                        pos=util.AdaptiveRange(0, max_input_size),
                        digits=util.AdaptiveIntChoice(
                            population=[
                                ord(i) for i in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")
                            ],
                        ),
                    ),
                ),
            ],
        )
        self._last_modify: Optional[Callable[[bytearray, Rands], None]] = None
        self._last_rands: Optional[Rands] = None

    def mutate(self, buf: bytearray) -> bytearray:
        res = buf[:]
        nm = self._modifications.sample()
        while nm:
            self._last_modify, self._last_rands = self._mutators.sample()
            try:
                self._last_modify(res, self._last_rands)
            except OutOfDataError:
                pass
            else:
                nm -= 1

        if self._max_input_size and len(res) > self._max_input_size:
            res = res[: self._max_input_size]
        return res

from __future__ import annotations

import ast
import struct
from typing import Callable, Optional

from . import common, util


class Params:
    def __init__(self, **kwargs: util.ParamBase[int]):
        self._data: dict[str, util.ParamBase[int]] = kwargs

    def __getattr__(self, attr: str) -> util.ParamBase[int]:
        if attr.startswith("_") or attr not in self._data:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")
        return self._data[attr]

    def update(self, success: bool = False) -> None:
        for rand in self._data.values():
            rand.update(success=success)


def _mutate_remove_range_of_bytes(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 2:
        raise common.OutOfDataError
    assert isinstance(rand.length, util.AdaptiveRange)
    assert isinstance(rand.start, util.AdaptiveRange)
    length = rand.length.sample(1, len(res))
    util.remove(data=res, start=rand.start.sample(0, len(res) - length), length=length)


def _mutate_insert_range_of_bytes(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    assert isinstance(rand.length, util.AdaptiveRange)
    assert isinstance(rand.start, util.AdaptiveRange)
    assert isinstance(rand.data, util.AdaptiveRange)
    assert isinstance(rand.max_length, util.Param)
    data = bytes(rand.data.sample(0, 255) for _ in range(rand.length.sample(1, rand.max_length())))
    util.insert(data=res, start=rand.start.sample(0, len(res)), data_to_insert=data)


def _mutate_duplicate_range_of_bytes(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 2:
        raise common.OutOfDataError
    assert isinstance(rand.src_pos, util.AdaptiveRange)
    assert isinstance(rand.dst_pos, util.AdaptiveRange)
    assert isinstance(rand.length, util.AdaptiveRange)
    dst_pos = rand.dst_pos.sample(1, len(res) - 1)
    src_pos = rand.src_pos.sample(0, dst_pos)
    length = rand.length.sample(1, len(res) - src_pos)
    util.insert(res, dst_pos, res[src_pos : src_pos + length])


def _mutate_copy_range_of_bytes(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 2:
        raise common.OutOfDataError
    assert isinstance(rand.src_pos, util.AdaptiveRange)
    assert isinstance(rand.dst_pos, util.AdaptiveRange)
    assert isinstance(rand.length, util.AdaptiveRange)
    dst_pos = rand.dst_pos.sample(1, len(res) - 1)
    src_pos = rand.src_pos.sample(0, dst_pos)
    length = rand.length.sample(1, min(len(res) - src_pos, len(res) - dst_pos))
    util.copy(res, src_pos, dst_pos, length)


def _mutate_bit_flip(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 1:
        raise common.OutOfDataError
    assert isinstance(rand.byte_pos, util.AdaptiveRange)
    assert isinstance(rand.bit_pos, util.AdaptiveRange)
    byte_pos = rand.byte_pos.sample(0, len(res) - 1)
    bit_pos = rand.bit_pos.sample(0, 7)
    res[byte_pos] ^= 1 << bit_pos


def _mutate_flip_random_bits_of_random_byte(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 1:
        raise common.OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.value, util.AdaptiveRange)
    pos = rand.pos.sample(0, len(res) - 1)
    res[pos] ^= rand.value.sample(0, 255)


def _mutate_swap_two_bytes(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 2:
        raise common.OutOfDataError
    assert isinstance(rand.first_pos, util.AdaptiveRange)
    assert isinstance(rand.second_pos, util.AdaptiveRange)
    first_pos = rand.first_pos.sample(0, len(res) - 1)
    second_pos = rand.second_pos.sample(0, len(res) - 1)
    res[first_pos], res[second_pos] = res[second_pos], res[first_pos]


def _mutate_add_subtract_from_a_byte(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 1:
        raise common.OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.value, util.AdaptiveRange)
    pos = rand.pos.sample(0, len(res) - 1)
    v_int = rand.value.sample(0, 255)
    res[pos] = (res[pos] + v_int) % 256


def _mutate_add_subtract_from_a_uint16(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 2:
        raise common.OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.value, util.AdaptiveRange)
    assert isinstance(rand.big_endian, util.AdaptiveRange)
    pos = rand.pos.sample(0, len(res) - 2)
    v_int = rand.value.sample(0, 2**16 - 1)
    v = struct.pack(">H", v_int) if rand.big_endian.sample(0, 1) else struct.pack("<H", v_int)
    # TODO(#18): Implement version performing 16-bit addition
    res[pos] = (res[pos] + v[0]) % 256
    res[pos + 1] = (res[pos + 1] + v[1]) % 256


def _mutate_add_subtract_from_a_uint32(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 4:
        raise common.OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.value, util.AdaptiveRange)
    assert isinstance(rand.big_endian, util.AdaptiveRange)
    pos = rand.pos.sample(0, len(res) - 4)
    v_int = rand.value.sample(0, 2**32 - 1)
    v = struct.pack(">I", v_int) if rand.big_endian.sample(0, 1) else struct.pack("<I", v_int)
    res[pos] = (res[pos] + v[0]) % 256
    res[pos + 1] = (res[pos + 1] + v[1]) % 256
    res[pos + 2] = (res[pos + 2] + v[2]) % 256
    res[pos + 3] = (res[pos + 3] + v[3]) % 256


def _mutate_add_subtract_from_a_uint64(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 8:
        raise common.OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.value, util.AdaptiveRange)
    assert isinstance(rand.big_endian, util.AdaptiveRange)
    pos = rand.pos.sample(0, len(res) - 8)
    v_int = rand.value.sample(0, 2**64 - 1)
    v = struct.pack(">Q", v_int) if rand.big_endian.sample(0, 1) else struct.pack("<Q", v_int)
    res[pos] = (res[pos] + v[0]) % 256
    res[pos + 1] = (res[pos + 1] + v[1]) % 256
    res[pos + 2] = (res[pos + 2] + v[2]) % 256
    res[pos + 3] = (res[pos + 3] + v[3]) % 256
    res[pos + 4] = (res[pos + 4] + v[4]) % 256
    res[pos + 5] = (res[pos + 5] + v[5]) % 256
    res[pos + 6] = (res[pos + 6] + v[6]) % 256
    res[pos + 7] = (res[pos + 7] + v[7]) % 256


def _mutate_replace_a_byte_with_an_interesting_value(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 1:
        raise common.OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.interesting_8, util.AdaptiveChoiceBase)
    pos = rand.pos.sample(0, len(res) - 1)
    res[pos] = rand.interesting_8.sample()


def _mutate_replace_an_uint16_with_an_interesting_value(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 2:
        raise common.OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.big_endian, util.AdaptiveRange)
    assert isinstance(rand.interesting_16, util.AdaptiveChoiceBase)
    pos = rand.pos.sample(0, len(res) - 2)
    v_int = rand.interesting_16.sample()
    v = struct.pack(">H", v_int) if rand.big_endian.sample(0, 1) else struct.pack("<H", v_int)
    res[pos] = v[0] % 256
    res[pos + 1] = v[1] % 256


def _mutate_replace_an_uint32_with_an_interesting_value(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 4:
        raise common.OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.big_endian, util.AdaptiveRange)
    assert isinstance(rand.interesting_32, util.AdaptiveChoiceBase)
    pos = rand.pos.sample(0, len(res) - 4)
    v_int = rand.interesting_32.sample()
    v = struct.pack(">I", v_int) if rand.big_endian.sample(0, 1) else struct.pack("<I", v_int)
    res[pos] = v[0] % 256
    res[pos + 1] = v[1] % 256
    res[pos + 2] = v[2] % 256
    res[pos + 3] = v[3] % 256


def _mutate_replace_an_ascii_digit_with_another_digit(
    res: bytearray,
    rand: Params,
    _inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    digits_present = [i for i in range(len(res)) if ord("0") <= res[i] <= ord("9")]
    if len(digits_present) < 1:
        raise common.OutOfDataError
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.digits, util.AdaptiveChoiceBase)
    pos = rand.pos.sample(0, len(res) - 1)
    res[pos] = rand.digits.sample()


def _mutate_splice(
    res: bytearray,
    rand: Params,
    inputs: Optional[util.AdaptiveChoiceBase[bytearray]] = None,
) -> None:
    if len(res) < 1:
        raise common.OutOfDataError
    assert inputs is not None
    right = inputs.sample()
    if len(right) < 1:
        raise common.OutOfDataError
    assert isinstance(rand.left_pos, util.AdaptiveRange)
    assert isinstance(rand.right_pos, util.AdaptiveRange)
    res[rand.left_pos.sample(0, len(res) - 1) + 1 :] = right[
        rand.right_pos.sample(0, len(right) - 1) :
    ]


class Mutator:
    def __init__(
        self,
        max_input_size: int = 1024,
        max_modifications: int = 10,
        max_insert_length: int = 10,
        adaptive: bool = True,
    ):
        self._inputs: util.AdaptiveChoiceBase[bytearray] = util.AdaptiveChoiceBase(population=None)
        self._max_input_size = max_input_size
        self._max_modifications = max_modifications
        self._modifications = util.AdaptiveRange(adaptive=adaptive)
        self._mutators: util.AdaptiveChoiceBase[
            tuple[Callable[[bytearray, Params, util.AdaptiveChoiceBase[bytearray]], None], Params]
        ] = util.AdaptiveChoiceBase(
            population=[
                (
                    _mutate_remove_range_of_bytes,
                    Params(
                        length=util.AdaptiveRange(adaptive=adaptive),
                        start=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_insert_range_of_bytes,
                    Params(
                        length=util.AdaptiveRange(adaptive=adaptive),
                        start=util.AdaptiveRange(adaptive=adaptive),
                        data=util.AdaptiveRange(adaptive=adaptive),
                        max_length=util.Param(max_insert_length),
                    ),
                ),
                (
                    _mutate_duplicate_range_of_bytes,
                    Params(
                        src_pos=util.AdaptiveRange(adaptive=adaptive),
                        dst_pos=util.AdaptiveRange(adaptive=adaptive),
                        length=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_copy_range_of_bytes,
                    Params(
                        src_pos=util.AdaptiveRange(adaptive=adaptive),
                        dst_pos=util.AdaptiveRange(adaptive=adaptive),
                        length=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_bit_flip,
                    Params(
                        byte_pos=util.AdaptiveRange(adaptive=adaptive),
                        bit_pos=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_flip_random_bits_of_random_byte,
                    Params(
                        pos=util.AdaptiveRange(adaptive=adaptive),
                        value=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_swap_two_bytes,
                    Params(
                        first_pos=util.AdaptiveRange(adaptive=adaptive),
                        second_pos=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_add_subtract_from_a_byte,
                    Params(
                        pos=util.AdaptiveRange(adaptive=adaptive),
                        value=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_add_subtract_from_a_uint16,
                    Params(
                        pos=util.AdaptiveRange(adaptive=adaptive),
                        value=util.AdaptiveRange(adaptive=adaptive),
                        big_endian=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_add_subtract_from_a_uint32,
                    Params(
                        pos=util.AdaptiveRange(adaptive=adaptive),
                        value=util.AdaptiveRange(adaptive=adaptive),
                        big_endian=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_add_subtract_from_a_uint64,
                    Params(
                        pos=util.AdaptiveRange(adaptive=adaptive),
                        value=util.AdaptiveRange(adaptive=adaptive),
                        big_endian=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_replace_a_byte_with_an_interesting_value,
                    Params(
                        pos=util.AdaptiveRange(adaptive=adaptive),
                        interesting_8=util.AdaptiveChoiceBase(
                            population=[1, 1, 16, 32, 64, 100, 127, 128, 129, 255],
                            adaptive=adaptive,
                        ),
                    ),
                ),
                (
                    _mutate_replace_an_uint16_with_an_interesting_value,
                    Params(
                        pos=util.AdaptiveRange(adaptive=adaptive),
                        interesting_16=util.AdaptiveChoiceBase(
                            population=[0, 128, 255, 256, 512, 1000, 1024, 4096, 32767, 65535],
                            adaptive=adaptive,
                        ),
                        big_endian=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_replace_an_uint32_with_an_interesting_value,
                    Params(
                        pos=util.AdaptiveRange(adaptive=adaptive),
                        interesting_32=util.AdaptiveChoiceBase(
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
                            adaptive=adaptive,
                        ),
                        big_endian=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
                (
                    _mutate_replace_an_ascii_digit_with_another_digit,
                    Params(
                        pos=util.AdaptiveRange(adaptive=adaptive),
                        digits=util.AdaptiveChoiceBase(
                            population=[
                                ord(i) for i in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")
                            ],
                            adaptive=adaptive,
                        ),
                    ),
                ),
                (
                    _mutate_splice,
                    Params(
                        left_pos=util.AdaptiveRange(adaptive=adaptive),
                        right_pos=util.AdaptiveRange(adaptive=adaptive),
                    ),
                ),
            ],
        )
        self._last_rands: Optional[Params] = None

    def _mutate(self, buf: bytearray) -> bytearray:
        res = buf[:]
        nm = self._modifications.sample(1, self._max_modifications)
        while nm:
            modify, self._last_rands = self._mutators.sample()
            try:
                modify(res, self._last_rands, self._inputs)
            except common.OutOfDataError:
                pass
            else:
                nm -= 1

        if self._max_input_size and len(res) > self._max_input_size:
            res = res[: self._max_input_size]
        return res

    def get_input(self) -> bytearray:
        return self._mutate(self._inputs.sample())

    def put_input(self, buf: bytearray) -> None:
        self._inputs.append(buf)

    def input_length(self) -> int:
        return len(self._inputs)

    def restore(self, data: list[str]) -> None:
        for d in data:
            self._inputs.append(bytearray(ast.literal_eval(d)))

    def dump(self) -> list[str]:
        return [str(bytes(i)) for i in self._inputs]

    def update(self, success: bool = False) -> None:
        if self._last_rands is not None:
            self._last_rands.update(success=success)
        self._inputs.update(success=success)
        self._modifications.update(success=success)
        self._mutators.update(success=success)

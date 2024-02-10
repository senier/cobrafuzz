from __future__ import annotations

import secrets
import struct

from . import util


class OutOfDataError(Exception):
    pass


class Mutator:
    def __init__(self, max_input_size: int = 1024):
        self._max_input_size = max_input_size
        self._INTERESTING8 = [0, 1, 16, 32, 64, 100, 127, 128, 129, 255]
        self._INTERESTING16 = [0, 128, 255, 256, 512, 1000, 1024, 4096, 32767, 65535]
        self._INTERESTING32 = [0, 1, 32768, 65535, 65536, 100663045, 2147483647, 4294967295]
        self._DIGITS = {ord(i) for i in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")}

    def _mutate_remove_range_of_bytes(self, res: bytearray) -> None:
        if len(res) < 2:
            raise OutOfDataError
        start = util.rand(len(res))
        util.remove(data=res, start=start, length=util.choose_len(len(res) - start))

    def _mutate_insert_range_of_bytes(self, res: bytearray) -> None:
        data = secrets.token_bytes(util.choose_len(10))
        util.insert(data=res, start=util.rand(len(res) + 1), data_to_insert=data)

    def _mutate_duplicate_range_of_bytes(self, res: bytearray) -> None:
        if len(res) < 2:
            raise OutOfDataError
        src = util.rand(len(res))
        dst = util.rand(len(res))
        n = util.choose_len(len(res) - src)
        util.insert(res, dst, res[src : src + n])

    def _mutate_copy_range_of_bytes(self, res: bytearray) -> None:
        if len(res) < 2:
            raise OutOfDataError
        src = util.rand(len(res))
        dst = util.rand(len(res))
        n = util.choose_len(min(len(res) - src, len(res) - dst))
        util.copy(res, src, dst, n)

    def _mutate_bit_flip(self, res: bytearray) -> None:
        if len(res) < 1:
            raise OutOfDataError
        pos = util.rand(len(res))
        res[pos] ^= 1 << util.rand(8)

    def _mutate_flip_random_bits_of_random_byte(self, res: bytearray) -> None:
        if len(res) < 1:
            raise OutOfDataError
        pos = util.rand(len(res))
        res[pos] ^= util.rand(255) + 1

    def _mutate_swap_two_bytes(self, res: bytearray) -> None:
        if len(res) < 2:
            raise OutOfDataError
        src = util.rand(len(res))
        dst = util.rand(len(res))
        res[src], res[dst] = res[dst], res[src]

    def _mutate_add_subtract_from_a_byte(self, res: bytearray) -> None:
        if len(res) < 1:
            raise OutOfDataError
        pos = util.rand(len(res))
        v_int = util.rand(2**8)
        res[pos] = (res[pos] + v_int) % 256

    def _mutate_add_subtract_from_a_uint16(self, res: bytearray) -> None:
        if len(res) < 2:
            raise OutOfDataError
        pos = util.rand(len(res) - 1)
        v_int = util.rand(2**16)
        v = struct.pack(">H", v_int) if util.rand_bool() else struct.pack("<H", v_int)
        # TODO(#18): Implement version performing 16-bit addition
        res[pos] = (res[pos] + v[0]) % 256
        res[pos + 1] = (res[pos + 1] + v[1]) % 256

    def _mutate_add_subtract_from_a_uint32(self, res: bytearray) -> None:
        if len(res) < 4:
            raise OutOfDataError
        pos = util.rand(len(res) - 3)
        v_int = util.rand(2**32)
        v = struct.pack(">I", v_int) if util.rand_bool() else struct.pack("<I", v_int)
        res[pos] = (res[pos] + v[0]) % 256
        res[pos + 1] = (res[pos + 1] + v[1]) % 256
        res[pos + 2] = (res[pos + 2] + v[2]) % 256
        res[pos + 3] = (res[pos + 3] + v[3]) % 256

    def _mutate_add_subtract_from_a_uint64(self, res: bytearray) -> None:
        if len(res) < 8:
            raise OutOfDataError
        pos = util.rand(len(res) - 7)
        v_int = util.rand(2**64)
        v = struct.pack(">Q", v_int) if util.rand_bool() else struct.pack("<Q", v_int)
        res[pos] = (res[pos] + v[0]) % 256
        res[pos + 1] = (res[pos + 1] + v[1]) % 256
        res[pos + 2] = (res[pos + 2] + v[2]) % 256
        res[pos + 3] = (res[pos + 3] + v[3]) % 256
        res[pos + 4] = (res[pos + 4] + v[4]) % 256
        res[pos + 5] = (res[pos + 5] + v[5]) % 256
        res[pos + 6] = (res[pos + 6] + v[6]) % 256
        res[pos + 7] = (res[pos + 7] + v[7]) % 256

    def _mutate_replace_a_byte_with_an_interesting_value(
        self,
        res: bytearray,
    ) -> None:
        if len(res) < 1:
            raise OutOfDataError
        pos = util.rand(len(res))
        res[pos] = secrets.choice(self._INTERESTING8)

    def _mutate_replace_an_uint16_with_an_interesting_value(
        self,
        res: bytearray,
    ) -> None:
        if len(res) < 2:
            raise OutOfDataError
        pos = util.rand(len(res) - 1)
        v_int = secrets.choice(self._INTERESTING16)
        v = struct.pack(">H", v_int) if util.rand_bool() else struct.pack("<H", v_int)
        res[pos] = v[0] % 256
        res[pos + 1] = v[1] % 256

    def _mutate_replace_an_uint32_with_an_interesting_value(
        self,
        res: bytearray,
    ) -> None:
        if len(res) < 4:
            raise OutOfDataError
        pos = util.rand(len(res) - 3)
        v_int = secrets.choice(self._INTERESTING32)
        v = struct.pack(">I", v_int) if util.rand_bool() else struct.pack("<I", v_int)
        res[pos] = v[0] % 256
        res[pos + 1] = v[1] % 256
        res[pos + 2] = v[2] % 256
        res[pos + 3] = v[3] % 256

    def _mutate_replace_an_ascii_digit_with_another_digit(
        self,
        res: bytearray,
    ) -> None:
        digits_present = [(i, res[i]) for i in range(len(res)) if ord("0") <= res[i] <= ord("9")]
        if len(digits_present) < 1:
            raise OutOfDataError
        pos, old = secrets.choice(digits_present)
        res[pos] = secrets.choice(list(self._DIGITS - {old}))

    def mutate(self, buf: bytearray) -> bytearray:
        res = buf[:]
        nm = util.rand_exp()
        while nm:
            modify = secrets.choice(
                [
                    self._mutate_insert_range_of_bytes,
                    self._mutate_add_subtract_from_a_byte,
                    self._mutate_add_subtract_from_a_uint16,
                    self._mutate_add_subtract_from_a_uint32,
                    self._mutate_add_subtract_from_a_uint64,
                    self._mutate_bit_flip,
                    self._mutate_copy_range_of_bytes,
                    self._mutate_duplicate_range_of_bytes,
                    self._mutate_replace_a_byte_with_an_interesting_value,
                    self._mutate_replace_an_ascii_digit_with_another_digit,
                    self._mutate_replace_an_uint16_with_an_interesting_value,
                    self._mutate_replace_an_uint32_with_an_interesting_value,
                    self._mutate_flip_random_bits_of_random_byte,
                    self._mutate_swap_two_bytes,
                    self._mutate_remove_range_of_bytes,
                ],
            )
            try:
                modify(res)
            except OutOfDataError:
                pass
            else:
                nm -= 1

        if self._max_input_size and len(res) > self._max_input_size:
            res = res[: self._max_input_size]
        return res

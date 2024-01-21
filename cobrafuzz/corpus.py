from __future__ import annotations

import hashlib
import os
import random
import secrets
import struct
from pathlib import Path
from secrets import randbelow
from typing import Optional

from . import dictionary, util

INTERESTING8 = [-128, -1, 0, 1, 16, 32, 64, 100, 127]
INTERESTING16 = [0, 128, 255, 256, 512, 1000, 1024, 4096, 32767, 65535]
INTERESTING32 = [0, 1, 32768, 65535, 65536, 100663045, 2147483647, 4294967295]


def _rand(n: int) -> int:
    if n < 2:
        return 0
    return randbelow(n)


# Exp2 generates n with probability 1/2^(n+1).
def _rand_exp() -> int:
    rand_bin = bin(random.randint(0, 2**32 - 1))[2:]  # noqa: S311
    rand_bin = "0" * (32 - len(rand_bin)) + rand_bin
    count = 0
    for i in rand_bin:
        if i == "0":
            count += 1
        else:
            break
    return count


def _choose_len(n: int) -> int:
    """
    Choose a length based on input value.

    With 90% probability, choose a random value in [1, n] (if n <=  8, otherwise [1, 8])
    With  9% probability, choose a random value in [1, n] (if n <= 32, otherwise [1, 32])
    With  1% probability, choose a random value in [1, n]
    """
    x = _rand(100)
    if x < 90:
        return _rand(min(8, n)) + 1
    if x < 99:
        return _rand(min(32, n)) + 1
    return _rand(n) + 1


def _mutate_remove_range_of_bytes(res: bytearray) -> bool:
    if len(res) < 2:
        return False
    start = _rand(len(res))
    util.remove(data=res, start=start, length=_choose_len(len(res) - start))
    return True


def _mutate_insert_range_of_bytes(res: bytearray) -> bool:
    # TODO(senier): Make magic number 10 configurable.
    data = secrets.token_bytes(_choose_len(10))
    util.insert(data=res, start=_rand(len(res) + 1), data_to_insert=data)
    return True


def _mutate_duplicate_range_of_bytes(res: bytearray) -> bool:
    if len(res) < 2:
        return False
    src = _rand(len(res))
    dst = _rand(len(res))
    n = _choose_len(len(res) - src)
    util.insert(res, dst, res[src : src + n])
    return True


def _mutate_copy_range_of_bytes(res: bytearray) -> bool:
    if len(res) < 2:
        return False
    src = _rand(len(res))
    dst = _rand(len(res))
    n = _choose_len(min(len(res) - src, len(res) - dst))
    util.copy(res, src, dst, n)
    return True


def _mutate_bit_flip(res: bytearray) -> bool:
    if len(res) < 1:
        return False
    pos = _rand(len(res))
    res[pos] ^= 1 << _rand(8)
    return True


def _mutate_flip_random_bits_of_random_byte(res: bytearray) -> bool:
    if len(res) < 1:
        return False
    pos = _rand(len(res))
    res[pos] ^= _rand(255) + 1
    return True


def _mutate_swap_two_bytes(res: bytearray) -> bool:
    if len(res) < 2:
        return False
    src = _rand(len(res))
    dst = _rand(len(res))
    res[src], res[dst] = res[dst], res[src]
    return True


def _mutate_add_subtract_from_a_byte(res: bytearray) -> bool:
    if len(res) < 1:
        return False
    pos = _rand(len(res))
    v_int = _rand(2**8)
    res[pos] = (res[pos] + v_int) % 256
    return True


def _mutate_add_subtract_from_a_uint16(res: bytearray) -> bool:
    if len(res) < 2:
        return False
    pos = _rand(len(res) - 1)
    v_int = _rand(2**16)
    v = struct.pack(">H", v_int) if bool(random.getrandbits(1)) else struct.pack("<H", v_int)
    res[pos] = (res[pos] + v[0]) % 256
    res[pos + 1] = (res[pos] + v[1]) % 256
    return True


def _mutate_add_subtract_from_a_uint32(res: bytearray) -> bool:
    if len(res) < 4:
        return False
    pos = _rand(len(res) - 3)
    v_int = _rand(2**32)
    v = struct.pack(">I", v_int) if bool(random.getrandbits(1)) else struct.pack("<I", v_int)
    res[pos] = (res[pos] + v[0]) % 256
    res[pos + 1] = (res[pos + 1] + v[1]) % 256
    res[pos + 2] = (res[pos + 2] + v[2]) % 256
    res[pos + 3] = (res[pos + 3] + v[3]) % 256
    return True


def _mutate_add_subtract_from_a_uint64(res: bytearray) -> bool:
    if len(res) < 8:
        return False
    pos = _rand(len(res) - 7)
    v_int = _rand(2**64)
    v = struct.pack(">Q", v_int) if bool(random.getrandbits(1)) else struct.pack("<Q", v_int)
    res[pos] = (res[pos] + v[0]) % 256
    res[pos + 1] = (res[pos + 1] + v[1]) % 256
    res[pos + 2] = (res[pos + 2] + v[2]) % 256
    res[pos + 3] = (res[pos + 3] + v[3]) % 256
    res[pos + 4] = (res[pos + 4] + v[4]) % 256
    res[pos + 5] = (res[pos + 5] + v[5]) % 256
    res[pos + 6] = (res[pos + 6] + v[6]) % 256
    res[pos + 7] = (res[pos + 7] + v[7]) % 256
    return True


def _mutate_replace_a_byte_with_an_interesting_value(res: bytearray) -> bool:
    if len(res) < 1:
        return False
    pos = _rand(len(res))
    res[pos] = INTERESTING8[_rand(len(INTERESTING8))] % 256
    return True


def _mutate_replace_an_uint16_with_an_interesting_value(res: bytearray) -> bool:
    if len(res) < 2:
        return False
    pos = _rand(len(res) - 1)
    v_int = random.choice(INTERESTING16)  # noqa: S311
    v = struct.pack(">H", v_int) if bool(random.getrandbits(1)) else struct.pack("<H", v_int)
    res[pos] = v[0] % 256
    res[pos + 1] = v[1] % 256
    return True


def _mutate_replace_an_uint32_with_an_interesting_value(res: bytearray) -> bool:
    if len(res) < 4:
        return False
    pos = _rand(len(res) - 3)
    v_int = random.choice(INTERESTING32)  # noqa: S311
    v = struct.pack(">I", v_int) if bool(random.getrandbits(1)) else struct.pack("<I", v_int)
    res[pos] = v[0] % 256
    res[pos + 1] = v[1] % 256
    res[pos + 2] = v[2] % 256
    res[pos + 3] = v[3] % 256
    return True


def _mutate_replace_an_ascii_digit_with_another_digit(res: bytearray) -> bool:
    digits = [k for k in range(len(res)) if ord("0") <= res[k] <= ord("9")]
    if len(digits) == 0:
        return False
    pos = _rand(len(digits))
    was = res[digits[pos]]
    now = was
    while was == now:
        now = _rand(10) + ord("0")
    res[digits[pos]] = now
    return False


class Corpus:
    def __init__(
        self,
        dirs: Optional[list[Path]] = None,
        max_input_size: int = 4096,
        dict_path: Optional[Path] = None,
    ):
        self._inputs: list[bytearray] = []
        self._dict = dictionary.Dictionary(dict_path)
        self._max_input_size = max_input_size
        self._dirs = dirs if dirs else []
        for i, path in enumerate(self._dirs):
            if i == 0 and not path.exists():
                path.mkdir()

            if path.is_file():
                self._add_file(path)
            else:
                for j in os.listdir(path):
                    fname = path / j
                    if fname.is_file():
                        self._add_file(fname)
        self._seed_run_finished = not self._inputs
        self._seed_idx = 0
        self._save_corpus: bool = bool(self._dirs) and self._dirs[0].is_dir()

        # TODO(senier): Why this additional 0 element?
        self._inputs.append(bytearray(0))

    def _add_file(self, path: Path) -> None:
        with path.open("rb") as f:
            self._inputs.append(bytearray(f.read()))

    @property
    def length(self) -> int:
        return len(self._inputs)

    def put(self, buf: bytearray) -> None:
        self._inputs.append(buf)
        if self._save_corpus:
            fname = self._dirs[0] / hashlib.sha256(buf).hexdigest()
            with fname.open("wb") as f:
                f.write(buf)

    def generate_input(self) -> bytearray:
        if not self._seed_run_finished:
            next_input = self._inputs[self._seed_idx]
            self._seed_idx += 1
            if self._seed_idx >= len(self._inputs):
                self._seed_run_finished = True
            return next_input

        buf = self._inputs[_rand(len(self._inputs))]
        return self.mutate(buf)

    def mutate(self, buf: bytearray) -> bytearray:
        res = buf[:]
        nm = _rand_exp()
        i = 0
        while i != nm:
            modify = random.choice(  # noqa: S311
                [
                    _mutate_insert_range_of_bytes,
                    _mutate_add_subtract_from_a_byte,
                    _mutate_add_subtract_from_a_uint16,
                    _mutate_add_subtract_from_a_uint32,
                    _mutate_add_subtract_from_a_uint64,
                    _mutate_bit_flip,
                    _mutate_copy_range_of_bytes,
                    _mutate_duplicate_range_of_bytes,
                    _mutate_replace_a_byte_with_an_interesting_value,
                    _mutate_replace_an_ascii_digit_with_another_digit,
                    _mutate_replace_an_uint16_with_an_interesting_value,
                    _mutate_replace_an_uint32_with_an_interesting_value,
                    _mutate_flip_random_bits_of_random_byte,
                    _mutate_swap_two_bytes,
                    _mutate_remove_range_of_bytes,
                ],
            )
            if modify(res):
                i += 1

        if len(res) > self._max_input_size:
            res = res[: self._max_input_size]
        return res

from __future__ import annotations

import hashlib
import os
import random
import struct
from pathlib import Path
from secrets import randbelow
from typing import Optional

from . import dictionary

INTERESTING8 = [-128, -1, 0, 1, 16, 32, 64, 100, 127]
INTERESTING16 = [0, 128, 255, 256, 512, 1000, 1024, 4096, 32767, 65535]
INTERESTING32 = [0, 1, 32768, 65535, 65536, 100663045, 2147483647, 4294967295]


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

    @staticmethod
    def _rand(n: int) -> int:
        if n < 2:
            return 0
        return randbelow(n)

    # Exp2 generates n with probability 1/2^(n+1).
    @staticmethod
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

    @staticmethod
    def _choose_len(n: int) -> int:
        x = Corpus._rand(100)
        if x < 90:
            return Corpus._rand(min(8, n)) + 1
        if x < 99:
            return Corpus._rand(min(32, n)) + 1
        return Corpus._rand(n) + 1

    @staticmethod
    def copy(
        src: bytearray,
        dst: bytearray,
        start_source: int,
        start_dst: int,
        end_source: Optional[int] = None,
        end_dst: Optional[int] = None,
    ) -> None:
        end_source = len(src) if end_source is None else end_source
        end_dst = len(dst) if end_dst is None else end_dst
        byte_to_copy = min(end_source - start_source, end_dst - start_dst)
        dst[start_dst : start_dst + byte_to_copy] = src[start_source : start_source + byte_to_copy]

    def put(self, buf: bytearray) -> None:
        self._inputs.append(buf)
        if self._save_corpus:
            m = hashlib.sha256()
            m.update(buf)
            fname = self._dirs[0] / m.hexdigest()
            with fname.open("wb") as f:
                f.write(buf)

    def generate_input(self) -> bytearray:
        if not self._seed_run_finished:
            next_input = self._inputs[self._seed_idx]
            self._seed_idx += 1
            if self._seed_idx >= len(self._inputs):
                self._seed_run_finished = True
            return next_input

        buf = self._inputs[self._rand(len(self._inputs))]
        return self.mutate(buf)

    def mutate(self, buf: bytearray) -> bytearray:  # noqa: PLR0912, PLR0915
        res = buf[:]
        nm = self._rand_exp()
        i = 0
        while i != nm:
            i += 1
            # Remove a range of bytes.
            x = self._rand(15)
            if x == 0:
                if len(self._inputs) <= 1:
                    i -= 1
                    continue
                pos0 = self._rand(len(res))
                pos1 = pos0 + self._choose_len(len(res) - pos0)
                self.copy(res, res, pos1, pos0)
                res = res[: len(res) - (pos1 - pos0)]
            elif x == 1:
                # Insert a range of random bytes.
                pos = self._rand(len(res) + 1)
                n = self._choose_len(10)
                for _ in range(n):
                    res.append(0)
                self.copy(res, res, pos, pos + n)
                for k in range(n):
                    res[pos + k] = self._rand(256)
            elif x == 2:
                # Duplicate a range of bytes.
                if len(res) <= 1:
                    i -= 1
                    continue
                src = self._rand(len(res))
                dst = self._rand(len(res))
                while src == dst:
                    dst = self._rand(len(res))
                n = self._choose_len(len(res) - src)
                tmp = bytearray(n)
                self.copy(res, tmp, src, 0)
                for _ in range(n):
                    res.append(0)
                self.copy(res, res, dst, dst + n)
                for k in range(n):
                    res[dst + k] = tmp[k]
            elif x == 3:
                # Copy a range of bytes.
                if len(res) <= 1:
                    i -= 1
                    continue
                src = self._rand(len(res))
                dst = self._rand(len(res))
                while src == dst:
                    dst = self._rand(len(res))
                n = self._choose_len(len(res) - src)
                self.copy(res, res, src, dst, src + n)
            elif x == 4:
                # Bit flip. Spooky!
                if len(res) == 0:
                    i -= 1
                    continue
                pos = self._rand(len(res))
                res[pos] ^= 1 << self._rand(8)
            elif x == 5:
                # Set a byte to a random value.
                if len(res) == 0:
                    i -= 1
                    continue
                pos = self._rand(len(res))
                res[pos] ^= self._rand(255) + 1
            elif x == 6:
                # Swap 2 bytes.
                if len(res) <= 1:
                    i -= 1
                    continue
                src = self._rand(len(res))
                dst = self._rand(len(res))
                while src == dst:
                    dst = self._rand(len(res))
                res[src], res[dst] = res[dst], res[src]
            elif x == 7:
                # Add/subtract from a byte.
                if len(res) == 0:
                    i -= 1
                    continue
                pos = self._rand(len(res))
                v_int = self._rand(2**8)
                res[pos] = (res[pos] + v_int) % 256
            elif x == 8:
                # Add/subtract from a uint16.
                if len(res) < 2:
                    i -= 1
                    continue
                pos = self._rand(len(res) - 1)
                v_int = self._rand(2**16)
                v = (
                    struct.pack(">H", v_int)
                    if bool(random.getrandbits(1))
                    else struct.pack("<H", v_int)
                )
                res[pos] = (res[pos] + v[0]) % 256
                res[pos + 1] = (res[pos] + v[1]) % 256
            elif x == 9:
                # Add/subtract from a uint32.
                if len(res) < 4:
                    i -= 1
                    continue
                pos = self._rand(len(res) - 3)
                v_int = self._rand(2**32)
                v = (
                    struct.pack(">I", v_int)
                    if bool(random.getrandbits(1))
                    else struct.pack("<I", v_int)
                )
                res[pos] = (res[pos] + v[0]) % 256
                res[pos + 1] = (res[pos + 1] + v[1]) % 256
                res[pos + 2] = (res[pos + 2] + v[2]) % 256
                res[pos + 3] = (res[pos + 3] + v[3]) % 256
            elif x == 10:
                # Add/subtract from a uint64.
                if len(res) < 8:
                    i -= 1
                    continue
                pos = self._rand(len(res) - 7)
                v_int = self._rand(2**64)
                v = (
                    struct.pack(">Q", v_int)
                    if bool(random.getrandbits(1))
                    else struct.pack("<Q", v_int)
                )
                res[pos] = (res[pos] + v[0]) % 256
                res[pos + 1] = (res[pos + 1] + v[1]) % 256
                res[pos + 2] = (res[pos + 2] + v[2]) % 256
                res[pos + 3] = (res[pos + 3] + v[3]) % 256
                res[pos + 4] = (res[pos + 4] + v[4]) % 256
                res[pos + 5] = (res[pos + 5] + v[5]) % 256
                res[pos + 6] = (res[pos + 6] + v[6]) % 256
                res[pos + 7] = (res[pos + 7] + v[7]) % 256
            elif x == 11:
                # Replace a byte with an interesting value.
                if len(res) == 0:
                    i -= 1
                    continue
                pos = self._rand(len(res))
                res[pos] = INTERESTING8[self._rand(len(INTERESTING8))] % 256
            elif x == 12:
                # Replace an uint16 with an interesting value.
                if len(res) < 2:
                    i -= 1
                    continue
                pos = self._rand(len(res) - 1)
                v_int = random.choice(INTERESTING16)  # noqa: S311
                v = (
                    struct.pack(">H", v_int)
                    if bool(random.getrandbits(1))
                    else struct.pack("<H", v_int)
                )
                res[pos] = v[0] % 256
                res[pos + 1] = v[1] % 256
            elif x == 13:
                # Replace an uint32 with an interesting value.
                if len(res) < 4:
                    i -= 1
                    continue
                pos = self._rand(len(res) - 3)
                v_int = random.choice(INTERESTING32)  # noqa: S311
                v = (
                    struct.pack(">I", v_int)
                    if bool(random.getrandbits(1))
                    else struct.pack("<I", v_int)
                )
                res[pos] = v[0] % 256
                res[pos + 1] = v[1] % 256
                res[pos + 2] = v[2] % 256
                res[pos + 3] = v[3] % 256
            elif x == 14:
                # Replace an ascii digit with another digit.
                digits = [k for k in range(len(res)) if ord("0") <= res[k] <= ord("9")]
                if len(digits) == 0:
                    i -= 1
                    continue
                pos = self._rand(len(digits))
                was = res[digits[pos]]
                now = was
                while was == now:
                    now = self._rand(10) + ord("0")
                res[digits[pos]] = now

        if len(res) > self._max_input_size:
            res = res[: self._max_input_size]
        return res

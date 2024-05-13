#!/usr/bin/env -S python3 -O

import contextlib

from cobrafuzz.common import OutOfBoundsError
from cobrafuzz.main import CobraFuzz
from cobrafuzz.mutator import Mutator


@CobraFuzz
def fuzz(data: bytes) -> None:
    with contextlib.suppress(OutOfBoundsError):
        Mutator()._mutate(bytearray(data))  # noqa: SLF001


if __name__ == "__main__":
    fuzz()

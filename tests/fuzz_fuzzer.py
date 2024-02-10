#!/usr/bin/env -S python3 -O

from cobrafuzz.main import CobraFuzz
from cobrafuzz.mutator import Corpus

CORPUS = Corpus()


@CobraFuzz
def fuzz(data: bytes) -> None:
    CORPUS.mutate(bytearray(data))


if __name__ == "__main__":
    fuzz()

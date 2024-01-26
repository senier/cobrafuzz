#!/usr/bin/env -S python3 -O

from cobrafuzz.corpus import Corpus
from cobrafuzz.main import CobraFuzz

CORPUS = Corpus()


@CobraFuzz
def fuzz(data: bytes) -> None:
    CORPUS.mutate(bytearray(data))


if __name__ == "__main__":
    fuzz()

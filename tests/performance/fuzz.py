#!/usr/bin/env python3
# ruff: noqa: SIM102

from cobrafuzz.main import CobraFuzz


class BoomError(Exception):
    pass


@CobraFuzz
def crashing_target_hard(data: bytes) -> None:
    if len(data) > 0 and data[0] == ord("b"):
        if len(data) > 1 and data[1] == ord("o"):
            if len(data) > 2 and data[2] == ord("o"):
                if len(data) > 3 and data[3] == ord("m"):
                    raise BoomError


if __name__ == "__main__":
    crashing_target_hard()

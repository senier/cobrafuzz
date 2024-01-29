#!/usr/bin/env python3

import argparse
import logging
import time

from cobrafuzz.corpus import mutate


def _mutate(rounds: int) -> None:
    data = bytearray(b"start")
    start = time.time()
    for _ in range(rounds):
        mutate(data)
    duration = time.time() - start
    logging.info("mutate: %d/s", rounds // duration)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rounds",
        type=int,
        default=1000000,
        help="Rounds to execute benchmark for (default: %(default)d)",
    )
    parser.add_argument(
        "--mutate",
        action="store_true",
        help="Benchmark corpus.mutate",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.mutate:
        _mutate(args.rounds)


if __name__ == "__main__":
    main()

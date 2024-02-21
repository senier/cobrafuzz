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


def bench_mutate(args: argparse.Namespace) -> None:
    _mutate(args.rounds)


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rounds",
        type=int,
        default=1000000,
        help="Rounds to execute benchmark for (default: %(default)d)",
    )

    subparsers = parser.add_subparsers()
    mutate_parser = subparsers.add_parser("mutate", help="Benchmark corpus.mutate")
    mutate_parser.set_defaults(func=bench_mutate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

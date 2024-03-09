import argparse
import logging
import sys
from pathlib import Path
from typing import Callable

from cobrafuzz import fuzzer


class CobraFuzz:
    def __init__(self, func: Callable[[bytes], None]):
        self.function = func

    def __call__(self) -> None:
        parser = argparse.ArgumentParser(description="Coverage-guided fuzzer for Python")

        parser.add_argument(
            "--crash-dir",
            type=Path,
            required=True,
            help="Crash output directory.",
        )
        parser.add_argument(
            "--regression",
            action="store_true",
            help="Runner target on examples in crash directory, print errors and exit.",
        )

        parser.add_argument(
            "-j",
            "--num-workers",
            type=int,
            help="Number of parallel workers (default: one less than CPUs available).",
        )
        parser.add_argument(
            "--max-input-size",
            type=int,
            default=4096,
            help="Max input size to be generated in bytes.",
        )
        parser.add_argument(
            "--close-stdout",
            action="store_true",
            help="Close standard output on worker startup.",
        )
        parser.add_argument(
            "--close-stderr",
            action="store_true",
            help="Close standard error on worker startup.",
        )
        parser.add_argument(
            "--max-crashes",
            type=int,
            help="Maximum number crashes before exiting.",
        )
        parser.add_argument(
            "--max-runs",
            type=int,
            help="Maximum number test runs to perform.",
        )
        parser.add_argument(
            "--max-time",
            type=int,
            help="Maximum number of seconds to run the fuzzer.",
        )
        parser.add_argument(
            "--start-method",
            type=str,
            choices=["spawn", "forkserver", "fork"],
            default="spawn",
            help="Start method to be used for multiprocessing (default: %(default)s).",
        )
        parser.add_argument(
            "--state-file",
            type=Path,
            help="File to periodically store fuzzer state to.",
        )

        parser.add_argument(
            "seeds",
            type=Path,
            nargs="*",
            help="List of files or directories to seed corpus from.",
        )

        args = parser.parse_args()
        f = fuzzer.Fuzzer(
            crash_dir=args.crash_dir,
            target=self.function,
            close_stderr=args.close_stderr,
            close_stdout=args.close_stdout,
            max_crashes=args.max_crashes,
            max_input_size=args.max_input_size,
            max_runs=args.max_runs,
            max_time=args.max_time,
            num_workers=args.num_workers,
            regression=args.regression,
            seeds=args.seeds,
            start_method=args.start_method,
            state_file=args.state_file,
        )
        logging.basicConfig(format="[%(asctime)s] %(message)s")
        try:
            f.start()
        except KeyboardInterrupt:
            sys.exit("\nUser cancellation. Exiting.\n")

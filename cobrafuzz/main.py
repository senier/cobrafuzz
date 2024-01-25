import argparse
from pathlib import Path
from typing import Callable

from cobrafuzz import fuzzer


class CobraFuzz:
    def __init__(self, func: Callable[[bytes], None]):
        self.function = func

    def __call__(self) -> None:
        parser = argparse.ArgumentParser(description="Coverage-guided fuzzer for python packages")
        parser.add_argument(
            "dirs",
            type=Path,
            nargs="*",
            help=(
                "one or more directories/files to use as seed corpus. "
                "the first directory will be used to save the generated test-cases"
            ),
        )
        parser.add_argument(
            "--crash-dir",
            type=Path,
            required=True,
            help="crash output directory",
        )
        parser.add_argument(
            "--artifact-name",
            type=str,
            help="set exact artifact path for crashes/OOMs",
        )
        parser.add_argument(
            "--regression",
            type=bool,
            default=False,
            help="run the fuzzer through set of files for regression or reproduction",
        )
        parser.add_argument("--rss-limit-mb", type=int, default=2048, help="Memory usage in MB")
        parser.add_argument(
            "--max-input-size",
            type=int,
            default=4096,
            help="Max input size in bytes",
        )
        parser.add_argument(
            "--close-fd-mask",
            type=int,
            default=0,
            help="Indicate output streams to close at startup",
        )
        parser.add_argument(
            "--runs",
            type=int,
            default=-1,
            help="Number of individual test runs, -1 (the default) to run indefinitely.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=30,
            help="If input takes longer then this timeout the process is treated as failure case",
        )
        args = parser.parse_args()
        f = fuzzer.Fuzzer(
            target=self.function,
            crash_dir=args.crash_dir,
            dirs=args.dirs,
            artifact_name=args.artifact_name,
            rss_limit_mb=args.rss_limit_mb,
            timeout=args.timeout,
            regression=args.regression,
            max_input_size=args.max_input_size,
            close_fd_mask=args.close_fd_mask,
            runs=args.runs,
        )
        f.start()

#!/usr/bin/env -S python3 -O
from __future__ import annotations

import argparse
import importlib
import json
import logging
import time
import traceback
from pathlib import Path

import plotly.colors  # type: ignore[import-untyped]
import plotly.graph_objects as go  # type: ignore[import-untyped]
from plotly.subplots import make_subplots  # type: ignore[import-untyped]

from cobrafuzz import fuzzer, mutator, state, tracer

EXAMPLES = [
    "aifc",
    "bs",
    "codeop",
    "furl",
    "htmlparser",
    "isort",
    "purl",
    "xml",
    "zipfile",
    "zlib",
]


def plot_paths(args: argparse.Namespace) -> None:
    data = {}
    for filename in args.input:
        with filename.open() as f:
            tmp = json.load(f)
            data[tmp["label"]] = tmp["data"]
    colors = dict(zip(data.keys(), plotly.colors.DEFAULT_PLOTLY_COLORS))
    examples = sorted({e for d in data.values() for e in d})
    fig = make_subplots(
        rows=len(examples),
        cols=1,
        shared_xaxes=True,
        subplot_titles=examples,
    )
    for label, benchmarks in data.items():
        for example, values in benchmarks.items():
            fig.add_trace(
                go.Scatter(
                    x=list(map(int, values.keys())),
                    y=list(values.values()),
                    name=f"{label}",
                    mode="lines+markers",
                    line={"color": colors[label]},
                    legendgroup=example,
                ),
                row=examples.index(example) + 1,
                col=1,
            )
    fig.update_layout(
        height=5000,
        legend_tracegroupgap=470,
    )
    fig.show()


def bench_paths(args: argparse.Namespace) -> None:
    result: dict[str, dict[int, int]] = {}
    tracer.initialize()
    for example in EXAMPLES:
        result[example] = {}
        st = state.State()
        tracer.reset()
        target = importlib.import_module(f"examples.fuzz_{example}.fuzz")
        for run in range(1, args.rounds):
            data = st.get_input()
            try:
                target.fuzz.function(bytes(data))
                increased = st.store_coverage(tracer.get_covered())
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                st.store_coverage(fuzzer.covered(e))
                increased = True

            st.update(success=increased)
            if increased:
                result[example][run] = st.total_coverage

    with args.output.open("w") as of:
        json.dump({"label": args.label, "data": result}, of)


def bench_mutate(args: argparse.Namespace) -> None:
    m = mutator.Mutator()
    data = bytearray(b"start")
    start = time.time()
    for _ in range(args.rounds):
        m._mutate(data)  # noqa: SLF001
    duration = time.time() - start
    logging.info("mutate: %d/s", args.rounds // duration)


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

    paths_parser = subparsers.add_parser("paths", help="Benchmark path exploration")
    paths_parser.add_argument("--output", type=Path, required=True, help="Output file (JSON)")
    paths_parser.add_argument(
        "--label",
        type=str,
        required=True,
        help="Label to associate benchmark with",
    )
    paths_parser.set_defaults(func=bench_paths)

    paths_parser = subparsers.add_parser("plot", help="Plot path exploration benchmarks")
    paths_parser.add_argument("input", type=Path, nargs="+", help="Input files (JSON)")
    paths_parser.set_defaults(func=plot_paths)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

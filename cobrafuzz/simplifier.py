from __future__ import annotations

import atexit
import logging
import multiprocessing as mp
import re
import time
from pathlib import Path
from typing import Callable, Optional, Union, cast

import dill as pickle  # type: ignore[import-untyped]

from cobrafuzz import common, util

MPContext = Union[mp.context.ForkContext, mp.context.ForkServerContext, mp.context.SpawnContext]
MPProcess = Union[mp.context.ForkProcess, mp.context.ForkServerProcess, mp.context.SpawnProcess]


def _simplify_remove_lines(
    data: bytes,
    rand: util.Params,
) -> bytes:
    lines = data.split(b"\n")
    assert isinstance(rand.start, util.AdaptiveRange)
    assert isinstance(rand.end, util.AdaptiveRange)
    start = rand.start.sample(lower=1, upper=len(lines))
    end = rand.end.sample(lower=start, upper=len(lines))
    return b"\n".join(lines[0 : start - 1] + lines[end:])


def _simplify_remove_characters(
    data: bytes,
    rand: util.Params,
) -> bytes:
    assert isinstance(rand.start, util.AdaptiveRange)
    assert isinstance(rand.length, util.AdaptiveRange)
    length = rand.length.sample(1, 9)
    start = rand.start.sample(0, len(data) - length)
    # Do not remove line breaks
    if b"\n" in data[start : start + length]:
        return data
    # Do not remove leading whitespace
    if data[: start + 1].split(b"\n")[-1].isspace():
        return data
    res = bytearray(data)
    util.remove(data=res, start=start, length=length)
    return bytes(res)


def _simplify_shorten_token(
    data: bytes,
    rand: util.Params,
) -> bytes:
    assert isinstance(rand.pos, util.AdaptiveRange)
    assert isinstance(rand.pattern, util.AdaptiveRange)

    pattern = (
        # This pattern treats underscores as special characters
        re.compile(rb"((?P<whitespace>\s+)|(?P<text>[a-zA-Z0-9]+))|([^a-zA-Z0-9])")
        if rand.pattern.sample(lower=0, upper=1)
        # This pattern treats underscores as part of a word
        else re.compile(rb"((?P<whitespace>\s+)|(?P<text>\w+))|([^\w\s])")
    )

    tokens = [
        (
            m.group(),
            "Whitespace" if m.group("whitespace") else "Text" if m.group("text") else "Special",
        )
        for m in pattern.finditer(data)
    ]
    text_tokens = sorted({t[0] for t in tokens if t[1] == "Text"})
    modify = text_tokens[rand.pos.sample(0, len(text_tokens) - 1)]
    return b"".join(t[0] if t[1] != "Text" or t[0] != modify else t[0][:-1] for t in tokens)


class Metrics:
    def __init__(
        self,
        data: bytes,
        coverage: Optional[set[tuple[Optional[str], Optional[int], str, int]]] = None,
    ):
        self.data = data
        self.coverage = coverage

    def __repr__(self) -> str:
        return f"{self.data!r} [{self.metrics}]"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            raise NotImplementedError

        diff_metrics = list(zip(other.metrics, self.metrics))
        no_decline = all(l <= r for l, r in diff_metrics)
        some_improvement = any(l < r for l, r in diff_metrics)

        return no_decline and some_improvement

    @property
    def metrics(self) -> list[int]:
        return [len(self.data), len([n for n in self.data if n == ord("\n")])]

    def equivalent_to(self, other: Metrics) -> bool:
        return self.coverage == other.coverage


def run_target(target: Callable[[bytes], None], data: bytes) -> Optional[Metrics]:
    try:
        with util.disable_logging():
            target(data)
    except Exception as e:  # noqa: BLE001
        return Metrics(data, util.covered(e.__traceback__, 1))
    return None


def simplifier(
    target_bytes: bytes,
    request_queue: mp.Queue[Optional[Metrics]],
    result_queue: mp.Queue[Optional[Metrics]],
    mutators: Optional[
        util.AdaptiveChoiceBase[
            tuple[
                Callable[[bytes, util.Params], bytes],
                util.Params,
            ]
        ]
    ] = None,
) -> None:
    target = cast(Callable[[bytes], None], pickle.loads(target_bytes))  # noqa: S301

    mutators = mutators or util.AdaptiveChoiceBase(
        population=[
            (
                _simplify_remove_lines,
                util.Params(start=util.AdaptiveRange(), end=util.AdaptiveRange()),
            ),
            (
                _simplify_remove_characters,
                util.Params(start=util.AdaptiveRange(), length=util.AdaptiveRange()),
            ),
            (
                _simplify_shorten_token,
                util.Params(pos=util.AdaptiveRange(), pattern=util.AdaptiveRange()),
            ),
        ],
    )

    while True:
        request = request_queue.get()
        if request is None:
            return

        modify, last_rands = mutators.sample()
        result = run_target(target, modify(request.data, last_rands))
        if result and result.equivalent_to(request) and request < result:
            result_queue.put(result)
            last_rands.update(success=True)
            mutators.update(success=True)
            continue

        result_queue.put(None)


class Simp:
    def __init__(  # noqa: PLR0913
        self,
        crash_dir: Path,
        output_dir: Path,
        target: Callable[[bytes], None],
        max_time: Optional[int] = None,
        start_method: Optional[str] = None,
        num_workers: int = 1,
    ) -> None:
        self._target = target
        self._crash_dir = crash_dir
        self._output_dir = output_dir
        self._max_time = max_time or 60

        mp_ctx: MPContext = (
            mp.get_context("fork")
            if start_method == "fork"
            else mp.get_context("forkserver")
            if start_method == "forkserver"
            else mp.get_context("spawn")
        )

        self._num_workers: int = num_workers or mp_ctx.cpu_count() - 1
        self._result_queue: mp.Queue[Optional[Metrics]] = mp_ctx.Queue()
        queue: mp.Queue[Optional[Metrics]] = mp_ctx.Queue(100)
        self._workers = [
            (
                mp_ctx.Process(
                    target=simplifier,
                    args=(
                        pickle.dumps(self._target),
                        queue,
                        self._result_queue,
                    ),
                ),
                queue,
            )
            for _ in range(self._num_workers)
        ]
        for p, _ in self._workers:
            p.start()

        atexit.register(self.terminate_workers)

    def terminate_workers(self) -> None:
        if not self._workers:
            return

        for _, q in self._workers:
            q.put(None)
        time.sleep(1)

        self._result_queue.cancel_join_thread()

        for p, q in self._workers:
            q.cancel_join_thread()
            p.terminate()
            p.join(timeout=1)

        del self._workers[:]

    def simplify(self) -> None:
        for in_filename in self._crash_dir.glob("*"):
            if not in_filename.is_file():
                continue
            out_filename = self._output_dir / in_filename.name
            if out_filename.exists():
                logging.info("Already simplified: %s", out_filename.name)
                continue
            if not self._output_dir.exists():
                self._output_dir.mkdir()

            with in_filename.open("rb") as in_f:
                data = in_f.read()
                try:
                    simplified = self._simplify(data)
                except common.InvalidSampleError:
                    logging.warning("Invalid sample: %s", in_filename.name)
                    continue

                with out_filename.open("wb") as out_f:
                    if not simplified:
                        logging.info("Could not simplify %s", in_filename.name)
                        out_f.write(data)
                        continue

                    logging.info("Simplified %s", in_filename.name)
                    out_f.write(simplified)

    def _simplify(self, data: bytes) -> bytes:
        start = time.time()
        best = run_target(self._target, data)

        if not best:
            raise common.InvalidSampleError("No exception for sample")

        while time.time() - start < self._max_time:
            while not self._result_queue.empty():
                result = self._result_queue.get()

                if result is not None and best < result:
                    best = result

            for _, queue in self._workers:
                if not queue.full():
                    queue.put(best)

        return best.data

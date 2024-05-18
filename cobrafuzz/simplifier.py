from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Optional

from cobrafuzz import common, util


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


@contextmanager
def disable_logging() -> Iterator[None]:
    previous_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)

    try:
        yield
    finally:
        logging.disable(previous_level)


class Simp:
    def __init__(
        self,
        crash_dir: Path,
        output_dir: Path,
        target: Callable[[bytes], None],
        steps: int = 10000,
    ) -> None:
        self._target = target
        self._crash_dir = crash_dir
        self._output_dir = output_dir
        self._steps = steps

        self._mutators: util.AdaptiveChoiceBase[
            tuple[
                Callable[[bytes, util.Params], bytes],
                util.Params,
            ]
        ] = util.AdaptiveChoiceBase(
            population=[
                (
                    _simplify_remove_lines,
                    util.Params(
                        start=util.AdaptiveRange(),
                        end=util.AdaptiveRange(),
                    ),
                ),
                (
                    _simplify_remove_characters,
                    util.Params(
                        start=util.AdaptiveRange(),
                        length=util.AdaptiveRange(),
                    ),
                ),
                (
                    _simplify_shorten_token,
                    util.Params(
                        pos=util.AdaptiveRange(),
                        pattern=util.AdaptiveRange(),
                    ),
                ),
            ],
        )

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

    def _run_target(self, data: bytes, previous: Optional[Metrics] = None) -> Optional[Metrics]:
        try:
            with disable_logging():
                self._target(data)
        except Exception as e:  # noqa: BLE001
            result = Metrics(data, util.covered(e.__traceback__, 1))
            if not previous or (result and result.equivalent_to(previous) and previous < result):
                return result

        return None

    def _simplify(self, data: bytes) -> bytes:
        steps = 0
        result: Optional[Metrics] = self._run_target(data)

        if result is None:
            raise common.InvalidSampleError("No exception for sample")

        while steps <= self._steps:
            steps += 1

            modify, self._last_rands = self._mutators.sample()
            current = self._run_target(data=modify(result.data, self._last_rands), previous=result)

            if current:
                self._last_rands.update(success=True)
                self._mutators.update(success=True)
                result = current
                steps = 0

        return result.data

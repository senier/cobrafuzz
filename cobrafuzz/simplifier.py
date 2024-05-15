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


def _metrics(data: bytes) -> list[int]:
    return [len(data), len([n for n in data if n == ord("\n")])]


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
            if not self._output_dir.exists():
                self._output_dir.mkdir()
            out_filename = self._output_dir / in_filename.name
            with in_filename.open("rb") as in_f, out_filename.open("wb") as out_f:
                data = in_f.read()
                try:
                    simplified = self._simplify(data)
                except common.InvalidSampleError:
                    logging.warning("Invalid sample: %s", in_filename.name)
                    continue

                if not simplified:
                    logging.info("Could not simplify %s", in_filename.name)
                    out_f.write(data)
                    continue

                logging.info("Simplified %s", in_filename.name)
                out_f.write(simplified)

    def _simplify(self, data: bytes) -> bytes:
        steps = 0
        result = current_data = data
        previous_metrics: Optional[list[int]] = None

        while steps <= self._steps:
            steps += 1

            modify, self._last_rands = self._mutators.sample()

            try:
                with disable_logging():
                    self._target(current_data)
            except Exception as e:  # noqa: BLE001
                covered = util.covered(e.__traceback__, 1)
                current_metrics = _metrics(current_data)
                if previous_metrics is None:
                    original_covered = covered
                    previous_metrics = current_metrics
                    continue
            else:
                if not previous_metrics:
                    raise common.InvalidSampleError("No exception for sample")
                current_data = modify(result, self._last_rands)
                continue

            if covered != original_covered:
                current_data = modify(result, self._last_rands)
                continue

            diff_metrics = list(zip(current_metrics, previous_metrics))
            no_decline = all(p >= c for c, p in diff_metrics)
            improvement = any(p > c for c, p in diff_metrics)

            if no_decline and improvement:
                self._last_rands.update(success=True)
                self._mutators.update(success=True)
                result = current_data
                previous_metrics = current_metrics
                steps = 0

            current_data = modify(result, self._last_rands)

        return result

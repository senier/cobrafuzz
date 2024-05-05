from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Optional

from cobrafuzz import common, util


def _simplify_remove_line(
    data: bytes,
    rand: util.Params,
) -> bytes:
    lines = data.split(b"\n")
    assert isinstance(rand.pos, util.AdaptiveRange)
    pos = rand.pos.sample(lower=1, upper=len(lines))
    return b"\n".join(lines[0 : pos - 1] + lines[pos:])


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
            population=[(_simplify_remove_line, util.Params(pos=util.AdaptiveRange()))],
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
                result = current_data
                previous_metrics = current_metrics
                steps = 0

            current_data = modify(result, self._last_rands)

        return result

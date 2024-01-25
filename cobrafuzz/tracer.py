from __future__ import annotations

import collections
import sys
from types import FrameType
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from _typeshed import TraceFunction

prev_line = 0
prev_filename = ""
data: collections.defaultdict[str, set[tuple[int, int]]] = collections.defaultdict(set)

_secondary_tracer: Optional[TraceFunction] = None


def initialize() -> None:
    global _secondary_tracer  # noqa: PLW0603
    _secondary_tracer = sys.gettrace()
    sys.settrace(_trace_dispatcher)


def get_coverage() -> int:
    return sum(map(len, data.values()))


def _primary_tracer(frame: FrameType, event: str, _: str) -> None:
    if event != "line":
        return

    global prev_line  # noqa: PLW0603
    global prev_filename  # noqa: PLW0603

    func_filename = frame.f_code.co_filename
    func_line_no = frame.f_lineno

    if func_filename != prev_filename:
        # We need a way to keep track of inter-files transfers,
        # and since we don't really care about the details of the coverage,
        # concatenating the two filenames in enough.
        data[func_filename + prev_filename].add((prev_line, func_line_no))
    else:
        data[func_filename].add((prev_line, func_line_no))

    prev_line = func_line_no
    prev_filename = func_filename


def _trace_dispatcher(frame: FrameType, event: str, args: str) -> TraceFunction:
    _primary_tracer(frame, event, args)
    if _secondary_tracer:
        _secondary_tracer(frame, event, args)

    return _trace_dispatcher

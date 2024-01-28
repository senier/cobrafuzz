from __future__ import annotations

import sys
from types import FrameType
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from _typeshed import TraceFunction

_prev_line: Optional[int] = None
_prev_filename: Optional[str] = None
_data: set[tuple[Optional[str], Optional[int], str, int]] = set()
_secondary_tracer: Optional[TraceFunction] = None


def initialize() -> None:
    reset()
    global _secondary_tracer  # noqa: PLW0603
    current_tracer = sys.gettrace()
    if current_tracer != _trace_dispatcher:
        _secondary_tracer = current_tracer
        sys.settrace(_trace_dispatcher)


def reset() -> None:
    global _prev_line  # noqa: PLW0603
    global _prev_filename  # noqa: PLW0603
    global _data  # noqa: PLW0603

    _prev_line = None
    _prev_filename = None
    _data = set()


def get_covered() -> set[tuple[Optional[str], Optional[int], str, int]]:
    return _data


def _primary_tracer(frame: FrameType, event: str, _args: str) -> None:
    if event != "line":
        return

    global _prev_filename  # noqa: PLW0603
    global _prev_line  # noqa: PLW0603

    _data.add((_prev_filename, _prev_line, frame.f_code.co_filename, frame.f_lineno))

    _prev_filename = frame.f_code.co_filename
    _prev_line = frame.f_lineno


def _trace_dispatcher(frame: FrameType, event: str, args: str) -> TraceFunction:
    _primary_tracer(frame, event, args)
    if _secondary_tracer:
        _secondary_tracer(frame, event, args)
        # Make sure secondary traces has not tampered with our trace function
        sys.settrace(_trace_dispatcher)

    return _trace_dispatcher

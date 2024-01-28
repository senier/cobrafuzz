# ruff: noqa: SLF001

from __future__ import annotations

import sys
from typing import Callable, Optional

import pytest

from cobrafuzz import tracer

_current_tracer: Optional[Callable[[FrameType, str, str], None]] = None


def _gettrace() -> Optional[Callable[[FrameType, str, str], None]]:
    return _current_tracer


def _settrace(tracer: Optional[Callable[[FrameType, str, str], None]]) -> None:
    global _current_tracer  # noqa: PLW0603
    _current_tracer = tracer


class Code:
    def __init__(self, filename: str):
        self.co_filename = filename


class FrameType:
    def __init__(self, name: str = "<invalid>", line: int = -1):
        self.f_code = Code(name)
        self.f_lineno = line


def test_primary_no_line(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as mp:
        mp.setattr(sys, "gettrace", _gettrace)
        mp.setattr(sys, "settrace", _settrace)

        sys.settrace(None)
        tracer.initialize()

        tracer._primary_tracer(
            frame=FrameType(),  # type: ignore[arg-type]
            event="no-line",
            _args="",
        )


def test_primary_line(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as mp:
        mp.setattr(sys, "gettrace", _gettrace)
        mp.setattr(sys, "settrace", _settrace)

        sys.settrace(None)
        tracer.initialize()

        assert tracer._prev_line is None
        assert tracer._prev_filename is None

        tracer._trace_dispatcher(
            frame=FrameType(name="test_1.py", line=100),  # type: ignore[arg-type]
            event="line",
            args="",
        )

        assert tracer._prev_line == 100
        assert tracer._prev_filename == "test_1.py"
        assert tracer.get_covered() == {(None, None, "test_1.py", 100)}

        tracer._trace_dispatcher(
            frame=FrameType(name="test_1.py", line=101),  # type: ignore[arg-type]
            event="line",
            args="",
        )

        assert tracer._prev_line == 101
        assert tracer._prev_filename == "test_1.py"
        assert tracer.get_covered() == {
            (None, None, "test_1.py", 100),
            ("test_1.py", 100, "test_1.py", 101),
        }

        tracer._trace_dispatcher(
            frame=FrameType(name="test_2.py", line=10),  # type: ignore[arg-type]
            event="line",
            args="",
        )

        assert tracer._prev_line == 10
        assert tracer._prev_filename == "test_2.py"
        assert tracer.get_covered() == {
            (None, None, "test_1.py", 100),
            ("test_1.py", 100, "test_1.py", 101),
            ("test_1.py", 101, "test_2.py", 10),
        }


def test_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as mp:
        mp.setattr(sys, "gettrace", _gettrace)
        mp.setattr(sys, "settrace", _settrace)

        tracer.initialize()

        tracer._trace_dispatcher(
            frame=FrameType(name="test_1.py", line=100),  # type: ignore[arg-type]
            event="line",
            args="",
        )
        assert tracer.get_covered() == {
            (None, None, "test_1.py", 100),
        }

        tracer.reset()

        tracer._trace_dispatcher(
            frame=FrameType(name="test_1.py", line=100),  # type: ignore[arg-type]
            event="line",
            args="",
        )
        assert tracer.get_covered() == {
            (None, None, "test_1.py", 100),
        }


def test_secondary_tracer(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    def local_tracer(_frame: FrameType, event: str, _args: str) -> None:
        events.append(event)

    with monkeypatch.context() as mp:
        mp.setattr(sys, "gettrace", _gettrace)
        mp.setattr(sys, "settrace", _settrace)

        _settrace(local_tracer)
        assert _gettrace() == local_tracer

        tracer.initialize()
        assert _gettrace() == tracer._trace_dispatcher  # type: ignore[comparison-overlap]

        tracer._trace_dispatcher(
            frame=FrameType(name="test_1.py", line=100),  # type: ignore[arg-type]
            event="line",
            args="",
        )

        assert tracer.get_covered() == {
            (None, None, "test_1.py", 100),
        }

        assert _gettrace() == tracer._trace_dispatcher  # type: ignore[comparison-overlap]


def test_secondary_tracer_resets_tracer(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    def secondary_tracer(_frame: FrameType, event: str, _args: str) -> None:
        events.append(event)
        _settrace(secondary_tracer)

    with monkeypatch.context() as mp:
        mp.setattr(sys, "gettrace", _gettrace)
        mp.setattr(sys, "settrace", _settrace)

        _settrace(secondary_tracer)
        assert _gettrace() == secondary_tracer

        tracer.initialize()
        assert _gettrace() == tracer._trace_dispatcher  # type: ignore[comparison-overlap]

        tracer._trace_dispatcher(
            frame=FrameType(name="test_1.py", line=100),  # type: ignore[arg-type]
            event="line",
            args="",
        )

        assert tracer.get_covered() == {
            (None, None, "test_1.py", 100),
        }

        assert _gettrace() == tracer._trace_dispatcher  # type: ignore[comparison-overlap]

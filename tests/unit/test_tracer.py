# ruff: noqa: SLF001

from cobrafuzz import tracer


class Code:
    def __init__(self, filename: str):
        self.co_filename = filename


class FrameType:
    def __init__(self, name: str = "<invalid>", line: int = -1):
        self.f_code = Code(name)
        self.f_lineno = line


def test_primary_no_line() -> None:
    tracer._primary_tracer(
        frame=FrameType(),  # type: ignore[arg-type]
        event="no-line",
        _args="",
    )


def test_primary_line() -> None:
    tracer._trace_dispatcher(
        frame=FrameType(name="test_1.py", line=100),  # type: ignore[arg-type]
        event="line",
        args="",
    )

    assert tracer._prev_line == 100
    assert tracer._prev_filename == "test_1.py"
    assert tracer.get_coverage() == 1

    tracer._trace_dispatcher(
        frame=FrameType(name="test_1.py", line=101),  # type: ignore[arg-type]
        event="line",
        args="",
    )

    assert tracer._prev_line == 101
    assert tracer._prev_filename == "test_1.py"
    assert tracer.get_coverage() == 2

    tracer._trace_dispatcher(
        frame=FrameType(name="test_2.py", line=10),  # type: ignore[arg-type]
        event="line",
        args="",
    )

    assert tracer._prev_line == 10
    assert tracer._prev_filename == "test_2.py"
    assert tracer.get_coverage() == 3

    assert list(tracer._data.items()) == [
        ("test_1.py", {(100, 101), (0, 100)}),
        ("test_2.pytest_1.py", {(101, 10)}),
    ]

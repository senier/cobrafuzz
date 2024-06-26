# ruff: noqa: SLF001
from __future__ import annotations

import copy
import logging
import multiprocessing as mp
from pathlib import Path
from typing import Callable, Optional, Tuple, cast

import dill  # type: ignore[import-untyped]
import pytest

from cobrafuzz import common, simplifier, util
from tests import utils

ArgsType = Tuple[
    bytes,
    utils.DummyQueue[simplifier.Metrics],
    utils.DummyQueue[simplifier.Metrics],
]


@pytest.mark.parametrize(
    ("data", "start", "end", "expected"),
    [
        (
            b"""\
            line1
            """,
            1,
            1,
            b"""\
            """,
        ),
        (
            b"""\
            line1
            line2
            line3
            """,
            1,
            1,
            b"""\
            line2
            line3
            """,
        ),
        (
            b"""\
            line1
            line2
            line3
            """,
            2,
            2,
            b"""\
            line1
            line3
            """,
        ),
        (
            b"""\
            line1
            line2
            line3
            """,
            3,
            3,
            b"""\
            line1
            line2
            """,
        ),
        (
            b"""\
            line1
            line2
            line3
            line4
            line5
            """,
            3,
            4,
            b"""\
            line1
            line2
            line5
            """,
        ),
        (
            b"""\
            line1
            line2
            line3
            """,
            1,
            3,
            b"""\
            """,
        ),
    ],
)
def test_remove_lines(data: bytes, start: int, end: int, expected: bytes) -> None:
    result = simplifier._simplify_remove_lines(
        data,
        util.Params(
            start=utils.StaticRand(start),
            end=utils.StaticRand(end),
        ),
    )
    assert result == bytearray(expected)


@pytest.mark.parametrize(
    ("data", "start", "length", "expected"),
    [
        (
            b"line1",
            0,
            1,
            b"ine1",
        ),
        (
            b"line1",
            2,
            1,
            b"lie1",
        ),
        (
            b"line1",
            4,
            1,
            b"line",
        ),
        (
            b"""\
            line1
            line2
            """,
            30,
            1,
            b"""\
            line1
            ine2
            """,
        ),
        (
            b"""\
            line1
            line2
            """,
            16,
            1,
            b"""\
            line
            line2
            """,
        ),
        (
            b"""\
            line1
            line2
            """,
            17,
            1,
            b"""\
            line1
            line2
            """,
        ),
        (
            b"""\
            line1
            line2
            """,
            17,
            2,
            b"""\
            line1
            line2
            """,
        ),
        (
            b"""\
            line1
            line2
            """,
            6,
            2,
            b"""\
            line1
            line2
            """,
        ),
        (
            b"""\
            line1
            line2
            """,
            6,
            10,
            b"""\
            line1
            line2
            """,
        ),
        (
            b"""\
            line1
            line2
            """,
            6,
            7,
            b"""\
            line1
            line2
            """,
        ),
        (
            b"""\
            line1
            line2
            """,
            20,
            6,
            b"""\
            line1
            line2
            """,
        ),
        (
            b"""\
            line1
            line2
            """,
            30,
            2,
            b"""\
            line1
            ne2
            """,
        ),
    ],
)
def test_remove_characters(data: bytes, start: int, length: int, expected: bytes) -> None:
    result = simplifier._simplify_remove_characters(
        data,
        util.Params(
            start=utils.StaticRand(start),
            length=utils.StaticRand(length),
        ),
    )
    assert result == bytearray(expected)


@pytest.mark.parametrize(
    ("data", "pos", "expected"),
    [
        (
            b"line1",
            0,
            b"line",
        ),
        (
            b"""line1
            line2
            line1
            """,
            0,
            b"""line
            line2
            line
            """,
        ),
        (
            b"""Some_Tag
            Unrelated
            Some_Tag
            """,
            0,
            b"""Som_Tag
            Unrelated
            Som_Tag
            """,
        ),
        (
            b"""Some_Tag
            Unrelated
            Some_Tag
            """,
            1,
            b"""Some_Ta
            Unrelated
            Some_Ta
            """,
        ),
        (
            b"""Some_Tag;
            Unrelated;
            Some_Tag;
            """,
            2,
            b"""Some_Tag;
            Unrelate;
            Some_Tag;
            """,
        ),
    ],
)
def test_shorten_token(data: bytes, pos: int, expected: bytes) -> None:
    result = simplifier._simplify_shorten_token(
        data,
        util.Params(
            pos=utils.StaticRand(pos),
            pattern=utils.StaticRand(1),
        ),
    )
    assert result == bytearray(expected)


@pytest.mark.parametrize("create_output_dir", [True, False])
def test_simplify_loop(
    create_output_dir: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    crash_dir = tmp_path / "crash"
    output_dir = tmp_path / "output"

    (crash_dir / "ignored_dir").mkdir(parents=True)
    (crash_dir / "01-simp").write_bytes(b"simplified")
    (crash_dir / "02-original").write_bytes(b"data")

    if create_output_dir:
        output_dir.mkdir()

    s = simplifier.Simp(  # pragma: no cover
        crash_dir=crash_dir,
        output_dir=output_dir,
        target=lambda _: None,
    )

    with monkeypatch.context() as m:
        m.setattr(s, "_simplify", lambda d: d if d.startswith(b"simp") else None)
        s.simplify()

    assert output_dir.exists()
    assert not (output_dir / "ignored_dir").exists()
    assert (output_dir / "01-simp").read_bytes() == b"simplified"
    assert (output_dir / "02-original").read_bytes() == b"data"


def test_simplify_invalid_sample(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    crash_dir = tmp_path / "crash"
    crash_dir.mkdir()
    output_dir = tmp_path / "output"

    (crash_dir / "unrelated").write_bytes(b"unrelated")
    (crash_dir / "invalid").write_bytes(b"invalid")

    with monkeypatch.context() as m:
        s = simplifier.Simp(  # pragma: no cover
            crash_dir=crash_dir,
            output_dir=output_dir,
            target=lambda _: None,
        )
        m.setattr(
            s,
            "_simplify",
            lambda d: utils.do_raise(
                common.InvalidSampleError,
                cond=(b"invalid" in d),
                message="Invalid sample",
            ),
        )
        with caplog.at_level(logging.INFO):
            s.simplify()
        del s

    assert "Could not simplify unrelated" in caplog.text
    assert "Invalid sample: invalid" in caplog.text


def test_simplify_already_simplified(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    crash_dir = tmp_path / "crash"
    output_dir = tmp_path / "output"

    crash_dir.mkdir()
    output_dir.mkdir()
    (crash_dir / "01-simp").write_bytes(b"simplified")
    (output_dir / "01-simp").write_bytes(b"already simplified")

    s = simplifier.Simp(  # pragma: no cover
        crash_dir=crash_dir,
        output_dir=output_dir,
        target=lambda _: None,
    )

    with monkeypatch.context() as m, caplog.at_level(logging.INFO):
        m.setattr(
            s,
            "_simplify",
            lambda d: d if d.startswith(b"simp") else None,
        )  # pragma: no cover
        s.simplify()

    assert output_dir.exists()
    assert (output_dir / "01-simp").read_bytes() == b"already simplified"

    assert "Already simplified: 01-simp" in caplog.text, caplog.text


def test_metrics_copy() -> None:
    current = simplifier.Metrics(b"AB")
    previous = current
    current = simplifier.Metrics(b"A")
    assert previous < current, f"{current=}, {previous=}"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"", [0, 0]),
        (b"single line", [11, 0]),
        (b"two\nlines", [9, 1]),
    ],
)
def test_metrics_values(data: bytes, expected: list[int]) -> None:
    assert simplifier.Metrics(data).metrics == expected


@pytest.mark.parametrize(
    ("less", "more", "improved"),
    [
        (b"", b"x", True),
        (b"x", b"x\ny", True),
        (b"x", "xy", True),
        (b"x", "x", False),
        (b"x", "", False),
        (b"xy", "x", False),
        (b"x\ny", b"x", False),
    ],
)
def test_metrics_comp(less: bytes, more: bytes, improved: bool) -> None:
    assert (simplifier.Metrics(more) < simplifier.Metrics(less)) == improved


def target(data: bytes) -> None:
    if not data.startswith(b"START"):
        return
    if not data.endswith(b"END"):
        return
    if b"CRASH" in data:
        raise AttributeError
    if b"BOOM" in data:
        raise AttributeError


@pytest.mark.parametrize(
    "data",
    [
        b"START",
        b"END",
        b"""START
        END""",
    ],
    ids=range(1, 4),
)
def test_simplify_no_crash(
    tmp_path: Path,
    data: bytes,
) -> None:
    s = simplifier.Simp(  # pragma: no cover
        crash_dir=tmp_path / "crash",
        output_dir=tmp_path / "output",
        target=target,
    )
    with pytest.raises(common.InvalidSampleError, match="^No exception for sample$"):
        s._simplify(data)


@pytest.mark.parametrize(
    ("data", "expected", "mutator"),
    [
        (
            b"""START
            CRASH
            END""",
            None,
            lambda data, _: data,
        ),
        (
            b"""START
            UNRELATED
            CRASH
            END""",
            b"""START
            CRASH
            END""",
            lambda data, _: b"\n".join(d for d in data.split(b"\n") if b"UNRELATED" not in d),
        ),
        (
            b"""START
            CRASH
            END""",
            None,
            lambda data, _: b"\n".join(d for d in data.split(b"\n") if b"CRASH" not in d),
        ),
        (
            b"""START
            CRASH
            BOOM
            END""",
            None,
            lambda data, _: b"\n".join(d for d in data.split(b"\n") if b"CRASH" not in d),
        ),
    ],
    ids=range(1, 5),
)
def test_simplification(
    data: bytes,
    expected: Optional[bytes],
    mutator: Callable[[bytes, util.Params], bytes],
) -> None:
    mutators: util.AdaptiveChoiceBase[
        tuple[
            Callable[[bytes, util.Params], bytes],
            util.Params,
        ]
    ] = util.AdaptiveChoiceBase(population=[(mutator, util.Params())])
    request_queue: mp.Queue[Optional[simplifier.Metrics]] = mp.Queue()
    result_queue: mp.Queue[Optional[simplifier.Metrics]] = mp.Queue()
    baseline = simplifier.run_target(target=target, data=data)

    request_queue.put(baseline)
    request_queue.put(None)
    simplifier.simplifier(
        target_bytes=dill.dumps(target),
        request_queue=request_queue,
        result_queue=result_queue,
        mutators=mutators,
    )

    result = result_queue.get()
    if result is None:
        assert expected is None
    else:
        assert result.data == expected


def test_terminate_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    def target(_: bytes) -> None:
        pass  # pragma: no cover

    args: ArgsType = (
        b"deadbeef",
        utils.DummyQueue(),
        utils.DummyQueue(),
    )

    workers: list[tuple[utils.DummyProcess[ArgsType], utils.DummyQueue[simplifier.Metrics]]] = [
        (utils.DummyProcess(target=target, args=args), utils.DummyQueue()),
        (utils.DummyProcess(target=target, args=args), utils.DummyQueue()),
    ]

    with monkeypatch.context() as p:
        p.setattr(mp, "get_context", lambda _: utils.DummyContext(wid=0))
        s = simplifier.Simp(crash_dir=Path("/"), output_dir=Path("/"), target=target)
        p.setattr(s, "_workers", workers)
        assert not cast(utils.DummyQueue[simplifier.Metrics], s._result_queue).canceled
        assert all(
            not w[0].terminated and not w[0].joined and w[0].timeout is None and not w[1].canceled
            for w in workers
        )
        s.terminate_workers()
        assert cast(utils.DummyQueue[simplifier.Metrics], s._result_queue).canceled
        assert all(
            w[0].terminated and w[0].joined and w[0].timeout == 1 and w[1].canceled for w in workers
        )

        previous_workers = copy.copy(workers)
        s.terminate_workers()
        assert workers == previous_workers


def test_simplify_inner_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    def target(_: bytes) -> None:
        pass  # pragma: no cover

    def run_target(_target: Callable[[bytes], None], data: bytes) -> Optional[simplifier.Metrics]:
        return simplifier.Metrics(data, set())

    args: ArgsType = (
        b"deadbeef",
        utils.DummyQueue(),
        utils.DummyQueue(),
    )

    workers: list[tuple[utils.DummyProcess[ArgsType], utils.DummyQueue[simplifier.Metrics]]] = [
        (utils.DummyProcess(target=target, args=args), utils.DummyQueue()),
        (utils.DummyProcess(target=target, args=args), utils.DummyQueue(length=1)),
    ]

    value_1 = b"aaaaaa"
    value_2 = b"aaaaa"

    result_queue: utils.DummyQueue[simplifier.Metrics] = utils.DummyQueue()
    result_queue.put(simplifier.Metrics(value_1, coverage=set()))
    result_queue.put(simplifier.Metrics(value_2, coverage=set()))

    # Make second worker queue full
    workers[1][1].put(simplifier.Metrics(data=b"unrelated", coverage=set()))

    with monkeypatch.context() as p:
        p.setattr(simplifier, "run_target", run_target)
        s = simplifier.Simp(crash_dir=Path("/"), output_dir=Path("/"), target=target, max_time=1)
        p.setattr(s, "_result_queue", result_queue)
        p.setattr(s, "_workers", workers)

        assert s._simplify(value_1) == value_2
        assert not workers[0][1].empty()
        assert workers[0][1].get().data == value_2

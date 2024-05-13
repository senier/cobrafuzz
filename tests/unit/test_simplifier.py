# ruff: noqa: SLF001
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

import pytest

from cobrafuzz import common, simplifier, util
from tests.utils import StaticRand, do_raise


@pytest.mark.parametrize(
    ("data", "pos", "expected"),
    [
        (
            b"""\
            line1
            """,
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
            b"""\
            line1
            line2
            """,
        ),
    ],
)
def test_remove_line(data: bytes, pos: int, expected: bytes) -> None:
    result = simplifier._simplify_remove_line(
        data,
        util.Params(
            pos=StaticRand(pos),
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
            start=StaticRand(start),
            length=StaticRand(length),
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
            pos=StaticRand(pos),
            pattern=StaticRand(1),
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

    s = simplifier.Simp(  # pragma: no cover
        crash_dir=crash_dir,
        output_dir=output_dir,
        target=lambda _: None,
    )

    with monkeypatch.context() as m:
        m.setattr(
            s,
            "_simplify",
            lambda d: do_raise(
                common.InvalidSampleError,
                cond=(b"invalid" in d),
                message="Invalid sample",
            ),
        )
        with caplog.at_level(logging.INFO):
            s.simplify()

    assert "Could not simplify unrelated" in caplog.text
    assert "Invalid sample: invalid" in caplog.text


def test_metrics() -> None:
    assert simplifier._metrics(b"") == [0, 0]
    assert simplifier._metrics(b"single line") == [11, 0]
    assert simplifier._metrics(b"two\nlines") == [9, 1]


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
        steps=10,
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
            b"""START
            CRASH
            END""",
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
            b"""START
            CRASH
            END""",
            lambda data, _: b"\n".join(d for d in data.split(b"\n") if b"CRASH" not in d),
        ),
        (
            b"""START
            CRASH
            BOOM
            END""",
            b"""START
            CRASH
            BOOM
            END""",
            lambda data, _: b"\n".join(d for d in data.split(b"\n") if b"CRASH" not in d),
        ),
    ],
    ids=range(1, 5),
)
def test_simplify(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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

    s = simplifier.Simp(  # pragma: no cover
        crash_dir=tmp_path / "crash",
        output_dir=tmp_path / "output",
        target=target,
        steps=10,
    )
    with monkeypatch.context() as m:
        m.setattr(s, "_mutators", mutators)
        assert s._simplify(data) == expected

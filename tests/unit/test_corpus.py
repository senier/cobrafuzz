from __future__ import annotations

import hashlib
import secrets
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import chisquare

from cobrafuzz import corpus


def test_length() -> None:
    c = corpus.Corpus()
    assert c.length == 1


def test_add_file_constructor(tmpdir: Path) -> None:
    filename = Path(tmpdir) / "input.dat"
    with filename.open("wb") as f:
        f.write(b"deadbeef")
    c = corpus.Corpus(dirs=[filename])
    assert c._inputs == [bytearray(b"deadbeef"), bytearray(0)]  # noqa: SLF001


def test_add_files_constructor(tmpdir: Path) -> None:
    basedir = Path(tmpdir) / "inputs"
    basedir.mkdir()
    (basedir / "subdir").mkdir()

    with (basedir / "f1").open("wb") as f:
        f.write(b"deadbeef")
    with (basedir / "f2").open("wb") as f:
        f.write(b"deadc0de")

    c = corpus.Corpus(dirs=[basedir])
    assert c._inputs == [  # noqa: SLF001
        bytearray(b"deadc0de"),
        bytearray(b"deadbeef"),
        bytearray(0),
    ]


def test_create_dir_constructor(tmpdir: Path) -> None:
    dirname = Path(tmpdir) / "input"
    c = corpus.Corpus(dirs=[dirname])
    assert dirname.exists()
    assert dirname.is_dir()
    assert c._inputs == [bytearray(0)]  # noqa: SLF001


def test_rand_uniform() -> None:
    assert corpus._rand(0) == 0  # noqa: SLF001
    assert corpus._rand(1) == 0  # noqa: SLF001

    data = [corpus._rand(10) for _ in range(1, 1000000)]  # noqa: SLF001
    result = chisquare(f_obs=list(np.bincount(data)))
    assert result.pvalue > 0.05


def test_rand_exponential() -> None:
    expected = [round(200000 / 2 ** (n + 1)) for n in range(32)]
    data = list(
        np.bincount(
            [corpus._rand_exp() for _ in range(sum(expected))],  # noqa: SLF001
            minlength=32,
        ),
    )

    # There should be more than 13 samples in each bin,
    # c.f. https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chisquare.html
    # Starting at the position *before* the element that is <= 13, bin all remaining elements.
    index = (
        min(
            next(i for i, v in enumerate(data) if v < 13),
            next(i for i, v in enumerate(expected) if v < 13),
        )
        - 1
    )
    data = data[:index] + [sum(data[index:])]
    expected = expected[:index] + [sum(expected[index:])]

    result = chisquare(f_obs=data, f_exp=expected)
    assert result.pvalue > 0.05, result


def test_choose_length() -> None:
    n = 1000
    lengths = [corpus._choose_len(n) for _ in range(10000)]  # noqa: SLF001

    assert n > 32
    assert len([v for v in lengths if v < 1]) == 0
    assert len([v for v in lengths if v > n]) == 0

    data = [
        len([v for v in lengths if 1 <= v <= 8]),
        len([v for v in lengths if 9 <= v <= 32]),
        len([v for v in lengths if 33 <= v <= n]),
    ]

    # Expected distribution for range 1..8, 9..32 and 33..n
    expected = [
        round((0.9 + 0.0225 + (8 / (100 * n))) * sum(data)),
        round((0.0675 + (24 / (100 * n))) * sum(data)),
        round(((n - 32) / (100 * n)) * sum(data)),
    ]

    result = chisquare(f_obs=data, f_exp=expected)
    assert result.pvalue > 0.05, result


def test_put_corpus_not_saved() -> None:
    c = corpus.Corpus()
    c.put(bytearray(b"deadbeef"))
    assert c._inputs == [bytearray(0), bytearray(b"deadbeef")]  # noqa: SLF001


def test_put_corpus_saved(tmpdir: Path) -> None:
    c = corpus.Corpus(dirs=[Path(tmpdir)])
    c.put(bytearray(b"deadbeef"))
    outfile = Path(tmpdir) / hashlib.sha256(b"deadbeef").hexdigest()
    assert c._inputs == [bytearray(0), bytearray(b"deadbeef")]  # noqa: SLF001
    assert outfile.exists()
    with outfile.open("rb") as of:
        assert of.read() == b"deadbeef"


def test_mutate_remove_range_of_bytes_fail() -> None:
    res = bytearray()
    assert not corpus._mutate_remove_range_of_bytes(res)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "start", "length", "expected"),
    [
        (b"0123456789", 0, 1, b"123456789"),
    ],
)
def test_mutate_remove_range_of_bytes_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    start: int,
    length: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:
        mp.setattr(corpus, "_rand", lambda _: start)
        mp.setattr(corpus, "_choose_len", lambda _: length)
        assert corpus._mutate_remove_range_of_bytes(tmp)  # noqa: SLF001
        assert tmp == expected


@pytest.mark.parametrize(
    ("data", "start", "length", "expected"),
    [
        (b"0123456789", 0, 5, b"XXXXX0123456789"),
        (b"0123456789", 10, 5, b"0123456789XXXXX"),
        (b"0123456789", 5, 5, b"01234XXXXX56789"),
    ],
)
def test_mutate_insert_range_of_bytes_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    start: int,
    length: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:
        mp.setattr(secrets, "token_bytes", lambda n: n * b"X")
        mp.setattr(corpus, "_rand", lambda _: start)
        mp.setattr(corpus, "_choose_len", lambda _: length)
        assert corpus._mutate_insert_range_of_bytes(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_duplicate_range_of_bytes_fail() -> None:
    data = bytearray(b"")
    assert not corpus._mutate_duplicate_range_of_bytes(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "start", "length", "dest", "expected"),
    [
        (b"0123456789", 0, 5, 10, b"012345678901234"),
        (b"0123456789", 0, 5, 0, b"012340123456789"),
        (b"0123456789", 0, 5, 5, b"012340123456789"),
        (b"0123456789", 4, 3, 10, b"0123456789456"),
        (b"0123456789", 4, 3, 0, b"4560123456789"),
        (b"0123456789", 4, 3, 5, b"0123445656789"),
    ],
)
def test_mutate_duplicate_range_of_bytes_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    start: int,
    length: int,
    dest: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:

        def rand(_: int) -> int:
            if not rand.second:  # type: ignore[attr-defined]
                rand.second = True  # type: ignore[attr-defined]
                return start
            rand.second = None  # type: ignore[attr-defined]
            return dest

        rand.second = None  # type: ignore[attr-defined]

        mp.setattr(corpus, "_rand", rand)
        mp.setattr(corpus, "_choose_len", lambda _: length)
        assert corpus._mutate_duplicate_range_of_bytes(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_copy_range_of_bytes_fail() -> None:
    data = bytearray(b"")
    assert not corpus._mutate_copy_range_of_bytes(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "start", "length", "dest", "expected"),
    [
        (b"0123456789", 0, 3, 5, b"0123401289"),
        (b"0123456789", 0, 1, 9, b"0123456780"),
        (b"0123456789", 4, 3, 0, b"4563456789"),
        (b"0123456789", 4, 3, 5, b"0123445689"),
        (b"0123456789", 4, 0, 5, b"0123456789"),
    ],
)
def test_mutate_copy_range_of_bytes_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    start: int,
    length: int,
    dest: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:

        def rand(_: int) -> int:
            if not rand.second:  # type: ignore[attr-defined]
                rand.second = True  # type: ignore[attr-defined]
                return start
            rand.second = None  # type: ignore[attr-defined]
            return dest

        rand.second = None  # type: ignore[attr-defined]

        mp.setattr(corpus, "_rand", rand)
        mp.setattr(corpus, "_choose_len", lambda _: length)
        assert corpus._mutate_copy_range_of_bytes(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_bit_flip_fail() -> None:
    data = bytearray(b"")
    assert not corpus._mutate_bit_flip(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "byte", "bit", "expected"),
    [
        (b"0123456789", 0, 0, b"1123456789"),
        (b"0123456789", 0, 4, b" 123456789"),
        (b"0123456789", 9, 0, b"0123456788"),
        (b"0123456789", 9, 6, b"012345678y"),
    ],
)
def test_mutate_bit_flip_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    byte: int,
    bit: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    # This would confuse our mocked _rand function below
    assert len(data) != 8, "data length must not be 8 in this test"

    with monkeypatch.context() as mp:
        mp.setattr(corpus, "_rand", lambda n: bit if n == 8 else byte)
        assert corpus._mutate_bit_flip(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_flip_random_bits_of_random_byte_fail() -> None:
    data = bytearray(b"")
    assert not corpus._mutate_flip_random_bits_of_random_byte(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "byte", "value", "expected"),
    [
        (b"0123456789", 0, 124, b"M123456789"),
        (b"0123456789", 5, 117, b"01234C6789"),
        (b"0123456789", 9, 121, b"012345678C"),
    ],
)
def test_mutate_flip_random_bits_of_random_byte_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    byte: int,
    value: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    # This would confuse our mocked _rand function below
    assert len(data) != 255, "data length must not be 255 in this test"

    with monkeypatch.context() as mp:
        mp.setattr(corpus, "_rand", lambda n: value if n == 255 else byte)
        assert corpus._mutate_flip_random_bits_of_random_byte(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_swap_two_bytes_fail() -> None:
    data = bytearray(b"")
    assert not corpus._mutate_swap_two_bytes(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "source", "dest", "expected"),
    [
        (b"0123456789", 0, 9, b"9123456780"),
        (b"0123456789", 9, 0, b"9123456780"),
        (b"0123456789", 0, 5, b"5123406789"),
        (b"0123456789", 5, 9, b"0123496785"),
        (b"0123456789", 0, 0, b"0123456789"),
        (b"0123456789", 5, 5, b"0123456789"),
        (b"0123456789", 9, 9, b"0123456789"),
    ],
)
def test_mutate_swap_two_bytes(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    source: int,
    dest: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    with monkeypatch.context() as mp:

        def rand(_: int) -> int:
            if not rand.second:  # type: ignore[attr-defined]
                rand.second = True  # type: ignore[attr-defined]
                return source
            rand.second = None  # type: ignore[attr-defined]
            return dest

        rand.second = None  # type: ignore[attr-defined]

        mp.setattr(corpus, "_rand", rand)
        assert corpus._mutate_swap_two_bytes(tmp)  # noqa: SLF001
        assert tmp == expected


def test_mutate_add_subtract_from_a_byte_fail() -> None:
    data = bytearray(b"")
    assert not corpus._mutate_swap_two_bytes(data)  # noqa: SLF001


@pytest.mark.parametrize(
    ("data", "position", "value", "expected"),
    [
        (b"0123456789", 0, 0, b"0123456789"),
        (b"0123456789", 0, 1, b"1123456789"),
        (b"0123456789", 0, 255, b"/123456789"),
        (b"0123456789", 5, 2, b"0123476789"),
        (b"0123456789", 5, 254, b"0123436789"),
        (b"0123456789", 9, 20, b"012345678M"),
        (b"0123456789", 9, 236, b"012345678%"),
    ],
)
def test_mutate_add_subtract_from_a_byte_success(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    position: int,
    value: int,
    expected: bytes,
) -> None:
    tmp = bytearray(data)

    # This would confuse our mocked _rand function below
    assert len(data) != 2**8, "data length must not be 2**8 in this test"

    with monkeypatch.context() as mp:
        mp.setattr(corpus, "_rand", lambda n: value if n == 2**8 else position)
        assert corpus._mutate_add_subtract_from_a_byte(tmp)  # noqa: SLF001
        assert tmp == expected

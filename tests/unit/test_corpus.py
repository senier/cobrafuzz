from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from scipy.stats import chisquare

import cobrafuzz.corpus


class Corpus(cobrafuzz.corpus.Corpus):
    @property
    def inputs(self) -> list[bytearray]:
        return self._inputs

    @staticmethod
    def rand(n: int) -> int:
        return Corpus._rand(n)

    @staticmethod
    def rand_exp() -> int:
        return Corpus._rand_exp()

    @staticmethod
    def choose_len(n: int) -> int:
        return Corpus._choose_len(n)


def test_length() -> None:
    c = Corpus()
    assert c.length == 1


def test_add_file_constructor(tmpdir: Path) -> None:
    filename = Path(tmpdir) / "input.dat"
    with filename.open("wb") as f:
        f.write(b"deadbeef")
    c = Corpus(dirs=[filename])
    assert c.inputs == [bytearray(b"deadbeef"), bytearray(0)]


def test_add_files_constructor(tmpdir: Path) -> None:
    basedir = Path(tmpdir) / "inputs"
    basedir.mkdir()
    (basedir / "subdir").mkdir()

    with (basedir / "f1").open("wb") as f:
        f.write(b"deadbeef")
    with (basedir / "f2").open("wb") as f:
        f.write(b"deadc0de")

    c = Corpus(dirs=[basedir])
    assert c.inputs == [bytearray(b"deadc0de"), bytearray(b"deadbeef"), bytearray(0)]


def test_create_dir_constructor(tmpdir: Path) -> None:
    dirname = Path(tmpdir) / "input"
    c = Corpus(dirs=[dirname])
    assert dirname.exists()
    assert dirname.is_dir()
    assert c.inputs == [bytearray(0)]


def test_rand_uniform() -> None:
    assert Corpus.rand(0) == 0
    assert Corpus.rand(1) == 0

    data = [Corpus.rand(10) for _ in range(1, 1000000)]
    result = chisquare(f_obs=list(np.bincount(data)))
    assert result.pvalue > 0.05


def test_rand_exponential() -> None:
    expected = [round(200000 / 2 ** (n + 1)) for n in range(32)]
    data = list(np.bincount([Corpus.rand_exp() for _ in range(sum(expected))], minlength=32))

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
    lengths = [Corpus.choose_len(n) for _ in range(10000)]

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
    c = Corpus()
    c.put(bytearray(b"deadbeef"))
    assert c.inputs == [bytearray(0), bytearray(b"deadbeef")]


def test_put_corpus_saved(tmpdir: Path) -> None:
    c = Corpus(dirs=[Path(tmpdir)])
    c.put(bytearray(b"deadbeef"))
    outfile = Path(tmpdir) / hashlib.sha256(b"deadbeef").hexdigest()
    assert c.inputs == [bytearray(0), bytearray(b"deadbeef")]
    assert outfile.exists()
    with outfile.open("rb") as of:
        assert of.read() == b"deadbeef"

from pythonfuzz import corpus


def test_remove() -> None:
    """Test if copy function works as intended in remove operation."""

    res = bytearray(b"abcdefg")

    pos0 = 4
    pos1 = 5

    corpus.Corpus.copy(res, res, pos1, pos0)

    res = res[: len(res) - (pos1 - pos0)]
    assert res == b"abcdfg"


def test_insert() -> None:
    """Test if copy function works as intended in insert operation."""

    res = bytearray(b"abcdefg")
    pos = 3
    n = 5

    for _ in range(n):
        res.append(0)

    corpus.Corpus.copy(res, res, pos, pos + n)

    for k in range(n):
        res[pos + k] = ord("Z")

    assert res == b"abcZZZZZdefg"


def test_duplicate() -> None:
    """Test if copy function works as intended in duplicate operation."""

    res = bytearray(b"abcdefg")

    src = 4
    dst = 5
    n = 2

    tmp = bytearray(n)
    corpus.Corpus.copy(res, tmp, src, 0)
    assert tmp == b"ef"

    for _ in range(n):
        res.append(0)
    corpus.Corpus.copy(res, res, dst, dst + n)
    for k in range(n):
        res[dst + k] = tmp[k]
    assert res == b"abcdeeffg"


def test_copy() -> None:
    """Test if copy function works as intended in copy operation."""

    res = bytearray(b"abcdefg")

    src = 4
    dst = 5
    n = 2

    corpus.Corpus.copy(res, res, src, dst, src + n)
    assert res == b"abcdeef"

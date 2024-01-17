import pytest

from pythonfuzz import fuzzer


def test_find_crash():
    def fuzz(buf):
        return True

    with pytest.raises(SystemExit, match="^0$"):
        fuzzer.Fuzzer(fuzz, runs=100).start()

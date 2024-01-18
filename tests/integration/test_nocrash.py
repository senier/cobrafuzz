import pytest

from pythonfuzz import fuzzer


def test_find_crash() -> None:
    def fuzz(_: bytes) -> None:
        pass

    with pytest.raises(SystemExit, match="^0$"):
        fuzzer.Fuzzer(fuzz, runs=100).start()

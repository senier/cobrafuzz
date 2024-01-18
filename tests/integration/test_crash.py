import pytest

from pythonfuzz import fuzzer


class NewExceptionError(Exception):
    pass


def test_find_crash() -> None:
    def fuzz(_: bytes) -> None:
        raise NewExceptionError

    with pytest.raises(SystemExit, match="^76$"):
        fuzzer.Fuzzer(fuzz, timeout=5, runs=1).start()

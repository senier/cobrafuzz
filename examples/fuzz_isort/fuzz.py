# mypy: disable-error-code="attr-defined"

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import contextlib

    import isort

    with contextlib.suppress(UnicodeDecodeError):
        isort.code(buf.decode("ascii"))


if __name__ == "__main__":
    fuzz()

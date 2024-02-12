# mypy: disable-error-code="attr-defined"

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import contextlib
    import zlib

    with contextlib.suppress(zlib.error):
        zlib.decompress(buf)


if __name__ == "__main__":
    fuzz()

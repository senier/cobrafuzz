# mypy: disable-error-code="import-untyped,attr-defined"

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import contextlib

    import idna

    with contextlib.suppress(UnicodeDecodeError, ValueError):
        idna.decode(buf)
        idna.encode(buf)


if __name__ == "__main__":
    fuzz()

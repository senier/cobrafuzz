# mypy: disable-error-code="import-untyped,attr-defined"

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import contextlib

    from furl import furl

    with contextlib.suppress(UnicodeDecodeError, ValueError):
        furl(buf.decode("ascii"))


if __name__ == "__main__":
    fuzz()

# mypy: disable-error-code="import-untyped,attr-defined"

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import contextlib

    from purl import URL

    with contextlib.suppress(UnicodeDecodeError, ValueError):
        URL(buf.decode("ascii")).as_string()


if __name__ == "__main__":
    fuzz()

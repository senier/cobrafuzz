# mypy: disable-error-code="import-untyped,attr-defined"

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import contextlib

    from dateutil.parser import ParserError, parse

    with contextlib.suppress(UnicodeDecodeError, ValueError, OverflowError, TypeError, ParserError):
        parse(buf.decode("utf-8"))


if __name__ == "__main__":
    fuzz()

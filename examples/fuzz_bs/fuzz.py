# mypy: disable-error-code="import-untyped"


from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import contextlib

    from bs4 import BeautifulSoup, builder

    with contextlib.suppress(UnicodeDecodeError, builder.ParserRejectedMarkup):
        BeautifulSoup(buf.decode(), "html.parser")


if __name__ == "__main__":
    fuzz()

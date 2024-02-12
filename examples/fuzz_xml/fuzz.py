from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import contextlib
    from xml.etree import ElementTree
    from xml.etree.ElementTree import ParseError

    with contextlib.suppress(UnicodeDecodeError, ParseError):
        ElementTree.fromstring(buf.decode())  # noqa: S314


if __name__ == "__main__":
    fuzz()

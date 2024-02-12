from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    from html.parser import HTMLParser

    try:
        parser = HTMLParser()
        parser.feed(buf.decode("ascii"))
    except UnicodeDecodeError:
        pass


if __name__ == "__main__":
    fuzz()

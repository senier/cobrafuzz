from html.parser import HTMLParser

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf):
    try:
        string = buf.decode("ascii")
        parser = HTMLParser()
        parser.feed(string)
    except UnicodeDecodeError:
        pass


if __name__ == "__main__":
    fuzz()

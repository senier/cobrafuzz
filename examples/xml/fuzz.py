from xml.etree import ElementTree
from xml.etree.ElementTree import ParseError

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    try:
        string = buf.decode("utf-8")
        ElementTree.fromstring(string)  # noqa: S314
    except (UnicodeDecodeError, ParseError):
        pass


if __name__ == "__main__":
    fuzz()

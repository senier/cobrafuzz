import xml.etree.ElementTree as et
from xml.etree.ElementTree import ParseError

from pythonfuzz.main import PythonFuzz


@PythonFuzz
def fuzz(buf):
    try:
        string = buf.decode("utf-8")
        et.fromstring(string)  # noqa: S314
    except (UnicodeDecodeError, ParseError):
        pass


if __name__ == "__main__":
    fuzz()

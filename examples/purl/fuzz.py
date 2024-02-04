# mypy: disable-error-code="attr-defined"

from cobrafuzz.main import CobraFuzz
from purl import URL


@CobraFuzz
def fuzz(buf: bytes) -> None:
    try:
        string = buf.decode("ascii")
        u = URL(string)
        u.as_string()
    except UnicodeDecodeError:
        pass


if __name__ == "__main__":
    fuzz()

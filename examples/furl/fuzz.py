# mypy: disable-error-code="attr-defined"

from cobrafuzz.main import CobraFuzz
from furl import furl


@CobraFuzz
def fuzz(buf: bytes) -> None:
    try:
        string = buf.decode("ascii")
        f = furl(string)
        f.path.normalize()
    except UnicodeDecodeError:
        pass


if __name__ == "__main__":
    fuzz()

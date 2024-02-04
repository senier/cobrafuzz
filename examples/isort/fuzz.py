# mypy: disable-error-code="attr-defined"
import isort
from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    try:
        string = buf.decode("ascii")
        isort.code(string)
    except UnicodeDecodeError:
        pass


if __name__ == "__main__":
    fuzz()

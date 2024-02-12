# mypy: disable-error-code="attr-defined"

import zlib

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    try:  # noqa: SIM105
        zlib.decompress(buf)
    except zlib.error:
        pass


if __name__ == "__main__":
    fuzz()
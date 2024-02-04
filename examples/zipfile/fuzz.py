# mypy: disable-error-code="attr-defined"

import io
import zipfile

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    f = io.BytesIO(buf)
    try:
        z = zipfile.ZipFile(f)
        z.testzip()
    except (zipfile.BadZipFile, zipfile.LargeZipFile):
        pass


if __name__ == "__main__":
    fuzz()

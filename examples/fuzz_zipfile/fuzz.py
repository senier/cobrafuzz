# mypy: disable-error-code="attr-defined"

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import io
    import zipfile

    f = io.BytesIO(buf)
    try:
        z = zipfile.ZipFile(f)
        z.testzip()
    except (zipfile.BadZipFile, zipfile.LargeZipFile):
        pass


if __name__ == "__main__":
    fuzz()

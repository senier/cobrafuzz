# mypy: disable-error-code="attr-defined"

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import aifc
    import io

    try:
        f = io.BytesIO(buf)
        a = aifc.open(f)
        a.readframes(1)
    except (EOFError, aifc.Error):
        pass


if __name__ == "__main__":
    fuzz()

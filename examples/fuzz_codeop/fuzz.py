# mypy: disable-error-code="attr-defined"

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import codeop
    import contextlib

    with contextlib.suppress(UnicodeDecodeError, ValueError, SyntaxError):
        codeop.compile_command(buf.decode("utf-8"))


if __name__ == "__main__":
    fuzz()

import codeop

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf):
    try:
        string = buf.decode("utf-8")
        codeop.compile_command(string)
    except (UnicodeDecodeError, ValueError, SyntaxError):
        pass


if __name__ == "__main__":
    fuzz()

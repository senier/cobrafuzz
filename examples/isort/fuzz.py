from cobrafuzz.main import CobraFuzz

import isort


@CobraFuzz
def fuzz(buf):
    try:
        string = buf.decode("ascii")
        isort.code(string)
    except UnicodeDecodeError:
        pass


if __name__ == "__main__":
    fuzz()

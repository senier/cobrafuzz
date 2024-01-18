from cobrafuzz.main import CobraFuzz

from purl import URL


@CobraFuzz
def fuzz(buf):
    try:
        string = buf.decode("ascii")
        u = URL(string)
        u.as_string()
    except UnicodeDecodeError:
        pass


if __name__ == "__main__":
    fuzz()

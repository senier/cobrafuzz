from purl import URL

from pythonfuzz.main import PythonFuzz


@PythonFuzz
def fuzz(buf):
    try:
        string = buf.decode("ascii")
        u = URL(string)
        u.as_string()
    except UnicodeDecodeError:
        pass


if __name__ == "__main__":
    fuzz()

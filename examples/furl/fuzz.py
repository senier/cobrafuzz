from furl import furl

from pythonfuzz.main import PythonFuzz


@PythonFuzz
def fuzz(buf):
    try:
        string = buf.decode("ascii")
        f = furl(string)
        f.path.normalize()
    except UnicodeDecodeError:
        pass


if __name__ == "__main__":
    fuzz()

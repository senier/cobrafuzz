import pytest
import zipfile
import io

from pythonfuzz import fuzzer


def test_find_crash():
    def fuzz(buf):
        f = io.BytesIO(buf)
        z = zipfile.ZipFile(f)
        z.testzip()

    with pytest.raises(SystemExit, match="^76$"):
        fuzzer.Fuzzer(fuzz).start()

# mypy: disable-error-code="import-untyped"

import requests
from bs4 import BeautifulSoup

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    try:
        url = buf.decode("ascii")
        page = requests.get(url, timeout=10)
        BeautifulSoup(page.text, "html.parser")
    except (UnicodeDecodeError, requests.RequestException):
        pass


if __name__ == "__main__":
    fuzz()

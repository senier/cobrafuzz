import requests
from bs4 import BeautifulSoup as bs
from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf):
    try:
        url = buf.decode("ascii")
        page = requests.get(url, timeout=10)
        bs(page.text, "html.parser")
    except (UnicodeDecodeError, requests.RequestException):
        pass


if __name__ == "__main__":
    fuzz()

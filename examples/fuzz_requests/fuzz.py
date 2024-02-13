#!/usr/bin/env python3

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(data: bytes) -> None:
    import contextlib

    import requests

    with contextlib.suppress(requests.exceptions.RequestException, ValueError, UnicodeDecodeError):
        requests.get(data, timeout=0.0001)


if __name__ == "__main__":
    fuzz()

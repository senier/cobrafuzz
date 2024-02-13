#!/usr/bin/env python3


from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(data: bytes) -> None:
    import charset_normalizer

    charset_normalizer.from_bytes(sequences=data).best()


if __name__ == "__main__":
    fuzz()

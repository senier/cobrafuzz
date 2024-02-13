# mypy: disable-error-code="import-not-found"

from cobrafuzz.main import CobraFuzz


@CobraFuzz
def fuzz(buf: bytes) -> None:
    import rflx.error
    import rflx.specification.parser

    try:
        p = rflx.specification.parser.Parser()
        p.parse_string(buf.decode())
        p.create_model()
    except (UnicodeDecodeError, rflx.error.RecordFluxError):
        pass


if __name__ == "__main__":
    fuzz()

class OutOfBoundsError(Exception):
    pass


def remove(data: bytearray, start: int, length: int) -> None:
    """
    Remove part of a bytearray.

    Arguments:
    ---------
    data: bytearray to modify.
    start: Start position of chunk to remove (inclusive).
    length: Number of bytes to remove.
    """
    if start >= len(data):
        raise OutOfBoundsError(f"Start out of range ({start=}, length={len(data)})")
    if start + length > len(data):
        raise OutOfBoundsError(f"End out of range (end={start + length - 1}, length={len(data)})")
    data[:] = data[:start] + data[start + length :]


def insert(data: bytearray, start: int, data_to_insert: bytes) -> None:
    """
    Insert data into bytearray.

    Arguments:
    ---------
    data: bytearray to modify.
    start: Position where to insert new data.
    data_to_insert: bytearray to insert.
    """
    if start > len(data):
        raise OutOfBoundsError("Start out of range")
    data[:] = data[:start] + data_to_insert + data[start:]

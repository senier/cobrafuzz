from __future__ import annotations

from typing import Callable, Optional

from cobrafuzz import util


def do_raise(e: type[BaseException], cond: bool = True, message: Optional[str] = None) -> None:
    if cond:
        raise e(message)


def mock_time() -> Callable[[], int]:
    current = 0

    def get_time() -> int:
        nonlocal current
        current += 1
        return current

    return get_time


class StaticRand(util.AdaptiveRange):
    def __init__(self, value: int) -> None:
        super().__init__()
        self._value = value

    def sample(self, lower: int, upper: int) -> int:  # noqa: ARG002
        return self._value

from __future__ import annotations

from typing import Callable, Generic, Optional, TypeVar

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


QueueType = TypeVar("QueueType")


class DummyQueue(Generic[QueueType]):
    def __init__(self, length: Optional[int] = None) -> None:
        self._data: list[QueueType] = []
        self.canceled = False
        self.length = length

    def put(self, item: QueueType) -> None:
        self._data.append(item)

    def get(self) -> QueueType:
        result = self._data[0]
        self._data = self._data[1:]
        return result

    def empty(self) -> bool:
        return len(self._data) == 0

    def full(self) -> bool:
        return self.length is not None and self.length <= len(self._data)

    def cancel_join_thread(self) -> None:
        self.canceled = True


ArgsType = TypeVar("ArgsType")


class DummyProcess(Generic[ArgsType]):
    def __init__(self, target: Callable[[bytes], None], args: ArgsType):
        self.target = target
        self.args = args
        self.terminated = False
        self.started = False
        self.joined = False
        self.timeout: Optional[int] = None

    def start(self) -> None:
        self.started = True

    def terminate(self) -> None:
        self.terminated = True

    def join(self, timeout: int) -> None:
        self.joined = True
        self.timeout = timeout


class DummyContext(Generic[ArgsType]):
    def __init__(
        self,
        wid: int,
    ):
        self._wid = wid

    def Queue(self, length: Optional[int] = None) -> DummyQueue[ArgsType]:  # noqa: N802
        return DummyQueue(length)

    def Process(  # noqa: N802
        self,
        target: Callable[[bytes], None],
        args: ArgsType,
    ) -> DummyProcess[ArgsType]:
        return DummyProcess(target=target, args=args)


def test_dummy_queue() -> None:
    assert not DummyQueue().full()
    assert DummyQueue().empty()
    assert not DummyQueue(1).full()
    assert DummyQueue(1).empty()

    dq: DummyQueue[int] = DummyQueue(1)
    dq.put(1)
    assert not dq.empty()
    assert dq.full()

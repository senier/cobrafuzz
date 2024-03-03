from __future__ import annotations

import logging
import multiprocessing as mp
import sys
from pathlib import Path

import pytest

import tests.utils
from cobrafuzz import fuzzer, state as st
from cobrafuzz.main import CobraFuzz


def worker_crash(
    wid: int,
    _target_bytes: bytes,
    _update_queue: mp.Queue[fuzzer.Update],
    result_queue: mp.Queue[fuzzer.StatusBase],
    _close_stdout: bool,
    _close_stderr: bool,
    _stat_frequency: int,
    _state: st.State,
) -> None:
    print("worker on stdout")  # noqa: T201
    print("worker on stderr", file=sys.stderr)  # noqa: T201
    result_queue.put(
        fuzzer.Error(
            wid=wid,
            runs=1000,
            data=b"deadbeef",
            covered={("a", 1, "b", 2)},
            message="worker crashed",
        ),
    )


def test_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with monkeypatch.context() as mp:
        mp.setattr(
            sys,
            "argv",
            [
                "main",
                "--crash-dir",
                str(tmp_path),
                "--max-runs",
                "500",
                "--max-crashes",
                "1",
            ],
        )
        mp.setattr(fuzzer, "worker", worker_crash)
        c = CobraFuzz(lambda _: None)  # pragma: no cover
        with pytest.raises(SystemExit, match="^1$"):
            c()


def test_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with monkeypatch.context() as mp:
        mp.setattr(
            sys,
            "argv",
            [
                "main",
                "--crash-dir",
                str(tmp_path),
                "--max-runs",
                "500",
                "--max-crashes",
                "1",
            ],
        )
        mp.setattr(logging, "info", lambda *_: tests.utils.do_raise(KeyboardInterrupt))
        c = CobraFuzz(func=lambda _: None)  # pragma: no cover
        with pytest.raises(SystemExit, match=r"^\nUser cancellation\. Exiting\.\n$"):
            c()

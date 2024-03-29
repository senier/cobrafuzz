from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import pytest

from cobrafuzz import state


def test_length() -> None:
    c = state.State()
    assert c.size == 1


def test_add_file_constructor(tmp_path: Path) -> None:
    filename = tmp_path / "input.dat"
    with filename.open("wb") as f:
        f.write(b"deadbeef")
    c = state.State(seeds=[filename])
    assert list(c._mutator._inputs) == [bytearray(b"deadbeef")]  # noqa: SLF001


def test_add_files_constructor(tmp_path: Path) -> None:
    basedir = tmp_path / "inputs"
    basedir.mkdir()
    (basedir / "subdir").mkdir()

    with (basedir / "f1").open("wb") as f:
        f.write(b"deadbeef")
    with (basedir / "f2").open("wb") as f:
        f.write(b"deadc0de")

    c = state.State(seeds=[basedir])
    assert sorted(c._mutator._inputs) == sorted(  # noqa: SLF001
        [
            bytearray(b"deadc0de"),
            bytearray(b"deadbeef"),
        ],
    )


def test_put_state_not_saved() -> None:
    c = state.State()
    c.put_input(bytearray(b"deadbeef"))
    assert list(c._mutator._inputs) == [bytearray(0), bytearray(b"deadbeef")]  # noqa: SLF001


def test_put_state_saved(tmp_path: Path) -> None:
    statefile = tmp_path / "state.json"
    c1 = state.State(file=statefile)
    c1.put_input(bytearray(b"deadbeef"))
    assert list(c1._mutator._inputs) == [bytearray(0), bytearray(b"deadbeef")]  # noqa: SLF001

    c1.save()
    assert statefile.exists()

    c2 = state.State(file=statefile)
    assert list(c2._mutator._inputs) == [  # noqa: SLF001
        bytearray(0),
        bytearray(0),
        bytearray(b"deadbeef"),
    ]


def test_generate_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    filename = tmp_path / "input.dat"
    with filename.open("wb") as f:
        f.write(b"deadbeef")
    c = state.State(seeds=[filename])
    with monkeypatch.context() as mp:
        mp.setattr(c._mutator, "_mutate", lambda buf: buf)  # noqa: SLF001
        assert c.get_input() == bytearray(b"deadbeef")
        assert c.get_input() == bytearray(b"deadbeef")


def test_fail_load_invalid_version(tmp_path: Path) -> None:
    filename = tmp_path / "state.json"
    with filename.open("w") as f:
        json.dump(obj={"version": 99999}, fp=f)
    with pytest.raises(
        state.LoadError,
        match=rf"^Invalid version in state file {filename} \(expected 1\)$",
    ):
        state.State(file=filename)


def test_fail_load_malformed_state_file(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    filename = tmp_path / "state.json"
    with filename.open("w") as f:
        f.write("MALFORMED!")
    with caplog.at_level(logging.INFO):
        state.State(file=filename)
    assert f"Malformed state file: {filename}" in caplog.text, caplog.text
    assert not filename.exists()


def test_fail_load_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    state.State(file=missing)
    assert not missing.exists()


def test_fail_load_invalid_file_path(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    with caplog.at_level(logging.INFO):
        state.State(file=tmp_path)
    assert f"[Errno 21] Is a directory: '{tmp_path}'" in caplog.text, caplog.text


@pytest.mark.parametrize("success", [True, False])
def test_update(monkeypatch: pytest.MonkeyPatch, success: bool) -> None:
    class MockMutator:
        def __init__(self) -> None:
            self.success: Optional[bool] = None

        def update(self, success: bool) -> None:
            self.success = success

    with monkeypatch.context() as mp:
        s = state.State()
        m = MockMutator()
        mp.setattr(s, "_mutator", m)
        s.update(success=success)
        assert m.success == success

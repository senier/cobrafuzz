import json
import logging
from pathlib import Path

import pytest

from cobrafuzz import corpus, state, util


def test_length() -> None:
    c = state.State()
    assert c.size == 1


def test_add_file_constructor(tmp_path: Path) -> None:
    filename = tmp_path / "input.dat"
    with filename.open("wb") as f:
        f.write(b"deadbeef")
    c = state.State(seeds=[filename])
    assert c._inputs == [bytearray(b"deadbeef")]  # noqa: SLF001


def test_add_files_constructor(tmp_path: Path) -> None:
    basedir = tmp_path / "inputs"
    basedir.mkdir()
    (basedir / "subdir").mkdir()

    with (basedir / "f1").open("wb") as f:
        f.write(b"deadbeef")
    with (basedir / "f2").open("wb") as f:
        f.write(b"deadc0de")

    c = state.State(seeds=[basedir])
    assert sorted(c._inputs) == sorted(  # noqa: SLF001
        [
            bytearray(b"deadc0de"),
            bytearray(b"deadbeef"),
        ],
    )


def test_put_state_not_saved() -> None:
    c = state.State()
    c.put_input(bytearray(b"deadbeef"))
    assert c._inputs == [bytearray(0), bytearray(b"deadbeef")]  # noqa: SLF001


def test_put_state_saved(tmp_path: Path) -> None:
    c1 = state.State()
    c1.put_input(bytearray(b"deadbeef"))
    assert c1._inputs == [bytearray(0), bytearray(b"deadbeef")]  # noqa: SLF001

    statefile = tmp_path / "state.json"
    c1.save(statefile)
    assert statefile.exists()

    c2 = state.State()
    c2.load(statefile)
    assert c2._inputs == [bytearray(0), bytearray(0), bytearray(b"deadbeef")]  # noqa: SLF001


def test_generate_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    filename = tmp_path / "input.dat"
    with filename.open("wb") as f:
        f.write(b"deadbeef")
    c = state.State(seeds=[filename])
    with monkeypatch.context() as mp:
        mp.setattr(corpus, "mutate", lambda buf, max_input_size: buf[:max_input_size])
        mp.setattr(util, "rand", lambda _: 0)
        assert c.get_input() == bytearray(b"deadbeef")
        assert c.get_input() == bytearray(b"deadbeef")


def test_fail_load_invalid_version(tmp_path: Path) -> None:
    filename = tmp_path / "state.json"
    with filename.open("w") as f:
        json.dump(obj={"version": 99999}, fp=f)
    c = state.State()
    with pytest.raises(
        state.LoadError,
        match=rf"^Invalid version in state file {filename} \(expected {c._VERSION}\)$",  # noqa: SLF001
    ):
        c.load(filename=filename)


def test_fail_load_malformed_state_file(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    filename = tmp_path / "state.json"
    with filename.open("w") as f:
        f.write("MALFORMED!")
    c = state.State()
    with caplog.at_level(logging.INFO):
        c.load(filename=filename)
    assert f"Malformed state file: {filename}" in caplog.text, caplog.text
    assert not filename.exists()


def test_fail_load_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    c = state.State()
    c.load(filename=missing)
    assert not missing.exists()


def test_fail_load_invalid_file_path(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    c = state.State()
    with caplog.at_level(logging.INFO):
        c.load(filename=tmp_path)
    assert f"[Errno 21] Is a directory: '{tmp_path}'" in caplog.text, caplog.text

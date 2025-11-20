from pathlib import Path

import pytest

from host.protocol.loader import ProtocolLoader


def _write(dirp: Path, name: str, text: str) -> None:
    (dirp / name).write_text(text, encoding="utf-8")


def _write_valid_protocol(dirp: Path) -> None:
    _write(dirp, "constants.yml", "protocol_version: 1\n")
    _write(dirp, "frames.yml", "frames: {}\n")
    _write(dirp, "header.yml", "header: []\n")
    _write(dirp, "commands.yml", "commands: {}\n")
    _write(dirp, "errors.yml", "errors: {}\n")


def test_load_all_requires_all_files(tmp_path: Path) -> None:
    _write_valid_protocol(tmp_path)
    (tmp_path / "frames.yml").unlink()

    loader = ProtocolLoader(tmp_path)

    with pytest.raises(FileNotFoundError):
        loader.load_all()


def test_load_all_populates_structures_and_hashes(tmp_path: Path) -> None:
    _write_valid_protocol(tmp_path)

    loader = ProtocolLoader(tmp_path)
    loader.load_all()

    assert loader.protocol_version() == 1
    assert loader.frames == {}
    assert loader.header == []
    assert loader.commands == {}
    assert loader.errors == {}

    assert set(loader.file_hashes) == set(loader.REQUIRED_FILES)
    for h in loader.file_hashes.values():
        assert isinstance(h, str) and len(h) == 64


def test_load_all_rejects_missing_frames_key(tmp_path: Path) -> None:
    _write_valid_protocol(tmp_path)
    _write(tmp_path, "frames.yml", "invalid: true\n")

    loader = ProtocolLoader(tmp_path)

    with pytest.raises(ValueError):
        loader.load_all()


def test_load_all_rejects_missing_header_key(tmp_path: Path) -> None:
    _write_valid_protocol(tmp_path)
    _write(tmp_path, "header.yml", "invalid: true\n")

    loader = ProtocolLoader(tmp_path)

    with pytest.raises(ValueError):
        loader.load_all()


def test_protocol_version_rejects_invalid_value(tmp_path: Path) -> None:
    _write_valid_protocol(tmp_path)
    _write(tmp_path, "constants.yml", "protocol_version: bad\n")

    loader = ProtocolLoader(tmp_path)
    loader.load_all()

    with pytest.raises(ValueError):
        loader.protocol_version()

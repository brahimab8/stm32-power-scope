from __future__ import annotations

import struct
import pytest

import host.protocol.core.defs as defs_mod


class FakeLoader:
    def __init__(self):
        self.constants = {"max_payload": 8, "cmd_none": 0}
        self.frames = {
            "ACK": {"code": 0x20, "min_payload": 0, "max_payload": 2},
            "NACK": {"code": 0x21, "min_payload": 0, "max_payload": 2},
        }
        self.header = [
            {"name": "magic", "type": "u16"},
            {"name": "type", "type": "u8"},
            {"name": "len", "type": "u8"},
        ]
        self.commands = {
            "PING": {"cmd_id": 1, "payload": [], "response_payload": []},
        }
        self.errors = {"UNKNOWN": 255, "BAD_CMD": 1}


def test_protocol_builds_header_struct_and_lookup_maps(monkeypatch):
    monkeypatch.setattr(defs_mod, "YAML_TO_STRUCT", {"u16": "H", "u8": "B"}, raising=False)

    p = defs_mod.Protocol(FakeLoader())

    assert p.header_fields == ["magic", "type", "len"]
    assert p.header_fmt == "<HBB".replace(" ", "")
    assert isinstance(p.header_struct, struct.Struct)

    assert p.frames_by_code[p.frames["ACK"]["code"]]["code"] == 0x20
    assert p.error_codes[255] == "UNKNOWN"
    assert p.error_codes[1] == "BAD_CMD"


def test_protocol_rejects_unknown_header_field_type(monkeypatch):
    loader = FakeLoader()
    loader.header = [{"name": "magic", "type": "nope"}]

    monkeypatch.setattr(defs_mod, "YAML_TO_STRUCT", {"u16": "H", "u8": "B"}, raising=False)

    with pytest.raises(ValueError):
        defs_mod.Protocol(loader)


def test_commands_by_id_builds_and_rejects_duplicates(monkeypatch):
    loader = FakeLoader()
    loader.commands = {
        "A": {"cmd_id": 7},
        "B": {"cmd_id": 7},
    }

    monkeypatch.setattr(defs_mod, "YAML_TO_STRUCT", {"u16": "H", "u8": "B"}, raising=False)

    with pytest.raises(ValueError):
        defs_mod.Protocol(loader)


def test_validate_payload_len_checks_bounds(monkeypatch):
    monkeypatch.setattr(defs_mod, "YAML_TO_STRUCT", {"u16": "H", "u8": "B"}, raising=False)

    p = defs_mod.Protocol(FakeLoader())

    ack = p.frames["ACK"]["code"]
    assert p.validate_payload_len(ack, 0) is True
    assert p.validate_payload_len(ack, 2) is True
    assert p.validate_payload_len(ack, 3) is False

    assert p.validate_payload_len(0x99, 0) is False


def test_get_command_def_unknown_raises(monkeypatch):
    monkeypatch.setattr(defs_mod, "YAML_TO_STRUCT", {"u16": "H", "u8": "B"}, raising=False)

    p = defs_mod.Protocol(FakeLoader())

    with pytest.raises(ValueError):
        p.get_command_def("NOPE")

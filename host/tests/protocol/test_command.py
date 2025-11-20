from __future__ import annotations

import struct
import pytest

import host.protocol.core.frames.command as cmd_mod


class FakeProto:
    def __init__(self):
        self.constants = {"cmd_none": 0, "max_payload": 64}
        self.frames = {"CMD": {"code": 0x01, "min_payload": 0, "max_payload": 8}}
        self._cmd_defs = {}

    def get_command_def(self, cmd_name: str) -> dict:
        return self._cmd_defs[cmd_name]

    def resolve_value(self, v, default=0):
        return v if v is not None else default


def test_next_seq_increments_and_never_returns_zero(monkeypatch):
    # Force a wrap scenario
    cmd_mod.CommandFrame._seq_counter = 0xFFFFFFFF

    s1 = cmd_mod.CommandFrame.next_seq()
    s2 = cmd_mod.CommandFrame.next_seq()

    assert s1 == 0xFFFFFFFF
    assert s2 == 1


def test_build_payload_packs_fields_in_order(monkeypatch):
    proto = FakeProto()
    proto._cmd_defs["SET"] = {
        "cmd_id": 7,
        "payload": [
            {"name": "a", "type": "u8"},
            {"name": "b", "type": "u16"},
        ],
    }

    monkeypatch.setattr(cmd_mod, "YAML_TO_STRUCT", {"u8": "B", "u16": "H"}, raising=False)

    payload = cmd_mod.CommandFrame.build_payload(proto, "SET", {"a": 0x11, "b": 0x2233})
    assert payload == struct.pack("<B", 0x11) + struct.pack("<H", 0x2233)


def test_build_payload_uses_field_value_when_present(monkeypatch):
    proto = FakeProto()
    proto._cmd_defs["PING"] = {
        "cmd_id": 1,
        "payload": [{"name": "x", "type": "u8", "value": 9}],
    }

    monkeypatch.setattr(cmd_mod, "YAML_TO_STRUCT", {"u8": "B"}, raising=False)

    payload = cmd_mod.CommandFrame.build_payload(proto, "PING", args={"x": 1})
    assert payload == struct.pack("<B", 9)


def test_build_payload_missing_arg_raises(monkeypatch):
    proto = FakeProto()
    proto._cmd_defs["SET"] = {
        "cmd_id": 7,
        "payload": [{"name": "a", "type": "u8"}],
    }

    monkeypatch.setattr(cmd_mod, "YAML_TO_STRUCT", {"u8": "B"}, raising=False)

    with pytest.raises(KeyError):
        cmd_mod.CommandFrame.build_payload(proto, "SET", args={})


def test_build_payload_unknown_type_raises(monkeypatch):
    proto = FakeProto()
    proto._cmd_defs["SET"] = {
        "cmd_id": 7,
        "payload": [{"name": "a", "type": "nope"}],
    }

    monkeypatch.setattr(cmd_mod, "YAML_TO_STRUCT", {"u8": "B"}, raising=False)

    with pytest.raises(ValueError):
        cmd_mod.CommandFrame.build_payload(proto, "SET", args={"a": 1})


def test_build_payload_enforces_cmd_frame_payload_bounds(monkeypatch):
    proto = FakeProto()
    proto.frames["CMD"]["min_payload"] = 2
    proto.frames["CMD"]["max_payload"] = 2

    proto._cmd_defs["SET"] = {
        "cmd_id": 7,
        "payload": [{"name": "a", "type": "u8"}],  # 1 byte
    }

    monkeypatch.setattr(cmd_mod, "YAML_TO_STRUCT", {"u8": "B"}, raising=False)

    with pytest.raises(ValueError):
        cmd_mod.CommandFrame.build_payload(proto, "SET", args={"a": 1})

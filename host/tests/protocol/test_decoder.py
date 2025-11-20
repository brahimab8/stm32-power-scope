from __future__ import annotations

import pytest

import host.protocol.core.decoder as dec_mod


class FakeProto:
    def __init__(self):
        self.constants = {"foo": 123, "cmd_none": 0}
        self.commands_by_id = {}


def test_resolve_value_int_returns_itself():
    proto = FakeProto()
    assert dec_mod.resolve_value(proto, 7, default=0) == 7


def test_resolve_value_constants_lookup():
    proto = FakeProto()
    assert dec_mod.resolve_value(proto, "constants:foo", default=0) == 123


def test_resolve_value_constants_missing_uses_default():
    proto = FakeProto()
    assert dec_mod.resolve_value(proto, "constants:missing", default=9) == 9


def test_resolve_value_unknown_returns_default():
    proto = FakeProto()
    assert dec_mod.resolve_value(proto, "other:foo", default=5) == 5


def test_decode_response_unknown_cmd_returns_raw_bytes():
    proto = FakeProto()
    out = dec_mod.decode_response(proto, cmd_id=99, payload=b"\x01\x02")
    assert out == {"raw": b"\x01\x02"}


def test_decode_response_decodes_scalar_fields(monkeypatch):
    proto = FakeProto()
    proto.commands_by_id[1] = {
        "response_payload": [
            {"name": "a", "type": "u8"},
            {"name": "b", "type": "u16"},
        ]
    }

    monkeypatch.setattr(dec_mod, "YAML_TO_STRUCT", {"u8": "B", "u16": "H"}, raising=False)

    payload = bytes([0x7F]) + (0x1234).to_bytes(2, "little")
    out = dec_mod.decode_response(proto, cmd_id=1, payload=payload)

    assert out == {"a": 0x7F, "b": 0x1234}


def test_decode_response_scalar_field_payload_too_short_raises(monkeypatch):
    proto = FakeProto()
    proto.commands_by_id[1] = {
        "response_payload": [{"name": "x", "type": "u16"}]
    }

    monkeypatch.setattr(dec_mod, "YAML_TO_STRUCT", {"u16": "H"}, raising=False)

    with pytest.raises(ValueError):
        dec_mod.decode_response(proto, cmd_id=1, payload=b"\x01")  # 1 byte < 2 bytes


def test_decode_response_array_of_struct_decodes_all_full_entries(monkeypatch):
    proto = FakeProto()
    proto.commands_by_id[2] = {
        "response_payload": [
            {
                "name": "items",
                "type": "array",
                "items": {
                    "type": "struct",
                    "fields": [
                        {"name": "x", "type": "u8"},
                        {"name": "y", "type": "u16"},
                    ],
                },
            }
        ]
    }

    monkeypatch.setattr(dec_mod, "YAML_TO_STRUCT", {"u8": "B", "u16": "H"}, raising=False)

    # Two full entries + 1 trailing byte (should be ignored for the array loop)
    entry1 = bytes([1]) + (100).to_bytes(2, "little")
    entry2 = bytes([2]) + (200).to_bytes(2, "little")
    payload = entry1 + entry2 + b"\xFF"

    out = dec_mod.decode_response(proto, cmd_id=2, payload=payload)
    assert out == {"items": [{"x": 1, "y": 100}, {"x": 2, "y": 200}]}


def test_decode_response_array_struct_unknown_field_type_raises(monkeypatch):
    proto = FakeProto()
    proto.commands_by_id[3] = {
        "response_payload": [
            {
                "name": "items",
                "type": "array",
                "items": {
                    "type": "struct",
                    "fields": [{"name": "x", "type": "unknown"}],
                },
            }
        ]
    }

    monkeypatch.setattr(dec_mod, "YAML_TO_STRUCT", {"u8": "B"}, raising=False)

    with pytest.raises(ValueError):
        dec_mod.decode_response(proto, cmd_id=3, payload=b"\x00")


def test_decode_response_unknown_array_format_returns_remaining_bytes(monkeypatch):
    proto = FakeProto()
    proto.commands_by_id[4] = {
        "response_payload": [
            {"name": "arr", "type": "array", "items": {"type": "not_struct"}}
        ]
    }

    monkeypatch.setattr(dec_mod, "YAML_TO_STRUCT", {"u8": "B"}, raising=False)

    payload = b"\xAA\xBB\xCC"
    out = dec_mod.decode_response(proto, cmd_id=4, payload=payload)
    assert out == {"arr": payload}


def test_decode_response_unknown_field_type_returns_remaining_bytes(monkeypatch):
    proto = FakeProto()
    proto.commands_by_id[5] = {
        "response_payload": [{"name": "rest", "type": "blob"}]
    }

    monkeypatch.setattr(dec_mod, "YAML_TO_STRUCT", {"u8": "B"}, raising=False)

    payload = b"\x10\x20"
    out = dec_mod.decode_response(proto, cmd_id=5, payload=payload)
    assert out == {"rest": payload}

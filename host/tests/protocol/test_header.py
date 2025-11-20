from __future__ import annotations

import struct
import pytest

from host.protocol.core.header import parse_header, build_header


class _HdrStruct:
    def __init__(self):
        self._st = struct.Struct("<HBBH")  # magic, type, ver, len

    @property
    def size(self) -> int:
        return self._st.size

    def pack(self, *vals):
        return self._st.pack(*vals)

    def unpack(self, raw: bytes):
        return self._st.unpack(raw)


class FakeProto:
    def __init__(self):
        self.header_struct = _HdrStruct()
        self.header_fields = ["magic", "type", "ver", "len"]


def test_parse_header_rejects_wrong_size():
    proto = FakeProto()
    with pytest.raises(ValueError):
        parse_header(proto, b"\x00" * (proto.header_struct.size - 1))


def test_build_then_parse_round_trip():
    proto = FakeProto()

    fields = {"magic": 0xABCD, "type": 0x20, "ver": 1, "len": 5}
    raw = build_header(proto, fields)

    out = parse_header(proto, raw)
    assert out == fields


def test_build_header_missing_field_raises_key_error():
    proto = FakeProto()
    with pytest.raises(KeyError):
        build_header(proto, {"magic": 0xABCD, "type": 1, "ver": 0})

from __future__ import annotations

import struct
import pytest

from host.protocol.core.frames.base import Frame


class FakeProto:
    def __init__(self):
        self.constants = {"cmd_none": 0, "magic": 0xABCD, "max_payload": 16}
        self.frames = {"ACK": {"code": 0x20}}
        self.frames_by_code = {
            0x20: {"min_payload": 0, "max_payload": 4},
        }

    def resolve_value(self, v, default=0):
        return v if v is not None else default

    def build_header(self, hdr_dict: dict) -> bytes:
        # Minimal deterministic header (doesn't have to match real wire format)
        # 2B magic + 1B type + 1B ver + 2B len + 4B seq + 4B ts + 1B cmd_id + 1B rsv = 16 bytes
        return struct.pack(
            "<HBBHII BB",
            hdr_dict["magic"],
            hdr_dict["type"],
            hdr_dict["ver"],
            hdr_dict["len"],
            hdr_dict["seq"],
            hdr_dict["ts_ms"],
            hdr_dict["cmd_id"] & 0xFF,
            hdr_dict["rsv"] & 0xFF,
        )

    def crc16(self, data: bytes) -> int:
        # Deterministic CRC stub for testing composition
        return 0xBEEF


def test_unknown_frame_type_raises():
    proto = FakeProto()
    with pytest.raises(ValueError):
        Frame(proto=proto, frame_type=0x99, seq=1, payload=b"")


def test_payload_too_short_raises():
    proto = FakeProto()
    proto.frames_by_code[0x20] = {"min_payload": 2, "max_payload": 4}
    with pytest.raises(ValueError):
        Frame(proto=proto, frame_type=0x20, seq=1, payload=b"\x00")


def test_payload_too_long_raises():
    proto = FakeProto()
    with pytest.raises(ValueError):
        Frame(proto=proto, frame_type=0x20, seq=1, payload=b"\x00" * 5)


def test_defaults_cmd_id_and_masks_ts_ms_and_seq():
    proto = FakeProto()
    f = Frame(proto=proto, frame_type=0x20, seq=0x1_0000_0001, payload=b"", ts_ms=0x1_0000_0002)

    assert f.seq == 1
    assert f.ts_ms == 2
    assert f.cmd_id == proto.constants["cmd_none"]


def test_encode_appends_crc_and_uses_proto_build_header():
    proto = FakeProto()
    payload = b"\xAA\xBB"
    f = Frame(proto=proto, frame_type=0x20, seq=7, payload=payload, ts_ms=123, cmd_id=3, rsv=9)

    raw = f.encode()

    # CRC is appended little-endian
    assert raw[-2:] == struct.pack("<H", 0xBEEF)

    # Header produced by build_header is at the start
    header = raw[:-2 - len(payload)]
    assert header == proto.build_header(
        {
            "magic": proto.constants["magic"],
            "type": 0x20,
            "ver": 0,
            "len": len(payload),
            "cmd_id": 3,
            "rsv": 9,
            "seq": 7,
            "ts_ms": 123,
        }
    )

    # Payload follows header
    assert raw[len(header) : len(header) + len(payload)] == payload


def test_type_name_matches_frames_mapping_and_falls_back():
    proto = FakeProto()
    f = Frame(proto=proto, frame_type=0x20, seq=1, payload=b"")
    assert f.type_name == "ACK"

    f2 = Frame(proto=proto, frame_type=0x20, seq=2, payload=b"")
    proto.frames = {}  # remove mapping
    assert f2.type_name == "TYPE_32"

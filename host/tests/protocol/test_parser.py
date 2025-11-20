from __future__ import annotations

from dataclasses import dataclass

import pytest

import host.protocol.core.parser as parser_mod


class _HdrStruct:
    def __init__(self, size: int):
        self.size = size


@dataclass
class _FakeStreamFrame:
    proto: object
    seq: int
    payload: bytes
    ts_ms: int
    rsv: int


class _FakeResponseFrame:
    def __init__(self):
        self.cmd_id = None
        self.rsv = None
        self._raw_header = b""
        self._hdr = {}

    @classmethod
    def from_bytes(cls, proto, hdr_bytes: bytes, payload: bytes):
        f = cls()
        f.payload = payload
        return f


class FakeProtocol:
    def __init__(self):
        self.header_struct = _HdrStruct(size=8)
        self.constants = {
            "magic": 0xABCD,
            "max_payload": 16,
            "cmd_none": 0,
        }
        self.frames = {"STREAM": {"code": 0x10}}

        self._crc_expected = None
        self._validate_ok = True
        self._parse_header_impl = None

    def parse_header(self, hdr_bytes: bytes) -> dict:
        if self._parse_header_impl:
            return self._parse_header_impl(hdr_bytes)
        raise RuntimeError("parse_header not configured")

    def crc16(self, data: bytes) -> int:
        if self._crc_expected is None:
            raise RuntimeError("crc16 not configured")
        return self._crc_expected

    def validate_payload_len(self, ftype: int, payload_len: int) -> bool:
        return self._validate_ok


def _build_frame_bytes(
    *,
    magic: int,
    hdr_size: int,
    payload: bytes,
    rx_crc: int,
) -> bytes:
    magic_bytes = magic.to_bytes(2, "little")
    hdr_rest = b"\x00" * (hdr_size - 2)
    crc_bytes = int(rx_crc).to_bytes(2, "little")
    return magic_bytes + hdr_rest + payload + crc_bytes


def test_get_frame_returns_none_until_header_available():
    proto = FakeProtocol()
    parser = parser_mod.FrameParser(proto)

    parser.feed(b"\xAA")
    assert parser.get_frame() is None


def test_sync_magic_discards_bytes_before_magic():
    proto = FakeProtocol()
    parser = parser_mod.FrameParser(proto)

    junk = b"\x01\x02\x03"
    parser.feed(junk + (0xABCD).to_bytes(2, "little") + b"\x00" * (proto.header_struct.size - 2))

    proto._parse_header_impl = lambda hb: {"type": 1, "seq": 1, "len": 1, "ts_ms": 0, "cmd_id": 0, "rsv": 0}
    assert parser.get_frame() is None

    assert bytes(parser.buffer[:2]) == (0xABCD).to_bytes(2, "little")


def test_header_parse_failure_skips_two_bytes():
    proto = FakeProtocol()
    parser = parser_mod.FrameParser(proto)

    parser.feed((0xABCD).to_bytes(2, "little") + b"\x11" * (proto.header_struct.size - 2))
    proto._parse_header_impl = lambda hb: (_ for _ in ()).throw(ValueError("bad header"))

    before = bytes(parser.buffer)
    assert parser.get_frame() is None
    after = bytes(parser.buffer)

    assert after == before[2:]


def test_payload_too_large_skips_magic():
    proto = FakeProtocol()
    parser = parser_mod.FrameParser(proto)

    proto._parse_header_impl = lambda hb: {"type": 1, "seq": 1, "len": proto.constants["max_payload"] + 1, "ts_ms": 0}
    parser.feed((0xABCD).to_bytes(2, "little") + b"\x00" * (proto.header_struct.size - 2))

    before = bytes(parser.buffer)
    assert parser.get_frame() is None
    after = bytes(parser.buffer)

    assert after == before[2:]


def test_crc_mismatch_skips_magic():
    proto = FakeProtocol()
    parser = parser_mod.FrameParser(proto)

    payload = b"\x01\x02\x03"
    rx_crc = 0x1234
    proto._crc_expected = 0x9999

    proto._parse_header_impl = lambda hb: {"type": 1, "seq": 7, "len": len(payload), "ts_ms": 0, "cmd_id": 0, "rsv": 0}

    parser.feed(
        _build_frame_bytes(
            magic=proto.constants["magic"],
            hdr_size=proto.header_struct.size,
            payload=payload,
            rx_crc=rx_crc,
        )
    )

    before = bytes(parser.buffer)
    assert parser.get_frame() is None
    after = bytes(parser.buffer)

    assert after == before[2:]


def test_invalid_payload_len_drops_entire_frame():
    proto = FakeProtocol()
    parser = parser_mod.FrameParser(proto)

    payload = b"\xAA\xBB"
    rx_crc = 0x2222
    proto._crc_expected = rx_crc
    proto._validate_ok = False

    proto._parse_header_impl = lambda hb: {"type": 1, "seq": 9, "len": len(payload), "ts_ms": 0, "cmd_id": 0, "rsv": 0}

    raw = _build_frame_bytes(
        magic=proto.constants["magic"],
        hdr_size=proto.header_struct.size,
        payload=payload,
        rx_crc=rx_crc,
    )
    parser.feed(raw)

    assert parser.get_frame() is None
    assert bytes(parser.buffer) == b""


def test_parses_stream_frame_and_clears_buffer(monkeypatch):
    proto = FakeProtocol()
    parser = parser_mod.FrameParser(proto)

    monkeypatch.setattr(parser_mod, "StreamFrame", _FakeStreamFrame)
    monkeypatch.setattr(parser_mod, "ResponseFrame", _FakeResponseFrame)

    payload = b"\x10\x20\x30"
    rx_crc = 0xBEEF
    proto._crc_expected = rx_crc
    proto._validate_ok = True

    proto._parse_header_impl = lambda hb: {
        "type": proto.frames["STREAM"]["code"],
        "seq": 3,
        "len": len(payload),
        "ts_ms": 123,
        "cmd_id": 77,
        "rsv": 5,
    }

    parser.feed(
        _build_frame_bytes(
            magic=proto.constants["magic"],
            hdr_size=proto.header_struct.size,
            payload=payload,
            rx_crc=rx_crc,
        )
    )

    frame = parser.get_frame()
    assert isinstance(frame, _FakeStreamFrame)
    assert frame.seq == 3
    assert frame.payload == payload
    assert frame.ts_ms == 123
    assert frame.rsv == 5
    assert bytes(parser.buffer) == b""


def test_parses_response_frame_and_sets_cmd_id_rsv_and_diagnostics(monkeypatch):
    proto = FakeProtocol()
    parser = parser_mod.FrameParser(proto)

    monkeypatch.setattr(parser_mod, "StreamFrame", _FakeStreamFrame)
    monkeypatch.setattr(parser_mod, "ResponseFrame", _FakeResponseFrame)

    payload = b"\xDE\xAD"
    rx_crc = 0x4444
    proto._crc_expected = rx_crc
    proto._validate_ok = True

    hdr_dict = {
        "type": 0x22,
        "seq": 11,
        "len": len(payload),
        "ts_ms": 999,
        "cmd_id": 12,
        "rsv": 9,
    }
    proto._parse_header_impl = lambda hb: dict(hdr_dict)

    raw = _build_frame_bytes(
        magic=proto.constants["magic"],
        hdr_size=proto.header_struct.size,
        payload=payload,
        rx_crc=rx_crc,
    )
    parser.feed(raw)

    frame = parser.get_frame()
    assert isinstance(frame, _FakeResponseFrame)
    assert frame.cmd_id == 12
    assert frame.rsv == 9
    assert frame._raw_header == raw[: proto.header_struct.size]
    assert frame._hdr == hdr_dict
    assert bytes(parser.buffer) == b""

from __future__ import annotations

import pytest

import host.protocol.core.frames.response as resp_mod


class FakeProto:
    def __init__(self):
        self.constants = {"cmd_none": 0}
        self.frames = {
            "ACK": {"code": 0x20},
            "NACK": {"code": 0x21},
            "STREAM": {"code": 0x10},
        }
        self.errors = {"UNKNOWN": 255}
        self.error_codes = {1: "BAD_CMD", 2: "BAD_ARG"}

        self._hdr = None
        self._decode_calls = []

        # Used by Frame._validate_payload_length in base class
        self.frames_by_code = {
            0x20: {"min_payload": 0, "max_payload": 64},
            0x21: {"min_payload": 0, "max_payload": 64},
            0x10: {"min_payload": 0, "max_payload": 64},
            0x33: {"min_payload": 0, "max_payload": 64},
        }

    def parse_header(self, raw_header: bytes) -> dict:
        assert self._hdr is not None
        return dict(self._hdr)

    def decode_response(self, cmd_id: int, payload: bytes) -> dict:
        self._decode_calls.append((int(cmd_id), bytes(payload)))
        return {"cmd_id": int(cmd_id), "payload_len": len(payload)}

    def resolve_value(self, v, default=0):
        return v if v is not None else default

    def build_header(self, hdr_dict: dict) -> bytes:
        raise RuntimeError("not used in these tests")

    def crc16(self, data: bytes) -> int:
        raise RuntimeError("not used in these tests")


def test_response_frame_from_bytes_dispatches_ack():
    proto = FakeProto()
    proto._hdr = {"type": proto.frames["ACK"]["code"], "seq": 7, "ts_ms": 100, "cmd_id": 3, "rsv": 9}

    f = resp_mod.ResponseFrame.from_bytes(proto, raw_header=b"hdr", payload=b"\xAA")
    assert isinstance(f, resp_mod.AckFrame)
    assert f.frame_type == proto.frames["ACK"]["code"]
    assert f.seq == 7
    assert f.ts_ms == 100
    assert f.cmd_id == 3
    assert f.rsv == 9
    assert f.data == b"\xAA"


def test_ack_frame_decoded_calls_proto_decode_response():
    proto = FakeProto()
    proto._hdr = {"type": proto.frames["ACK"]["code"], "seq": 1, "ts_ms": 1, "cmd_id": 12, "rsv": 0}

    f = resp_mod.ResponseFrame.from_bytes(proto, raw_header=b"hdr", payload=b"\x01\x02")
    out = f.decoded

    assert out == {"cmd_id": 12, "payload_len": 2}
    assert proto._decode_calls == [(12, b"\x01\x02")]


def test_response_frame_from_bytes_dispatches_nack():
    proto = FakeProto()
    proto._hdr = {"type": proto.frames["NACK"]["code"], "seq": 2, "ts_ms": 200, "cmd_id": 5, "rsv": 1}

    f = resp_mod.ResponseFrame.from_bytes(proto, raw_header=b"hdr", payload=b"\x02")
    assert isinstance(f, resp_mod.NackFrame)
    assert f.frame_type == proto.frames["NACK"]["code"]
    assert f.seq == 2
    assert f.ts_ms == 200
    assert f.cmd_id == 5
    assert f.rsv == 1


def test_nack_error_code_and_error_mapping():
    proto = FakeProto()
    proto._hdr = {"type": proto.frames["NACK"]["code"], "seq": 2, "ts_ms": 200, "cmd_id": 5, "rsv": 0}

    f = resp_mod.ResponseFrame.from_bytes(proto, raw_header=b"hdr", payload=b"\x02\x99")
    assert f.error_code == 2
    assert f.error == {"code": 2, "name": "BAD_ARG"}


def test_nack_empty_payload_uses_unknown_fallback():
    proto = FakeProto()
    proto._hdr = {"type": proto.frames["NACK"]["code"], "seq": 2, "ts_ms": 200, "cmd_id": 5, "rsv": 0}

    f = resp_mod.ResponseFrame.from_bytes(proto, raw_header=b"hdr", payload=b"")
    assert f.error_code == 255
    assert f.error == {"code": 255, "name": "UNKNOWN"}


def test_response_frame_from_bytes_generic_fallback():
    proto = FakeProto()
    proto._hdr = {"type": 0x33, "seq": 9, "ts_ms": 999, "cmd_id": 1, "rsv": 7}

    f = resp_mod.ResponseFrame.from_bytes(proto, raw_header=b"hdr", payload=b"\x10")
    assert isinstance(f, resp_mod.ResponseFrame)
    assert not isinstance(f, resp_mod.AckFrame)
    assert not isinstance(f, resp_mod.NackFrame)

    assert f.frame_type == 0x33
    assert f.seq == 9
    assert f.ts_ms == 999
    assert f.cmd_id == 1
    assert f.rsv == 7


def test_stream_frame_requires_runtime_id_byte():
    proto = FakeProto()
    with pytest.raises(ValueError):
        resp_mod.StreamFrame(proto=proto, seq=1, payload=b"", ts_ms=0)


def test_stream_frame_splits_runtime_id_and_payload():
    proto = FakeProto()
    f = resp_mod.StreamFrame(proto=proto, seq=1, payload=b"\x05\xAA\xBB", ts_ms=10, rsv=3)

    assert f.sensor_runtime_id == 5
    assert f.payload == b"\xAA\xBB"
    assert f.get_raw_payload() == b"\xAA\xBB"
    assert f.frame_type == proto.frames["STREAM"]["code"]
    assert f.cmd_id == proto.constants["cmd_none"]
    assert f.rsv == 3

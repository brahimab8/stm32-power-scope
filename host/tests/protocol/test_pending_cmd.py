from __future__ import annotations

import pytest

from host.protocol._internal.pending_command import PendingCommand


class FakeProto:
    def __init__(self):
        self.frames = {"ACK": {"code": 0x20}, "NACK": {"code": 0x21}}


class FakeResp:
    def __init__(self, *, frame_type: int, payload: bytes = b"", decoded=None, data=None, error=None):
        self.proto = FakeProto()
        self.frame_type = frame_type
        self.payload = payload
        if decoded is not None:
            self.decoded = decoded
        if data is not None:
            self.data = data
        if error is not None:
            self.error = error


def test_set_result_timeout():
    p = PendingCommand(seq=1, cmd_name="PING", timeout_s=1.0)
    p.set_result(None, "timeout")
    assert p.wait(0) == {"status": "timeout"}


def test_set_result_send_failed():
    p = PendingCommand(seq=1, cmd_name="PING", timeout_s=1.0)
    p.set_result(None, "send_failed")
    assert p.wait(0) == {"status": "send_failed"}


def test_set_result_none_resp_unknown():
    p = PendingCommand(seq=1, cmd_name="PING", timeout_s=1.0)
    p.set_result(None, "ok")
    assert p.wait(0) == {"status": "unknown"}


def test_set_result_ack_prefers_decoded_property():
    p = PendingCommand(seq=1, cmd_name="GET", timeout_s=1.0)
    resp = FakeResp(frame_type=0x20, payload=b"\xAA", decoded={"x": 1})
    p.set_result(resp, "ok")
    assert p.wait(0) == {"status": "ok", "payload": {"x": 1}}


def test_set_result_ack_falls_back_to_data_then_payload():
    p1 = PendingCommand(seq=1, cmd_name="GET", timeout_s=1.0)
    resp1 = FakeResp(frame_type=0x20, payload=b"\xAA", data=b"\xBB")
    p1.set_result(resp1, "ok")
    assert p1.wait(0) == {"status": "ok", "payload": b"\xBB"}

    p2 = PendingCommand(seq=2, cmd_name="GET", timeout_s=1.0)
    resp2 = FakeResp(frame_type=0x20, payload=b"\xCC")
    p2.set_result(resp2, "ok")
    assert p2.wait(0) == {"status": "ok", "payload": b"\xCC"}


def test_set_result_ack_decode_fn_applied_to_bytes():
    p = PendingCommand(seq=1, cmd_name="GET", timeout_s=1.0)
    resp = FakeResp(frame_type=0x20, payload=b"\x01\x02")

    def decode_fn(b: bytes):
        return {"raw_sum": sum(b)}

    p.set_result(resp, "ok", decode_fn=decode_fn)
    assert p.wait(0) == {"status": "ok", "payload": {"raw_sum": 3}}


def test_set_result_ack_decode_fn_failure_returns_hex_raw():
    p = PendingCommand(seq=1, cmd_name="GET", timeout_s=1.0)
    resp = FakeResp(frame_type=0x20, payload=b"\xDE\xAD")

    def decode_fn(_b: bytes):
        raise ValueError("boom")

    p.set_result(resp, "ok", decode_fn=decode_fn)
    assert p.wait(0) == {"status": "ok", "payload": {"raw": "dead"}}


def test_set_result_nack_uses_error_property():
    p = PendingCommand(seq=1, cmd_name="SET", timeout_s=1.0)
    resp = FakeResp(frame_type=0x21, error={"code": 2, "name": "BAD_ARG"})
    p.set_result(resp, "fail")
    assert p.wait(0) == {"status": "fail", "error": {"code": 2, "name": "BAD_ARG"}}


def test_set_result_nack_error_property_exception_falls_back():
    p = PendingCommand(seq=1, cmd_name="SET", timeout_s=1.0)

    class RespWithBadError(FakeResp):
        @property
        def error(self):
            raise RuntimeError("nope")

    resp = RespWithBadError(frame_type=0x21)
    p.set_result(resp, "fail")
    assert p.wait(0) == {"status": "fail", "error": {"code": None, "name": "UNKNOWN"}}


def test_set_result_unknown_frame_type_returns_frame():
    p = PendingCommand(seq=1, cmd_name="X", timeout_s=1.0)
    resp = FakeResp(frame_type=0x99, payload=b"\x00")
    p.set_result(resp, "ok")
    out = p.wait(0)
    assert out["status"] == "unknown"
    assert out["frame"] is resp


def test_wait_pending_returns_pending():
    p = PendingCommand(seq=1, cmd_name="PING", timeout_s=1.0)
    assert p.wait(timeout=0.0) == {"status": "pending"}


def test_set_result_is_idempotent_once_done():
    p = PendingCommand(seq=1, cmd_name="PING", timeout_s=1.0)
    p.set_result(None, "timeout")
    p.set_result(None, "send_failed")  # should be ignored
    assert p.wait(0) == {"status": "timeout"}

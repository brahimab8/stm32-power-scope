# host/tests/test_protocol_engine.py
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

import host.protocol.engine as eng_mod


class FakeTransport:
    """Minimal TransportIO stub."""
    def __init__(self):
        self.writes: list[bytes] = []
        self.read_data: bytes = b""
        self.raise_on_write: Exception | None = None

    def write(self, data: bytes) -> int:
        if self.raise_on_write:
            raise self.raise_on_write
        self.writes.append(data)
        return len(data)

    def read(self, size: int) -> bytes:
        # Return whatever is staged (single-shot)
        data = self.read_data
        self.read_data = b""
        return data

    def flush(self) -> None:
        return None


class FakeProto:
    def __init__(self):
        self.frames = {
            "STREAM": {"code": 0x10},
            "ACK": {"code": 0x20},
            "NACK": {"code": 0x21},
        }
        self.constants = {"cmd_none": 0}

    def get_command_def(self, cmd_name: str) -> dict:
        return {"cmd_id": 1}

    def resolve_value(self, v, default):
        return v if v is not None else default

    def decode_response(self, cmd_id: int, payload: bytes) -> dict:
        # Default behavior: return a decoded dict (tests override via monkeypatch)
        return {"decoded": True, "cmd_id": cmd_id, "payload": payload.hex()}


class FakeParser:
    """
    Parser stub:
    - feed() records bytes fed
    - get_frame() yields a preloaded sequence of frames
    """
    def __init__(self, frames):
        self._frames = list(frames)
        self.fed: list[bytes] = []

    def feed(self, data: bytes) -> None:
        self.fed.append(data)

    def get_frame(self):
        if not self._frames:
            return None
        return self._frames.pop(0)


class FakePending:
    """
    PendingCommand stub capturing results that engine sets.
    Mimics the minimal API used by ProtocolEngine.
    """
    def __init__(self, seq: int, cmd_name: str, timeout_s: float, created_at: float = 0.0):
        self.seq = seq
        self.cmd_name = cmd_name
        self.timeout_s = timeout_s
        self.created_at = created_at
        self.result_calls = []  # (frame, status)

        self._callbacks = []

    def add_done_callback(self, cb):
        self._callbacks.append(cb)

    def set_result(self, frame, status: str, decode_fn=None):
        # In real PendingCommand, this would resolve a future; we only record.
        self.result_calls.append((frame, status))

        class _Fut:
            def result(self_nonlocal):
                # Minimal result dict shape used by the callback in engine.py
                if status == "ok":
                    return {"status": "ok", "payload": {}}
                return {"status": status, "payload": {}}

        for cb in self._callbacks:
            cb(_Fut())


class FakeCommandFrame:
    """CommandFrame stub used by send_cmd_async()."""
    def __init__(self, proto, cmd_name: str, args: dict):
        self.proto = proto
        self.cmd_name = cmd_name
        self.args = args
        self.seq = 123  # fixed seq for deterministic tests

    def encode(self) -> bytes:
        return b"\xAA\xBB\xCC"  # arbitrary


# -----------------------------
# Helpers
# -----------------------------

def _make_engine(monkeypatch, *, parser_frames=(), cmd_timeout_s=1.0):
    """
    Build a ProtocolEngine with parser + framing stubbed so tests are deterministic.
    """
    proto = FakeProto()
    transport = FakeTransport()

    # Stub FrameParser to return a FakeParser instance
    fake_parser = FakeParser(parser_frames)
    monkeypatch.setattr(eng_mod, "FrameParser", lambda *a, **k: fake_parser)

    engine = eng_mod.ProtocolEngine(proto, transport, cmd_timeout_s=cmd_timeout_s, logger=logging.getLogger("test"))
    return engine, proto, transport, fake_parser


# -----------------------------
# Tests: core engine logic
# -----------------------------

def test_pump_rx_ack_resolves_pending_and_removes_it(monkeypatch):
    """
    Algorithm: ACK frame with seq must resolve the matching pending command,
    set status 'ok', and remove it from _pending.
    """
    ack_frame = SimpleNamespace(frame_type=0x20, seq=7, payload=b"\x01\x02")
    engine, _, _, _ = _make_engine(monkeypatch, parser_frames=[ack_frame])

    pending = FakePending(seq=7, cmd_name="PING", timeout_s=1.0)
    engine._pending[7] = pending

    engine._pump_rx()

    assert pending.result_calls == [(ack_frame, "ok")]
    assert 7 not in engine._pending


def test_pump_rx_nack_resolves_pending_and_removes_it(monkeypatch):
    """
    Algorithm: NACK frame with seq must resolve the matching pending command,
    set status 'fail', and remove it from _pending.
    """
    nack_frame = SimpleNamespace(frame_type=0x21, seq=9, payload=b"\xFF")
    engine, _, _, _ = _make_engine(monkeypatch, parser_frames=[nack_frame])

    pending = FakePending(seq=9, cmd_name="SET_PERIOD", timeout_s=1.0)
    engine._pending[9] = pending

    engine._pump_rx()

    assert pending.result_calls == [(nack_frame, "fail")]
    assert 9 not in engine._pending


def test_pump_rx_stream_enqueues_and_invokes_callback(monkeypatch):
    """
    Algorithm: STREAM frames must be queued and optional on_stream callback invoked.
    """
    stream_frame = SimpleNamespace(frame_type=0x10, seq=1, payload=b"\xAA")
    engine, _, _, _ = _make_engine(monkeypatch, parser_frames=[stream_frame])

    seen = []
    engine.on_stream = lambda f: seen.append(f)

    engine._pump_rx()

    # Queue contains the stream frame
    got = engine.try_get_stream_frame(timeout=0.01)
    assert got is stream_frame

    # Callback got invoked
    assert seen == [stream_frame]


def test_pump_rx_stream_callback_error_does_not_crash(monkeypatch):
    """
    Algorithm: on_stream callback exceptions must be caught (engine must keep running).
    We assert the pump completes and the frame is still queued.
    """
    stream_frame = SimpleNamespace(frame_type=0x10, seq=2, payload=b"\xBB")
    engine, _, _, _ = _make_engine(monkeypatch, parser_frames=[stream_frame])

    def boom(_):
        raise RuntimeError("handler failed")

    engine.on_stream = boom

    # Should not raise
    engine._pump_rx()

    got = engine.try_get_stream_frame(timeout=0.01)
    assert got is stream_frame


def test_pump_rx_expires_pending_by_timeout(monkeypatch):
    """
    Algorithm: Pending commands older than timeout_s must be marked 'timeout'
    and removed from _pending during pump.
    """
    engine, _, _, _ = _make_engine(monkeypatch, parser_frames=[])

    # Control time.perf_counter deterministically
    monkeypatch.setattr(eng_mod.time, "perf_counter", lambda: 100.0)

    # created_at far in the past so it expires
    pending = FakePending(seq=42, cmd_name="GET_SENSORS", timeout_s=1.0, created_at=0.0)
    engine._pending[42] = pending

    engine._pump_rx()

    assert pending.result_calls == [(None, "timeout")]
    assert 42 not in engine._pending


def test_decode_response_falls_back_to_raw_on_decode_error(monkeypatch):
    """
    Contract: if proto decode throws, _decode_response returns {'raw': hex}.
    This is useful because it prevents crashes and preserves data for debugging.
    """
    engine, proto, _, _ = _make_engine(monkeypatch)

    def bad_decode(cmd_id, payload):
        raise ValueError("decode failed")

    proto.decode_response = bad_decode  # force the exception path

    out = engine._decode_response("PING", b"\xDE\xAD\xBE\xEF")
    assert out == {"raw": "deadbeef"}


def test_send_cmd_async_send_failure_removes_pending_and_sets_send_failed(monkeypatch):
    """
    If transport.write raises, the engine must:
    - remove the pending command from _pending
    - mark the pending result with status 'send_failed'
    """
    engine, _, transport, _ = _make_engine(monkeypatch)

    # Prevent real rx thread startup (not needed for this unit test)
    engine._rx_thread = SimpleNamespace(is_alive=lambda: True)

    # Stub CommandFrame + PendingCommand for deterministic behavior
    monkeypatch.setattr(eng_mod, "CommandFrame", FakeCommandFrame)

    created = {}

    def _pending_factory(seq, cmd_name, timeout_s):
        p = FakePending(seq=seq, cmd_name=cmd_name, timeout_s=timeout_s)
        created["pending"] = p
        return p

    monkeypatch.setattr(eng_mod, "PendingCommand", _pending_factory)

    transport.raise_on_write = OSError("no device")

    p = engine.send_cmd_async("PING")

    # Engine returns the pending handle
    assert p is created["pending"]

    # It must not remain in the pending dict after send failure
    assert FakeCommandFrame(None, "PING", {}).seq not in engine._pending

    # And it must be marked send_failed
    assert p.result_calls == [(None, "send_failed")]

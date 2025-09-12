# host/common/session.py
from __future__ import annotations

import threading
from typing import Callable, Optional, Dict, Tuple

from . import protocol as proto
from .serial_link import open_port
from .telemetry import decode_data_frame, Sample
from .control import parse_control_frame


class Session:
    """
    Headless serial session.

    - Owns the serial port and a single RX thread.
    - Decodes frames and invokes callbacks.
    - START/STOP helpers support blocking (ACK/NACK/TIMEOUT) or fire-and-forget.
    """

    # ---- lifecycle ---------------------------------------------------
    def __init__(self, ser):
        self._ser = ser
        self._rx_thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._running = False

        # Pending command seq → (Event, result_str)
        self._pending: Dict[int, Tuple[threading.Event, Optional[str]]] = {}

        # Session-managed command sequence (device echoes this in ACK/NACK seq)
        self._seq = 1

        # Lock guards writes, seq allocation, and _pending map
        self._lock = threading.Lock()

        # callbacks (set by caller)
        self.on_sample: Optional[Callable[[Sample], None]] = None
        self.on_control: Optional[Callable[[dict], None]] = None
        self.on_other: Optional[Callable[[dict, bytes], None]] = None
        self.on_disconnected: Optional[Callable[[str], None]] = None

    @classmethod
    def open(cls, port: Optional[str] = None, timeout: float = 1.0, assert_dtr: bool = True) -> "Session":
        """Open a serial port (auto-detect if None) and create a Session."""
        ser = open_port(port, timeout=timeout, assert_dtr=assert_dtr)
        return cls(ser)

    def start(self) -> None:
        """Start RX loop in a thread (idempotent)."""
        if self._running:
            return
        self._stop_evt.clear()
        self._running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, name="SessionRX", daemon=True)
        self._rx_thread.start()

    def stop(self) -> None:
        """Stop RX loop (keeps port open)."""
        if not self._running:
            return
        self._stop_evt.set()
        if self._rx_thread:
            self._rx_thread.join(timeout=1.5)
        self._running = False
        self._rx_thread = None
        self._fail_pending_timeouts()

    def close(self) -> None:
        """Stop and close the serial port."""
        self.stop()
        try:
            self._ser.close()
        except Exception:
            pass

    @property
    def is_running(self) -> bool:
        return self._running

    # ---- commands (blocking/non-blocking) ----------------------------
    def send_start(self, *, wait: bool = True, timeout_s: float = 1.0) -> Tuple[str, int]:
        """Send START. Returns ('ACK'|'NACK'|'TIMEOUT'|'SENT', seq)."""
        return self._send_cmd(proto.CMD_START, wait=wait, timeout_s=timeout_s)

    def send_stop(self, *, wait: bool = True, timeout_s: float = 1.0) -> Tuple[str, int]:
        """Send STOP. Returns ('ACK'|'NACK'|'TIMEOUT'|'SENT', seq)."""
        return self._send_cmd(proto.CMD_STOP, wait=wait, timeout_s=timeout_s)

    # ---- internals ---------------------------------------------------
    def _next_seq(self) -> int:
        with self._lock:
            s = self._seq
            self._seq = (s + 1) & 0xFFFFFFFF or 1
            return s

    def _send_cmd(self, opcode: int, *, wait: bool, timeout_s: float) -> Tuple[str, int]:
        seq = self._next_seq()
        with self._lock:
            proto.write_frame(self._ser, proto.PROTO_TYPE_CMD, bytes([opcode]), seq=seq, ts_ms=0)
            if not wait:
                return ("SENT", seq)
            ev = threading.Event()
            self._pending[seq] = (ev, None)

        ok = ev.wait(timeout_s)
        with self._lock:
            _, result = self._pending.pop(seq, (ev, None))
        if not ok or result is None:
            return ("TIMEOUT", seq)
        return (result, seq)

    def _rx_loop(self):
        try:
            while not self._stop_evt.is_set():
                hdr, payload = proto.read_frame(self._ser)
                if hdr is None:
                    continue

                t = hdr["type"]
                if t == proto.PROTO_TYPE_STREAM:
                    s = decode_data_frame(hdr, payload)
                    if self.on_sample:
                        self.on_sample(s)

                elif t in (proto.PROTO_TYPE_ACK, proto.PROTO_TYPE_NACK):
                    ev = parse_control_frame(hdr, payload)
                    # Wake pending waiter (if any) before forwarding the event
                    seq = int(hdr.get("seq", 0))
                    result = "ACK" if t == proto.PROTO_TYPE_ACK else "NACK"
                    with self._lock:
                        pending = self._pending.get(seq)
                        if pending:
                            pevt, _ = pending
                            self._pending[seq] = (pevt, result)
                            pevt.set()
                    if self.on_control:
                        self.on_control(ev)

                else:
                    if self.on_other:
                        self.on_other(hdr, payload)

        except Exception as e:
            if self.on_disconnected:
                self.on_disconnected(f"Disconnected: {e}")
        finally:
            try:
                self._ser.close()
            except Exception:
                pass

    def _fail_pending_timeouts(self) -> None:
        """
        Unblock any threads waiting on send_* when the session stops.
        """
        with self._lock:
            for seq, (ev, result) in list(self._pending.items()):
                if not result:
                    self._pending[seq] = (ev, "TIMEOUT")
                ev.set()
            self._pending.clear()

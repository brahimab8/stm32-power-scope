# host/protocol/_internal/pending_command.py
from __future__ import annotations

import time
from concurrent.futures import Future
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from host.protocol.core.frames import ResponseFrame


class PendingCommand:
    """Holds a Future for an asynchronous command."""

    def __init__(self, seq: int, cmd_name: str, timeout_s: float):
        self.seq = int(seq)
        self.cmd_name = str(cmd_name)
        self.timeout_s = float(timeout_s)
        self.created_at = time.perf_counter()
        self.future: Future = Future()

    def add_done_callback(self, cb: Callable[[Future], Any]) -> Any:
        """Forward callback registration to the underlying Future."""
        return self.future.add_done_callback(cb)

    def result(self, *args: Any, **kwargs: Any) -> Any:
        """Forward result() to underlying Future."""
        return self.future.result(*args, **kwargs)

    def done(self) -> bool:
        return self.future.done()

    def set_result(
        self,
        resp: Optional["ResponseFrame"],
        status: str,
        decode_fn: Optional[Callable[[bytes], Any]] = None,
    ) -> None:
        """Set the result of this command, optionally decoding ACK payloads."""
        if self.future.done():
            return

        if status == "timeout":
            self.future.set_result({"status": "timeout"})
            return

        if status == "send_failed":
            self.future.set_result({"status": "send_failed"})
            return

        if resp is None:
            self.future.set_result({"status": "unknown"})
            return

        try:
            ack_code = resp.proto.frames["ACK"]["code"]
            nack_code = resp.proto.frames["NACK"]["code"]

            if resp.frame_type == ack_code:
                # try decoded property first
                try:
                    payload = getattr(resp, "decoded", None)
                except Exception:
                    payload = None

                # fallback to raw payload bytes
                if payload is None:
                    payload = getattr(resp, "data", getattr(resp, "payload", b""))

                # decode if decode_fn is given
                if decode_fn and isinstance(payload, (bytes, bytearray)):
                    try:
                        payload = decode_fn(bytes(payload))
                    except Exception:
                        payload = {"raw": bytes(payload).hex()}

                self.future.set_result({"status": "ok", "payload": payload})
                return

            if resp.frame_type == nack_code:
                try:
                    error = getattr(resp, "error", {"code": None, "name": "UNKNOWN"})
                except Exception:
                    error = {"code": None, "name": "UNKNOWN"}
                self.future.set_result({"status": "fail", "error": error})
                return

            self.future.set_result({"status": "unknown", "frame": resp})

        except Exception:
            # Fallback if anything above fails
            self.future.set_result({"status": "unknown"})

    def wait(self, timeout: Optional[float] = None) -> dict:
        """Blocking wait for command completion."""
        try:
            return self.future.result(timeout=timeout)
        except Exception:
            return {"status": "pending"}

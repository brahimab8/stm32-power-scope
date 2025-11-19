# host/protocol/engine.py
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, Dict, Optional, Protocol as TypingProtocol

from . import CommandFrame, Protocol, StreamFrame
from host.interfaces.command_sink import CommandEvent ,CommandSink
from .core import FrameParser
from ._internal.pending_command import PendingCommand
from ._internal.rx_worker import RxWorker


class TransportIO(TypingProtocol):
    """Minimal I/O interface for ProtocolEngine."""
    def write(self, data: bytes) -> int: ...
    def read(self, size: int) -> bytes: ...
    def flush(self) -> None: ...


class ProtocolEngine:
    """
    Low-level protocol engine.
    Manages sending commands, receiving responses, and handling streams.
    """

    def __init__(
        self,
        proto: Protocol,
        transport: TransportIO,
        *,
        cmd_timeout_s: float = 1.0,
        cmd_sink: Optional[CommandSink] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.proto = proto
        self.transport = transport

        self._log = logger or logging.getLogger(__name__)
        self._cmd_sink = cmd_sink

        self.cmd_timeout_s = float(cmd_timeout_s)

        self._parser = FrameParser(proto, logger=self._log)

        self._rx_thread: Optional[RxWorker] = None
        self.on_stream: Optional[Callable[[StreamFrame], None]] = None

        self._lock = threading.Lock()
        self._pending: Dict[int, PendingCommand] = {}
        self._stream_queue: "queue.Queue[StreamFrame]" = queue.Queue(maxsize=200)

        self.STREAM_CODE = proto.frames["STREAM"]["code"]
        self.ACK_CODE = proto.frames["ACK"]["code"]
        self.NACK_CODE = proto.frames["NACK"]["code"]

    # ---------------- Decoder ----------------
    def _decode_response(self, cmd_name: str, payload: bytes) -> dict:
        """
        Attempt to decode payload. If decoding fails, return raw hex.
        """
        try:
            cmd_def = self.proto.get_command_def(cmd_name)
            cmd_id = self.proto.resolve_value(
                cmd_def.get("cmd_id"),
                self.proto.constants.get("cmd_none", 0),
            )
            return self.proto.decode_response(cmd_id, payload)
        except Exception:
            self._log.warning("CMD_DECODE_FAILED cmd=%s payload_len=%d", cmd_name, len(payload))
            return {"raw": payload.hex()}

    # ---------------- Command API ----------------
    def send_cmd_async(self, cmd_name: str, **kwargs) -> PendingCommand:
        if self._rx_thread is None or not self._rx_thread.is_alive():
            self.start_rx_thread()

        frame = CommandFrame(self.proto, cmd_name, args=kwargs)
        raw = frame.encode()

        self._log.debug("SENDING_FRAME cmd=%s len=%d raw=%s", cmd_name, len(raw), raw.hex())

        seq = frame.seq
        pending = PendingCommand(seq, cmd_name, self.cmd_timeout_s)

        # Command event
        if self._cmd_sink:
            start_ts = pending.created_at  # perf_counter base

            def _on_done(fut):
                end_ts = time.perf_counter()
                rtt_ms = (end_ts - start_ts) * 1000.0

                try:
                    result = fut.result()
                except Exception as e:
                    self._cmd_sink.on_command(
                        CommandEvent(
                            name=cmd_name,
                            kind="exception",
                            request_id=str(seq),
                            payload={
                                "args": kwargs,
                                "response": {"status": "exception", "error": str(e)},
                                "rtt_ms": rtt_ms,
                            },
                        )
                    )
                    return

                status = result.get("status")
                if status == "ok":
                    self._cmd_sink.on_command(
                        CommandEvent(
                            name=cmd_name,
                            kind="ok",
                            request_id=str(seq),
                            payload={
                                "args": kwargs,
                                "response": result.get("payload"),
                                "rtt_ms": rtt_ms,
                            },
                        )
                    )
                else:
                    self._cmd_sink.on_command(
                        CommandEvent(
                            name=cmd_name,
                            kind=status or "fail",
                            request_id=str(seq),
                            payload={
                                "args": kwargs,
                                "error": result,
                                "rtt_ms": rtt_ms,
                            },
                        )
                    )

            pending.add_done_callback(_on_done)

        with self._lock:
            self._pending[seq] = pending

        try:
            self.transport.write(raw)
            try:
                self.transport.flush()
            except Exception:
                pass
        except Exception:
            with self._lock:
                self._pending.pop(seq, None)

            # Send failure.
            pending.set_result(None, "send_failed", decode_fn=self._decode_response)
            self._log.exception("CMD_SEND_FAILED cmd=%s", cmd_name)

        return pending

    def send_cmd(self, cmd_name: str, timeout: Optional[float] = None, **kwargs) -> dict:
        handle = self.send_cmd_async(cmd_name, **kwargs)
        return handle.wait(timeout=timeout or self.cmd_timeout_s)

    # ---------------- RX Thread ----------------
    def start_rx_thread(self) -> None:
        if self._rx_thread is None or not self._rx_thread.is_alive():
            self._rx_thread = RxWorker(self)
            self._rx_thread.start()
            self._log.info("RX_THREAD_STARTED")

    def stop_rx_thread(self) -> None:
        if self._rx_thread:
            self._rx_thread.stop()
            self._rx_thread.join()
            self._log.info("RX_THREAD_STOPPED")

    # ---------------- RX Pump ----------------
    def _pump_rx(self) -> None:
        data = self.transport.read(256)
        if data:
            self._parser.feed(data)

        while True:
            frame = self._parser.get_frame()
            if frame is None:
                break

            seq = getattr(frame, "seq", None)
            if frame.frame_type in (self.ACK_CODE, self.NACK_CODE) and seq is not None:
                with self._lock:
                    pending = self._pending.pop(seq, None)
                if pending:
                    decode_fn = lambda payload, cmd_name=pending.cmd_name: self._decode_response(cmd_name, payload)
                    status = "ok" if frame.frame_type == self.ACK_CODE else "fail"
                    pending.set_result(frame, status, decode_fn=decode_fn)

            elif frame.frame_type == self.STREAM_CODE:
                self._handle_stream(frame)

        # Cleanup expired pending commands
        now = time.perf_counter()
        expired_items: list[PendingCommand] = []
        expired_seqs: list[int] = []

        with self._lock:
            for seq, pending in list(self._pending.items()):
                if (now - pending.created_at) > pending.timeout_s:
                    expired_items.append(pending)
                    expired_seqs.append(seq)

            for seq in expired_seqs:
                self._pending.pop(seq, None)

        for pending in expired_items:
            decode_fn = lambda payload, cmd_name=pending.cmd_name: self._decode_response(cmd_name, payload)
            pending.set_result(None, "timeout", decode_fn=decode_fn)

    # ---------------- Stream Queue ----------------
    def _handle_stream(self, frame: StreamFrame) -> None:
        try:
            self._stream_queue.put_nowait(frame)
        except queue.Full:
            self._log.warning("STREAM_QUEUE_FULL dropped_seq=%s", getattr(frame, "seq", None))

        if self.on_stream:
            try:
                self.on_stream(frame)
            except Exception:
                self._log.exception("ON_STREAM_CALLBACK_ERROR")

    def try_get_stream_frame(self, timeout: float = 0.1) -> Optional[StreamFrame]:
        try:
            return self._stream_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ---------------- Factory ----------------
    @classmethod
    def create(
        cls,
        proto: Protocol,
        transport: TransportIO,
        *,
        cmd_timeout_s: float = 1.0,
        cmd_sink: Optional[CommandSink] = None,
        logger: Optional[logging.Logger] = None,
        on_stream: Optional[Callable[[StreamFrame], None]] = None,
    ) -> "ProtocolEngine":
        engine = cls(
            proto,
            transport,
            cmd_timeout_s=cmd_timeout_s,
            cmd_sink=cmd_sink,
            logger=logger,
        )
        engine.on_stream = on_stream
        engine.start_rx_thread()
        return engine

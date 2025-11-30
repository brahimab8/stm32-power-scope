# host/runtime/device_link.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from host.interfaces.command_sink import CommandSink
from host.protocol.core.defs import Protocol
from host.protocol.core.frames import StreamFrame
from host.protocol.engine import ProtocolEngine
from host.protocol.mcu_client import McuClient
from host.transport.base import Transport as HwTransport
from host.transport.errors import TransportError, TransportOpenError

from host.core.errors import DeviceConnectError, ProtocolCommunicationError


@dataclass
class DeviceLink:
    """
    High-level host/device link managing ProtocolEngine and transport.

    Responsibilities:
      - open/close the underlying transport
      - create/stop the ProtocolEngine RX thread
      - expose an MCU client handle once started
      - translate low-level failures into operator-safe errors
    """

    proto: Protocol
    transport: HwTransport
    cmd_timeout_s: float = 1.0
    cmd_sink: Optional[CommandSink] = None
    logger: Optional[logging.Logger] = None
    on_stream: Optional[Callable[[StreamFrame], None]] = None

    def __post_init__(self) -> None:
        self._log = self.logger or logging.getLogger(__name__)
        self._engine: Optional[ProtocolEngine] = None
        self._client: Optional[McuClient] = None

    @property
    def is_started(self) -> bool:
        return self._engine is not None and self._client is not None

    @property
    def client(self) -> McuClient:
        if self._client is None:
            raise RuntimeError("DeviceLink not started (client is None)")
        return self._client

    def start(self) -> None:
        if self.is_started:
            return

        # Open transport
        try:
            self.transport.open()
        except TransportOpenError as e:
            self._log.exception("TRANSPORT_OPEN_FAILED")
            raise DeviceConnectError(
                "Could not open device transport.",
                hint=str(e),
                details={"driver": type(self.transport).__name__},
            ) from None
        except TransportError as e:
            self._log.exception("TRANSPORT_OPEN_ERROR")
            raise DeviceConnectError(
                "Transport error while opening device.",
                hint=str(e),
                details={"driver": type(self.transport).__name__},
            ) from None

        # Create protocol engine + API client
        try:
            self._engine = ProtocolEngine.create(
                self.proto,
                self.transport,
                cmd_timeout_s=self.cmd_timeout_s,
                cmd_sink=self.cmd_sink,
                logger=self._log,
                on_stream=self._on_stream,
            )
            self._client = McuClient(self._engine)
        except Exception as e:
            self._log.exception("PROTOCOL_ENGINE_INIT_FAILED")
            self._cleanup_after_failed_start()
            raise ProtocolCommunicationError(
                "Failed to initialize protocol engine.",
                hint=str(e),
                details={"driver": type(self.transport).__name__},
            ) from None

    def _cleanup_after_failed_start(self) -> None:
        try:
            self.transport.close()
        except Exception:
            pass
        self._engine = None
        self._client = None

    def stop(self) -> None:
        if self._engine is not None:
            try:
                self._engine.stop_rx_thread()
            except Exception:
                self._log.exception("Failed to stop RX thread")
            self._engine = None

        self._client = None

        try:
            self.transport.close()
        except Exception:
            self._log.exception("Failed to close transport")

    def _on_stream(self, frame: StreamFrame) -> None:
        cb = self.on_stream
        if cb is not None:
            cb(frame)

    def __enter__(self) -> "DeviceLink":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

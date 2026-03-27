# host/protocol/_internal/rx_worker.py
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from host.transport.errors import TransportIOError

if TYPE_CHECKING:
    from host.protocol.engine import ProtocolEngine


class RxWorker(threading.Thread):
    """Thread that continuously reads from transport and feeds ProtocolEngine."""

    def __init__(self, proto_engine: "ProtocolEngine"):
        super().__init__(daemon=True)
        self.engine = proto_engine
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.engine._pump_rx()
            except TransportIOError:
                if self._stop_event.is_set():
                    break
                self.engine._log.info("RX_WORKER_TRANSPORT_CLOSED")
                break
            except Exception:
                if self._stop_event.is_set():
                    break
                self.engine._log.exception(
                    "RX_WORKER_EXCEPTION pending=%s",
                    list(getattr(self.engine, "_pending", {}).keys()),
                )
                self._stop_event.wait(0.01)
            else:
                self._stop_event.wait(0.001)

    def stop(self) -> None:
        self._stop_event.set()

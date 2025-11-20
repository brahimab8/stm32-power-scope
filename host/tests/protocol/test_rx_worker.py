from __future__ import annotations

import logging
import time

from host.protocol._internal.rx_worker import RxWorker


class FakeEngine:
    def __init__(self):
        self._log = logging.getLogger("test")
        self._pending = {}
        self.calls = 0
        self.raise_once = False

    def _pump_rx(self):
        self.calls += 1
        if self.raise_once:
            self.raise_once = False
            raise RuntimeError("boom")


def test_rx_worker_stops_cleanly():
    eng = FakeEngine()
    w = RxWorker(eng)

    w.start()
    time.sleep(0.01)
    w.stop()
    w.join(timeout=0.2)

    assert not w.is_alive()
    assert eng.calls > 0


def test_rx_worker_keeps_running():
    eng = FakeEngine()
    eng.raise_once = True
    w = RxWorker(eng)

    w.start()

    deadline = time.time() + 0.5
    while eng.calls < 2 and time.time() < deadline:
        time.sleep(0.005)

    w.stop()
    w.join(timeout=0.2)

    assert not w.is_alive()
    assert eng.calls >= 2

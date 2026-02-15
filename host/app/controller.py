# host/app/controller.py
from __future__ import annotations

import logging
from typing import Callable, Optional

from host.app.config import PowerScopeConfig
from host.core.context import Context
from host.runtime.device_session import DeviceSession
from host.runtime.state import SessionStatus, SensorState
from host.transport.factory import DeviceTransport
from host.interfaces import CommandSink, ReadingSink
from host.model import DecodedReading


class PowerScopeController:
    """
    App-level controller for PowerScope.
    """

    def __init__(
        self,
        config: PowerScopeConfig,
        *,
        context: Context,
        device_transport: DeviceTransport,
        cmd_sink: Optional[CommandSink] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self._config = config
        self._log = logger or logging.getLogger(__name__)

        self._context = context
        self._device_transport = device_transport

        self._session = DeviceSession(
            proto=self._context.protocol,
            sensors=self._context.sensors,
            device_transport=self._device_transport,
            cmd_timeout_s=config.cmd_timeout_s,
            cmd_sink=cmd_sink,
            logger=self._log,
        )

        self._reading_sinks: list[ReadingSink] = []
        self._unsubscribe: Optional[Callable[[], None]] = None

    @property
    def context(self) -> Context:
        return self._context

    @property
    def config(self) -> PowerScopeConfig:
        return self._config

    @property
    def device_transport(self) -> DeviceTransport:
        return self._device_transport

    def add_sink(self, sink: ReadingSink) -> None:
        if sink not in self._reading_sinks:
            self._reading_sinks.append(sink)

    def remove_sink(self, sink: ReadingSink) -> None:
        if sink in self._reading_sinks:
            self._reading_sinks.remove(sink)

    def start(self) -> None:
        self._subscribe_once()
        try:
            self._session.start()
        except Exception:
            try:
                self.stop()
            except Exception:
                self._log.exception("CONTROLLER_STOP_AFTER_START_FAIL")
            raise

    def stop(self) -> None:
        # unsubscribe
        if self._unsubscribe:
            try:
                self._unsubscribe()
            finally:
                self._unsubscribe = None

        # close sinks
        for s in list(self._reading_sinks):
            try:
                s.close()
            except Exception:
                self._log.exception("SINK_CLOSE_ERROR")

        self._reading_sinks.clear()

        # stop session
        try:
            self._session.stop()
        except Exception:
            self._log.exception("SESSION_STOP_ERROR")

    def __enter__(self) -> "PowerScopeController":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def _subscribe_once(self) -> None:
        if self._unsubscribe is not None:
            return

        def _fanout(runtime_id: int, reading: DecodedReading) -> None:
            for s in list(self._reading_sinks):
                try:
                    s.on_reading(runtime_id, reading)
                except Exception:
                    self._log.exception("SINK_ON_READING_ERROR")

        self._unsubscribe = self._session.subscribe_readings(_fanout)

    # passthrough ops
    def status(self) -> SessionStatus:
        return self._session.status()

    def refresh_sensors(self) -> list[SensorState]:
        return self._session.refresh_sensors()

    def set_period(self, sensor_runtime_id: int, *, period_ms: int) -> None:
        self._session.set_period(sensor_runtime_id, period_ms=period_ms)

    def get_period(self, sensor_runtime_id: int) -> int:
        return self._session.get_period(sensor_runtime_id)

    def start_stream(self, sensor_runtime_id: int) -> None:
        self._session.start_stream(sensor_runtime_id)

    def stop_stream(self, sensor_runtime_id: int) -> None:
        self._session.stop_stream(sensor_runtime_id)

    def read_sensor(self, sensor_runtime_id: int) -> DecodedReading:
        reading = self._session.read_sensor(sensor_runtime_id)

        # push into the same pipeline as streaming
        for s in list(self._reading_sinks):
            try:
                s.on_reading(sensor_runtime_id, reading)
            except Exception:
                self._log.exception("SINK_ON_READING_ERROR")

        return reading

    def get_uptime(self) -> int:
        return self._session.get_uptime()

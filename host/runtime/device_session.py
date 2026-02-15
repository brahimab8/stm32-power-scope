# host/runtime/device_session.py
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Mapping
from dataclasses import replace

from host.runtime.device_link import DeviceLink
from host.runtime.state import TransportState, McuState, SensorState, SessionStatus
from host.transport.factory import DeviceTransport
from host.model.sensor import DecodedReading, Sensor
from host.interfaces.command_sink import CommandSink

from host.protocol.core.frames import StreamFrame
from host.protocol.core.defs import Protocol
from host.protocol.mcu_client import McuClient, SensorInfo

from host.core.errors import PowerScopeError, McuNotRespondingError

ReadingCallback = Callable[[int, DecodedReading], None]  # (runtime_id, reading)
RawStreamCallback = Callable[[StreamFrame], None]        # optional debug hook


class DeviceSession:
    """
    High-level device session managing DeviceLink, McuClient, and runtime sensor state.
    """

    def __init__(
        self,
        *,
        proto: Protocol,
        sensors: Mapping[int, Sensor],
        device_transport: DeviceTransport,
        cmd_timeout_s: float = 1.0,
        logger: Optional[logging.Logger] = None,
        cmd_sink: Optional[CommandSink] = None,
    ):
        self._proto = proto
        self._sensors_catalog = sensors
        self._created = device_transport
        self._log = logger or logging.getLogger(__name__)

        self._lock = threading.RLock()

        self._link = DeviceLink(
            proto=self._proto,
            transport=device_transport.transport,
            cmd_timeout_s=cmd_timeout_s,
            logger=self._log,
            cmd_sink=cmd_sink,
        )
        self._link.on_stream = self._on_stream_frame

        self._client: Optional[McuClient] = None

        self._runtime_to_type: Dict[int, int] = {}
        self._sensors: Dict[int, SensorState] = {}

        self._reading_cbs: List[ReadingCallback] = []
        self._raw_stream_cbs: List[RawStreamCallback] = []

        self._transport_last_error: Optional[str] = None
        self._mcu_last_error: Optional[str] = None
        self._mcu_last_seen_monotonic: Optional[float] = None
        self._mcu_uptime_s: Optional[float] = None

    @property
    def is_started(self) -> bool:
        return self._link.is_started

    def start(self) -> None:
        with self._lock:
            if self._link.is_started:
                return
            self._transport_last_error = None
            self._mcu_last_error = None

        meta = self._created.meta
        params = dict(self._created.params)
        self._log.info(
            "SESSION_START type_id=%s driver=%s label=%s params=%s",
            meta.type_id,
            meta.driver,
            meta.label,
            params,
        )

        try:
            self._link.start()
            with self._lock:
                self._client = self._link.client  # property raises if not started
        except PowerScopeError as e:
            with self._lock:
                self._transport_last_error = e.message
            self._log.warning("SESSION_START_FAILED code=%s msg=%s", getattr(e, "code", "unknown"), e.message)
            raise
        except Exception as e:
            self._log.exception("DEVICE_SESSION_START_FAILED")
            with self._lock:
                self._transport_last_error = str(e)
            raise

        # MCU ping
        ok = self._client.ping() if self._client is not None else False
        if not ok:
            with self._lock:
                self._mcu_last_error = "MCU not responding (PING failed)"
                self._mcu_last_seen_monotonic = time.monotonic()
            self._log.warning("MCU_PING_FAILED")
            raise McuNotRespondingError(
                "MCU not responding (PING failed).",
                hint="Check firmware is running and baudrate/protocol match.",
            )

        self._mark_mcu_ok()
        self._log.info("MCU_PING_OK")

        sensors = self.refresh_sensors()
        self._log.info("SENSORS_REFRESHED count=%d", len(sensors))

    def stop(self) -> None:
        self._log.info("SESSION_STOP")
        with self._lock:
            self._client = None
            self._runtime_to_type.clear()
            self._sensors.clear()
            self._mcu_last_seen_monotonic = None
            self._mcu_last_error = None
        self._link.stop()

    def status(self) -> SessionStatus:
        with self._lock:
            meta = self._created.meta
            kp = getattr(meta, "key_param", None)
            key_param_value = str(self._created.params.get(kp, "")) if kp else ""

            transport_state = TransportState(
                connected=self._link.is_started,
                driver=meta.driver,
                key_param_value=key_param_value,
                last_error=self._transport_last_error,
            )

            now = time.monotonic()
            last_seen_s = (
                (now - self._mcu_last_seen_monotonic)
                if self._mcu_last_seen_monotonic is not None
                else None
            )

            # Calculate uptime as last known uptime + time since last seen
            if self._mcu_uptime_s is not None and self._mcu_last_seen_monotonic is not None:
                uptime_s = (self._mcu_uptime_s / 1000.0) + (now - self._mcu_last_seen_monotonic)
            else:
                uptime_s = None

            mcu_state = McuState(
                available=(
                    self._link.is_started
                    and self._mcu_last_error is None
                    and self._mcu_last_seen_monotonic is not None
                ),
                last_seen_s=last_seen_s,
                uptime_s=uptime_s,
                last_error=self._mcu_last_error,
            )

            sensors = list(self._sensors.values())

        return SessionStatus(transport=transport_state, mcu=mcu_state, sensors=sensors)

    def refresh_sensors(self) -> List[SensorState]:
        client = self._require_client()
        sensors: List[SensorInfo] = client.get_sensors()

        runtime_to_type: Dict[int, int] = {s.runtime_id: s.type_id for s in sensors}

        new_states: Dict[int, SensorState] = {}
        with self._lock:
            old_states = dict(self._sensors)

        for s in sensors:
            sensor_meta = self._sensors_catalog.get(int(s.type_id))
            name = sensor_meta.name if sensor_meta else f"type_id={s.type_id}"

            old = old_states.get(s.runtime_id)
            new_states[s.runtime_id] = SensorState(
                runtime_id=s.runtime_id,
                type_id=s.type_id,
                name=name,
                streaming=old.streaming if old else False,
                period_ms=old.period_ms if old else None,
                last_error=None,
            )

        with self._lock:
            self._runtime_to_type = runtime_to_type
            self._sensors = new_states
        self._mark_mcu_ok()

        return list(new_states.values())

    def ping(self) -> bool:
        client = self._require_client()
        ok = client.ping()
        if ok:
            self._mark_mcu_ok()
        else:
            with self._lock:
                self._mcu_last_seen_monotonic = time.monotonic()
                self._mcu_last_error = "PING returned not-ok"
            self._log.warning("MCU_PING_NOT_OK")
        return ok

    def set_period(self, sensor_runtime_id: int, period_ms: int) -> None:
        self._log.info("SET_PERIOD sensor_runtime_id=%d period_ms=%d", int(sensor_runtime_id), int(period_ms))
        client = self._require_client()
        client.set_period(sensor_runtime_id, period_ms=period_ms)
        self._set_sensor_state(sensor_runtime_id, period_ms=int(period_ms), last_error=None)
        self._mark_mcu_ok()

    def get_period(self, sensor_runtime_id: int) -> int:
        client = self._require_client()
        period_ms = client.get_period(sensor_runtime_id)
        self._set_sensor_state(sensor_runtime_id, period_ms=period_ms, last_error=None)
        self._mark_mcu_ok()
        return period_ms

    def start_stream(self, sensor_runtime_id: int) -> None:
        self._log.info("START_STREAM sensor_runtime_id=%d", int(sensor_runtime_id))
        client = self._require_client()
        client.start_stream(sensor_runtime_id)
        self._set_sensor_state(sensor_runtime_id, streaming=True, last_error=None)
        self._mark_mcu_ok()

    def stop_stream(self, sensor_runtime_id: int) -> None:
        self._log.info("STOP_STREAM sensor_runtime_id=%d", int(sensor_runtime_id))
        client = self._require_client()
        client.stop_stream(sensor_runtime_id)
        self._set_sensor_state(sensor_runtime_id, streaming=False, last_error=None)
        self._mark_mcu_ok()

    def get_uptime(self) -> int:
        client = self._require_client()
        uptime_ms = client.get_uptime()
        with self._lock:
            # Update timestamp and uptime
            self._mcu_last_seen_monotonic = time.monotonic()
            self._mcu_last_error = None
            self._mcu_uptime_s = uptime_ms / 1000.0 # Convert ms to seconds
        return uptime_ms

    def read_sensor(self, sensor_runtime_id: int) -> Optional[DecodedReading]:
        client = self._require_client()
        resp = client.read_sensor(sensor_runtime_id)
        cmd_seq = resp.get("seq")

        # --- Extract payload correctly ---
        if "raw_readings" not in resp:
            self._set_sensor_state(sensor_runtime_id, last_error="no 'raw_readings' in payload")
            self._mark_mcu_ok()
            self._log.warning("READ_SENSOR_FAILED runtime_id=%d: no 'raw_readings'", sensor_runtime_id)
            return None

        raw = resp["raw_readings"]
        if not isinstance(raw, (bytes, bytearray)):
            self._set_sensor_state(sensor_runtime_id, last_error=f"raw_readings invalid type {type(raw)}")
            self._mark_mcu_ok()
            self._log.warning("READ_SENSOR_FAILED runtime_id=%d: raw_readings invalid type", sensor_runtime_id)
            return None

        payload_bytes = bytes(raw)

        # --- Resolve sensor ---
        type_id = self._runtime_to_type.get(sensor_runtime_id)
        if type_id is None:
            self._log.warning("Unknown sensor runtime_id=%d", sensor_runtime_id)
            return None

        sensor_meta = self._sensors_catalog.get(type_id)
        if sensor_meta is None:
            self._log.warning("Unknown sensor type_id=%d", type_id)
            return None

        # --- Decode payload ---
        try:
            base = sensor_meta.decode_payload(payload_bytes, compute=True, source="read_sensor", cmd_seq=cmd_seq)
        except Exception as e:
            self._set_sensor_state(sensor_runtime_id, last_error=str(e))
            self._mark_mcu_ok()
            self._log.warning("READ_SENSOR_FAILED runtime_id=%d: %s", sensor_runtime_id, e)
            return None

        reading = replace(
            base,
            source="read_sensor",
            stream_seq=None,
            cmd_seq=int(cmd_seq) if cmd_seq is not None else None,
        )
        self._mark_mcu_ok()
        return reading


    def subscribe_readings(self, cb: ReadingCallback) -> Callable[[], None]:
        with self._lock:
            self._reading_cbs.append(cb)

        def _unsubscribe() -> None:
            with self._lock:
                if cb in self._reading_cbs:
                    self._reading_cbs.remove(cb)

        return _unsubscribe

    def subscribe_raw_stream(self, cb: RawStreamCallback) -> Callable[[], None]:
        with self._lock:
            self._raw_stream_cbs.append(cb)

        def _unsubscribe() -> None:
            with self._lock:
                if cb in self._raw_stream_cbs:
                    self._raw_stream_cbs.remove(cb)

        return _unsubscribe

    def _on_stream_frame(self, frame: StreamFrame) -> None:
        # Fan out raw frames first (debug / tracing hooks)
        with self._lock:
            raw_cbs = list(self._raw_stream_cbs)
    
        for cb in raw_cbs:
            try:
                cb(frame)
            except Exception:
                self._log.exception("RAW_STREAM_CALLBACK_ERROR")

        # Decode STREAM frame (sensor_runtime_id is inside payload)
        try:
            d = frame.decoded

            runtime_id = int(d["sensor_runtime_id"])
            payload = d["raw_readings"]
            stream_seq = int(d["seq"])
        except Exception as e:
            self._log.error("STREAM_DECODE_FAILED err=%s", e)
            return
        
        # Resolve runtime_id -> sensor type
        sensor_meta = self._resolve_sensor_meta(runtime_id)
        if sensor_meta is None:
            self._log.warning(
                "Received stream for unknown runtime_id=%d; type_id mapping missing",
                runtime_id,
            )
            return
        # Decode payload into channels
        try:
            base = sensor_meta.decode_payload(payload, compute=True, source="stream", stream_seq=stream_seq)

            # Attach stream metadata
            reading = replace(
                base,
                source="stream",
                stream_seq=stream_seq,
                cmd_seq=None,
            )

        except Exception as e:
            self._set_sensor_state(runtime_id, last_error=f"decode_failed: {e}")
            return

        # Deliver to subscribers
        with self._lock:
            cbs = list(self._reading_cbs)

        self._mark_mcu_ok()

        for cb in cbs:
            try:
                cb(runtime_id, reading)
            except Exception:
                self._log.exception("READING_CALLBACK_ERROR")

    def _set_sensor_state(
        self,
        runtime_id: int,
        *,
        streaming: Optional[bool] = None,
        period_ms: Optional[int] = None,
        last_error: Optional[str] = None,
    ) -> None:
        with self._lock:
            st = self._sensors.get(runtime_id)
            if not st:
                return

            self._sensors[runtime_id] = SensorState(
                runtime_id=st.runtime_id,
                type_id=st.type_id,
                name=st.name,
                streaming=st.streaming if streaming is None else streaming,
                period_ms=st.period_ms if period_ms is None else period_ms,
                last_error=last_error,
            )

    def _mark_mcu_ok(self) -> None:
        with self._lock:
            self._mcu_last_seen_monotonic = time.monotonic()
            self._mcu_last_error = None

    def _require_client(self) -> McuClient:
        with self._lock:
            client = self._client
        if client is None:
            raise RuntimeError("DeviceSession not started (client is None)")
        return client

    def _resolve_sensor_meta(self, runtime_id: int) -> Optional[Sensor]:
        with self._lock:
            type_id = self._runtime_to_type.get(runtime_id)
        if type_id is None:
            return None
        return self._sensors_catalog.get(int(type_id))


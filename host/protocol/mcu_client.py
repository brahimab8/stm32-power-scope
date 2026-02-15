# host/protocol/mcu_client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .engine import ProtocolEngine
from .errors import CommandFailed, CommandTimeout, SendFailed

@dataclass(frozen=True)
class SensorInfo:
    runtime_id: int
    type_id: int


class McuClient:
    """
    User-facing API over ProtocolEngine.
    """

    def __init__(self, engine: ProtocolEngine):
        self._engine = engine

    @staticmethod
    def _require_ok(resp: dict, cmd_name: str, *, timeout_s: float | None = None) -> dict:
        status = resp.get("status")
        if status == "ok":
            return resp
        if status == "timeout":
            raise CommandTimeout(cmd_name, timeout_s or 0.0)
        if status == "send_failed":
            raise SendFailed(cmd_name)
        raise CommandFailed(cmd_name, resp)

    def ping(self) -> bool:
        resp = self._engine.send_cmd("PING")
        return resp.get("status") == "ok"

    def get_sensors(self) -> List[SensorInfo]:
        resp = self._require_ok(self._engine.send_cmd("GET_SENSORS"), "GET_SENSORS")

        payload = resp.get("payload") or {}
        sensors = payload.get("sensors") or []

        out: List[SensorInfo] = []
        for s in sensors:
            if not isinstance(s, dict):
                raise RuntimeError(f"GET_SENSORS returned invalid sensor entry: {s!r}")
            out.append(
                SensorInfo(
                    runtime_id=int(s["sensor_runtime_id"]),
                    type_id=int(s["type_id"]),
                )
            )
        return out

    def set_period(self, sensor_runtime_id: int, period_ms: int) -> None:
        resp = self._engine.send_cmd(
            "SET_PERIOD",
            sensor_runtime_id=int(sensor_runtime_id),
            period_ms=int(period_ms),
        )
        self._require_ok(resp, "SET_PERIOD")

    def get_period(self, sensor_runtime_id: int) -> int:
        resp = self._require_ok(
            self._engine.send_cmd("GET_PERIOD", sensor_runtime_id=int(sensor_runtime_id)),
            "GET_PERIOD",
        )
        return resp["period_ms"]

    def start_stream(self, sensor_runtime_id: int) -> None:
        resp = self._engine.send_cmd("START_STREAM", sensor_runtime_id=int(sensor_runtime_id))
        self._require_ok(resp, "START_STREAM")

    def stop_stream(self, sensor_runtime_id: int) -> None:
        resp = self._engine.send_cmd("STOP_STREAM", sensor_runtime_id=int(sensor_runtime_id))
        self._require_ok(resp, "STOP_STREAM")

    def read_sensor(self, sensor_runtime_id: int) -> dict:
        resp = self._engine.send_cmd("READ_SENSOR", sensor_runtime_id=int(sensor_runtime_id))
        resp = self._require_ok(resp, "READ_SENSOR")
        return resp.get("payload", {})

    def get_uptime(self) -> int:
        resp = self._require_ok(self._engine.send_cmd("GET_UPTIME"), "GET_UPTIME")
        return resp["uptime_ms"]


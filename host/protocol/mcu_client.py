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


@dataclass(frozen=True)
class BoardUid:
    uid_hex: str


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

    @staticmethod
    def _extract_numeric_field(resp: dict, field: str, cmd_name: str) -> int:
        payload = resp.get("payload")
        if isinstance(payload, dict) and field in payload:
            return int(payload[field])
        if field in resp:
            return int(resp[field])
        raise RuntimeError(f"{cmd_name} response missing '{field}'")

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
        return self._extract_numeric_field(resp, "period_ms", "GET_PERIOD")

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
        return self._extract_numeric_field(resp, "uptime_ms", "GET_UPTIME")

    def get_board_uid(self) -> BoardUid:
        resp = self._require_ok(self._engine.send_cmd("GET_BOARD_UID"), "GET_BOARD_UID")
        payload = resp.get("payload")

        if isinstance(payload, dict):
            raw_hex = payload.get("raw")
            if isinstance(raw_hex, str):
                try:
                    raw = bytes.fromhex(raw_hex)
                except ValueError as e:
                    raise RuntimeError("GET_BOARD_UID returned invalid raw UID hex") from e
                if len(raw) != 12:
                    raise RuntimeError("GET_BOARD_UID returned invalid UID length")
                return BoardUid(uid_hex=raw.hex())

            try:
                uid_w0 = int(payload["uid_w0"])
                uid_w1 = int(payload["uid_w1"])
                uid_w2 = int(payload["uid_w2"])
            except KeyError as e:
                raise RuntimeError(f"GET_BOARD_UID response missing {e.args[0]!r}") from e

            uid = (
                uid_w0.to_bytes(4, "little", signed=False)
                + uid_w1.to_bytes(4, "little", signed=False)
                + uid_w2.to_bytes(4, "little", signed=False)
            )
            return BoardUid(uid_hex=uid.hex())

        raise RuntimeError("GET_BOARD_UID returned invalid payload")

    def get_board_uid_hex(self) -> str:
        return self.get_board_uid().uid_hex


# host/app/session_index.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from host.core.session_store import load_session_json, write_session_json


def upsert_sensor_schema(
    session_json_path: Path,
    *,
    sensor_runtime_id: int,
    schema: Dict[str, Any],
) -> bool:
    data = load_session_json(session_json_path)

    sensors = data.get("sensors")
    if not isinstance(sensors, dict):
        sensors = {}
        data["sensors"] = sensors

    key = str(int(sensor_runtime_id))
    prev = sensors.get(key)

    if prev == schema:
        return False

    sensors[key] = schema
    write_session_json(session_json_path, data)
    return True


def set_latest_stream_path(
    session_json_path: Path,
    *,
    sensor_runtime_id: int,
    csv_rel_path: str,
) -> None:
    data = load_session_json(session_json_path)

    latest = data.get("latest")
    if not isinstance(latest, dict):
        latest = {}
        data["latest"] = latest

    key = str(int(sensor_runtime_id))
    latest[key] = Path(csv_rel_path).as_posix()

    write_session_json(session_json_path, data)

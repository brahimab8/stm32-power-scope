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
    merged: Dict[str, Any] = dict(prev) if isinstance(prev, dict) else {}
    merged.update(schema)

    if isinstance(prev, dict) and "stream_files" in prev and "stream_files" not in schema:
        merged["stream_files"] = prev.get("stream_files")

    if prev == merged:
        return False

    sensors[key] = merged
    write_session_json(session_json_path, data)
    return True


def append_sensor_stream_file(
    session_json_path: Path,
    *,
    sensor_runtime_id: int,
    csv_rel_path: str,
) -> None:
    data = load_session_json(session_json_path)

    sensors = data.get("sensors")
    if not isinstance(sensors, dict):
        sensors = {}
        data["sensors"] = sensors

    key = str(int(sensor_runtime_id))
    entry = sensors.get(key)
    if not isinstance(entry, dict):
        entry = {}

    files = list(entry.get("stream_files", []) or [])
    rel = Path(csv_rel_path).as_posix()
    if rel not in files:
        files.append(rel)
    entry["stream_files"] = files
    sensors[key] = entry

    write_session_json(session_json_path, data)

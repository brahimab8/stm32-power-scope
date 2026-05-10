# host/clients/dash/data.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
import requests

from host.clients.sdk import DaemonApiClient

_METADATA: dict[str, Any] = {}


def load_metadata() -> dict[str, Any]:
    global _METADATA
    if _METADATA:
        return _METADATA

    base_path = Path(__file__).parent.parent.parent / "metadata"

    try:
        with open(base_path / "transports.yml", encoding="utf-8") as f:
            transports_data = yaml.safe_load(f) or {}
            _METADATA["transports"] = transports_data.get("transports", {})
    except Exception:
        _METADATA["transports"] = {}

    try:
        with open(base_path / "sensors.yml", encoding="utf-8") as f:
            sensors_data = yaml.safe_load(f) or {}
            _METADATA["sensors"] = sensors_data.get("sensors", {})
    except Exception:
        _METADATA["sensors"] = {}

    return _METADATA


def new_client(daemon_url: str) -> DaemonApiClient:
    return DaemonApiClient(base_url=str(daemon_url).strip() or "http://127.0.0.1:8765")



def load_boards(daemon_url: str) -> list[dict[str, Any]]:
    out = new_client(daemon_url).list_boards()
    boards = list(out.get("boards", []))
    for b in boards:
        if "board_id" in b:
            b["board_id"] = int(b["board_id"])
    return boards


def transport_options() -> list[dict[str, str]]:
    transports = load_metadata().get("transports", {})
    return [
        {"label": str(item.get("label", f"transport_{tid}")), "value": str(tid)}
        for tid, item in transports.items()
    ]


def resolve_transport_meta(transport_value: Any) -> dict[str, Any]:
    transports = load_metadata().get("transports", {})
    if transport_value is None:
        return {}

    if transport_value in transports:
        return dict(transports.get(transport_value, {}) or {})

    as_text = str(transport_value).strip()
    if as_text in transports:
        return dict(transports.get(as_text, {}) or {})

    try:
        as_int = int(as_text)
        if as_int in transports:
            return dict(transports.get(as_int, {}) or {})
    except Exception:
        pass

    lowered = as_text.lower()
    for _, item in transports.items():
        label = str((item or {}).get("label", "")).strip().lower()
        if label == lowered:
            return dict(item or {})

    return {}


def coerce_by_type(value: Any, param_type: str) -> Any:
    if value is None:
        return None
    if param_type == "bool":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() == "true"
    if param_type == "int":
        return int(value)
    if param_type == "float":
        return float(value)
    return str(value)


def resolve_sensor_channels(sensor_type_id: int) -> list[dict[str, Any]]:
    sensors = load_metadata().get("sensors", {}) or {}

    entry = sensors.get(sensor_type_id)
    if entry is None:
        entry = sensors.get(str(sensor_type_id))
    if not isinstance(entry, dict):
        return []

    channels = entry.get("channels", {}) or {}
    if not isinstance(channels, dict):
        return []

    out: list[dict[str, Any]] = []
    for cid, ch in channels.items():
        if not isinstance(ch, dict):
            continue
        try:
            channel_id = int(cid)
        except Exception:
            continue
        out.append(
            {
                "channel_id": channel_id,
                "name": str(ch.get("name", f"ch_{channel_id}")),
                "unit": str(ch.get("display_unit", "")),
                "unit_options": [str(item) for item in list(ch.get("unit_options", []) or []) if str(item).strip()],
                "is_measured": bool(ch.get("is_measured", True)),
            }
        )

    out.sort(key=lambda item: int(item.get("channel_id", 0)))
    return out


def load_session_sensor_history(
    daemon_url: str,
    session_id: str,
    sensor_runtime_id: int,
    limit: int = 10000,
    stream_file: str | None = None,
) -> list[dict[str, Any]]:
    return new_client(daemon_url).get_session_sensor_history(
        session_id=session_id,
        sensor_runtime_id=sensor_runtime_id,
        limit=limit,
        stream_file=stream_file,
    ).get("items", [])


def history_items_to_plot_records(
    items: list[dict[str, Any]],
    *,
    sensor_name: str = "",
    sensor_runtime_id: int = 0, 
    board_uid: str = "",
) -> list[dict[str, Any]]:
    """Pivots row-oriented history items → column-oriented records for build_plot()."""
    channel_series: dict[int, dict] = {}

    for item in items:
        ts_utc = str(item.get("ts_utc") or "").strip()
        if not ts_utc:
            continue
        reading = item.get("reading") or {}
        all_channels = {**(reading.get("measured") or {}), **(reading.get("computed") or {})}
        for cid_str, ch in all_channels.items():
            if not isinstance(ch, dict):
                continue
            try:
                cid = int(cid_str)
            except Exception:
                continue
            try:
                value = float(ch.get("value"))
            except Exception:
                continue
            if cid not in channel_series:
                channel_series[cid] = {
                    "channel_label": str(ch.get("name", f"ch_{cid}")),
                    "unit": str(ch.get("unit", "") or ""),
                    "history_points": [],
                }
            channel_series[cid]["history_points"].append({"ts_utc": ts_utc, "value": value})

    return [
        {
            "board_id": board_uid,
            "board_label": board_uid[:12] if board_uid else "session",
            "sensor_id": sensor_runtime_id,
            "sensor_label": sensor_name,
            "channel_id": cid,
            "channel_label": entry["channel_label"],
            "unit": entry["unit"],
            "value": entry["history_points"][-1]["value"] if entry["history_points"] else None,
            "history_points": entry["history_points"],
        }
        for cid, entry in sorted(channel_series.items())
    ]
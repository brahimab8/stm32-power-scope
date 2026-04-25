# host/core/session_identity.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from host.core.context import Context
from host.transport.factory import DeviceTransport


def transport_fingerprint(transport: DeviceTransport) -> Dict[str, Any]:
    return {
        "type_id": int(transport.meta.type_id),
        "driver": transport.meta.driver,
        "label": transport.meta.label,
        "params": transport.params,
    }


def context_identity(context: Context) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "protocol_version": int(context.protocol_version),
        "protocol_files_sha256": dict(context.protocol_hashes),
        "metadata_files_sha256": dict(context.metadata_hashes),
    }
    return out


def context_identity_with_board_uid(
    context: Context,
    *,
    board_uid_hex: str | None,
    startup_sensors: Iterable[Any] | None = None,
) -> Dict[str, Any]:
    out = context_identity(context)
    if board_uid_hex:
        out["board_uid_hex"] = str(board_uid_hex).lower()
    if startup_sensors is not None:
        out["startup_sensors"] = normalize_startup_sensors(startup_sensors)
    return out


def normalize_startup_sensors(sensors: Iterable[Any] | None) -> List[Dict[str, int]]:
    out: List[Dict[str, int]] = []
    for item in sensors or []:
        if not isinstance(item, dict):
            continue
        try:
            out.append({
                "runtime_id": int(item["runtime_id"]),
                "type_id": int(item["type_id"]),
            })
        except Exception:
            continue

    out.sort(key=lambda x: (int(x["runtime_id"]), int(x["type_id"])))
    return out


def session_matches(
    session_json_path: Path,
    *,
    identity: Dict[str, Any],
    transport_fp: Dict[str, Any],
) -> bool:
    try:
        with open(session_json_path, "r", encoding="utf-8") as f:
            sj = json.load(f) or {}
    except Exception:
        return False

    proto = sj.get("protocol") or {}
    meta = sj.get("metadata") or {}

    expected_uid = str(identity.get("board_uid_hex") or "").lower()
    session_uid = str(proto.get("board_uid_hex") or "").lower()
    uid_matches = True if not expected_uid else (session_uid == expected_uid)

    expected_sensors = identity.get("startup_sensors")
    sensors_matches = True if expected_sensors is None else (
        normalize_startup_sensors(proto.get("startup_sensors")) == normalize_startup_sensors(expected_sensors)
    )

    return (
        int(proto.get("protocol_version", -1)) == int(identity["protocol_version"])
        and uid_matches
        and sensors_matches
        and (proto.get("files_sha256") or {}) == identity["protocol_files_sha256"]
        and (meta.get("files_sha256") or {}) == identity["metadata_files_sha256"]
        and (sj.get("transport") or {}) == transport_fp
    )

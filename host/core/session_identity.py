# host/core/session_identity.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

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
    return {
        "protocol_version": int(context.protocol_version),
        "protocol_files_sha256": dict(context.protocol_hashes),
        "metadata_files_sha256": dict(context.metadata_hashes),
    }


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

    return (
        int(proto.get("protocol_version", -1)) == int(identity["protocol_version"])
        and (proto.get("files_sha256") or {}) == identity["protocol_files_sha256"]
        and (meta.get("files_sha256") or {}) == identity["metadata_files_sha256"]
        and (sj.get("transport") or {}) == transport_fp
    )

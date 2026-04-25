# host/core/session_store.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List

from host.core.session_identity import normalize_startup_sensors, session_matches

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionPaths:
    root: Path
    commands_jsonl: Path
    streams_dir: Path
    session_json: Path


# ---------------- low-level json helpers ----------------

def load_session_json(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        _log.warning("SESSION_JSON_CORRUPT path=%s error=%s", path, e)
        return {}
    except Exception:
        _log.exception("SESSION_JSON_READ_FAILED path=%s", path)
        return {}


def write_session_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    data = dict(data)

    if path.exists():
        try:
            existing = load_session_json(path)
            data.setdefault("created_at_utc", existing.get("created_at_utc"))
        except Exception:
            pass

    data.setdefault("created_at_utc", now)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------- session creation ----------------

def _normalized_board_uid(identity: Dict[str, Any]) -> str:
    uid = str(identity.get("board_uid_hex") or "").strip().lower()
    return uid if uid else "unknown"


def _board_dir_name(identity: Dict[str, Any]) -> str:
    return f"board_uid_{_normalized_board_uid(identity)}"


def _board_sessions_dir(base_dir: Path, *, identity: Dict[str, Any]) -> Path:
    return base_dir / _board_dir_name(identity)

def create_session_dir(
    base_dir: str | Path,
    *,
    identity: Dict[str, Any],
    transport: Dict[str, Any],
    startup_sensors: List[Dict[str, Any]] | None = None,
    initial_sensor_schemas: Dict[str, Dict[str, Any]] | None = None,
    prefix: str = "session",
) -> SessionPaths:
    """
    Create a new session directory and write initial session.json.

    `identity` is a dict produced by the app layer, expected keys:
      - protocol_version: int
      - protocol_files_sha256: dict[str, str]
      - metadata_files_sha256: dict[str, str]
    """
    base_dir = Path(base_dir)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    root = _board_sessions_dir(base_dir, identity=identity) / f"{prefix}_{ts}"
    root.mkdir(parents=True, exist_ok=False)

    normalized_startup_sensors = normalize_startup_sensors(startup_sensors)

    streams_dir = root / "streams"
    streams_dir.mkdir(parents=True, exist_ok=True)

    paths = SessionPaths(
        root=root,
        commands_jsonl=root / "commands.jsonl",
        streams_dir=streams_dir,
        session_json=root / "session.json",
    )

    now = datetime.now(timezone.utc).isoformat()
    write_session_json(
        paths.session_json,
        {
            "created_at_utc": now,
            "protocol": {
                "protocol_version": int(identity["protocol_version"]),
                **(
                    {"board_uid_hex": str(identity["board_uid_hex"]).lower()}
                    if identity.get("board_uid_hex")
                    else {}
                ),
                **(
                    {"startup_sensors": normalized_startup_sensors}
                    if startup_sensors is not None
                    else {}
                ),
                "files_sha256": dict(identity["protocol_files_sha256"]),
            },
            "metadata": {
                "files_sha256": dict(identity["metadata_files_sha256"]),
            },
            "transport": dict(transport),
            **(
                {"sensors": dict(initial_sensor_schemas)}
                if initial_sensor_schemas
                else {}
            ),
        },
    )

    return paths


# ---------------- misc ----------------

def find_latest_matching_session(
    base_dir: str | Path,
    *,
    identity: Dict[str, Any],
    transport: Dict[str, Any],
    prefix: str = "session",
) -> Optional[Path]:
    base_dir = Path(base_dir)
    if not base_dir.exists():
        return None

    board_dir = _board_sessions_dir(base_dir, identity=identity)
    if not board_dir.exists():
        return None

    candidates: List[Path] = []
    for p in board_dir.iterdir():
        if p.is_dir() and p.name.startswith(prefix + "_"):
            sj = p / "session.json"
            if sj.exists() and session_matches(sj, identity=identity, transport_fp=transport):
                candidates.append(p)

    if not candidates:
        return None

    return max(candidates)

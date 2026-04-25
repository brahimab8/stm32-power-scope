from __future__ import annotations

from collections import deque
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from host.app.config import PowerScopeConfig
from host.app.runner import AppRun, close_run, start_run
from host.app.transport_index import TransportIndex
from host.core.context import Context
from host.core.session_store import load_session_json
from host.core.recording.history import load_sensor_stream_csv
from host.core.errors import DeviceDisconnectedError, PowerScopeError, ProtocolCommunicationError
from host.protocol.errors import CommandFailed, CommandTimeout, ProtocolError, SendFailed
from host.transport.errors import TransportError


class _LiveReadingBuffer:
    def __init__(self, maxlen: int = 4096):
        self._lock = threading.RLock()
        self._queue: deque[dict[str, Any]] = deque(maxlen=int(maxlen))

    def on_reading(self, runtime_id: int, reading) -> None:
        payload = reading.as_dict() if reading is not None else None
        item = {
            "runtime_id": int(runtime_id),
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "reading": payload,
        }
        with self._lock:
            self._queue.append(item)

    def drain(self, *, sensor_runtime_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        take = max(1, int(limit))
        with self._lock:
            while self._queue and len(out) < take:
                item = self._queue.popleft()
                if sensor_runtime_id is not None and int(item.get("runtime_id", -1)) != int(sensor_runtime_id):
                    continue
                out.append(item)
        return out

    def close(self) -> None:
        with self._lock:
            self._queue.clear()


@dataclass(frozen=True)
class BoardRef:
    board_id: str
    transport_type_id: int
    transport_label: str
    transport_overrides: Dict[str, Any]


@dataclass
class _BoardEntry:
    ref: BoardRef
    run: AppRun
    live_buffer: _LiveReadingBuffer


class BoardManager:
    """
    Manages multiple long-lived board sessions inside one daemon process.
    """

    def __init__(
        self,
        *,
        metadata_dir: str,
        protocol_dir: str,
        sessions_base_dir: Path,
        session_prefix: str = "session",
    ):
        self._metadata_dir = metadata_dir
        self._protocol_dir = protocol_dir
        self._sessions_base_dir = Path(sessions_base_dir)
        self._session_prefix = session_prefix

        self._context = Context.load(metadata_dir, protocol_dir)
        self._tindex = TransportIndex.from_context(self._context)

        self._lock = threading.RLock()
        self._boards: Dict[int, _BoardEntry] = {}
        self._next_board_id = 1

    def resolve_transport_type_id(self, label: str) -> int:
        return self._tindex.resolve_type_id_by_label(label)

    def transport_catalog(self) -> dict[str, Any]:
        return {
            "transports": [
                {
                    "type_id": int(tid),
                    "label": meta.label,
                    "driver": meta.driver,
                    "key_param": getattr(meta, "key_param", None),
                    "params": getattr(meta, "params", {}) or {},
                }
                for tid, meta in sorted(self._tindex.catalog().items(), key=lambda kv: kv[0])
            ]
        }

    def connect_board(
        self,
        *,
        transport_type_id: int,
        transport_overrides: Dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            
            # Check for duplicate transport before allocating a board_id
            for entry in self._boards.values():
                if (
                    entry.ref.transport_type_id == int(transport_type_id)
                    and entry.ref.transport_overrides == dict(transport_overrides)
                ):
                    raise PowerScopeError(
                        f"A board with this transport is already connected.",
                        hint=f"Disconnect board '{entry.ref.board_id}' first before reconnecting.",
                    )

            board_id = self._next_board_id
            self._next_board_id += 1
            if board_id in self._boards:
                raise PowerScopeError(
                    f"Board '{board_id}' is already connected.",
                    hint="Internal error: duplicate board_id.",
                )

        cfg = PowerScopeConfig(
            metadata_dir=self._metadata_dir,
            protocol_dir=self._protocol_dir,
            transport_type_id=int(transport_type_id),
            transport_overrides=dict(transport_overrides),
        )

        live_buffer = _LiveReadingBuffer()

        run = start_run(
            cfg,
            sessions_base_dir=self._sessions_base_dir,
            prefix=self._session_prefix,
            context=self._context,
            extra_sinks=[live_buffer],
        )

        meta = self._tindex.meta_for_type_id(int(transport_type_id))
        entry = _BoardEntry(
            ref=BoardRef(
                board_id=board_id,
                transport_type_id=int(transport_type_id),
                transport_label=meta.label,
                transport_overrides=dict(transport_overrides),
            ),
            run=run,
            live_buffer=live_buffer,
        )

        with self._lock:
            self._boards[board_id] = entry

        return self.describe_board(board_id)

    def disconnect_board(self, board_id: int) -> dict[str, Any]:
        with self._lock:
            entry = self._boards.pop(board_id, None)

        if entry is None:
            raise PowerScopeError(f"Unknown board '{board_id}'.")

        try:
            status = entry.run.controller.status()
            for sensor in status.sensors:
                if sensor.streaming:
                    try:
                        entry.run.controller.stop_stream(sensor.runtime_id)
                    except Exception:
                        pass
        except Exception:
            pass

        close_run(entry.run)
        return {"board_id": board_id, "disconnected": True}

    def list_sessions(self) -> dict[str, Any]:
        base = self._sessions_base_dir
        boards_out = []

        if not base.exists():
            return {"boards": []}

        for board_dir in sorted(base.iterdir()):
            if not board_dir.is_dir() or not board_dir.name.startswith("board_uid_"):
                continue
            board_uid = board_dir.name.removeprefix("board_uid_")
            sessions_out = []

            for session_dir in sorted(board_dir.iterdir(), reverse=True):
                if not session_dir.is_dir():
                    continue
                sj_path = session_dir / "session.json"
                if not sj_path.exists():
                    continue

                sj = load_session_json(sj_path)
                if not sj:
                    continue

                sensors_raw = sj.get("sensors") or {}
                sensors_summary = []
                for rid, s in sensors_raw.items():
                    if not isinstance(s, dict):
                        continue

                    stream_files_raw = s.get("stream_files") or []
                    stream_files_info = []
                    for rel in stream_files_raw:
                        full = session_dir / rel
                        if not full.exists():
                            continue
                        # Filename is like "streams/sensor_1/20260419T143243Z.csv"
                        # Parse timestamp from the stem
                        stem = full.stem  # "20260419T143243Z"
                        try:
                            dt = datetime.strptime(stem, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                            ts_label = dt.strftime("%Y-%m-%d  %H:%M:%S UTC")
                        except Exception:
                            ts_label = stem
                        stream_files_info.append({
                            "rel_path": rel,
                            "filename": full.name,
                            "ts_label": ts_label,
                            "size_bytes": full.stat().st_size,
                        })

                    sensors_summary.append({
                        "sensor_runtime_id": int(rid),
                        "sensor_type_id": s.get("sensor_type_id"),
                        "sensor_name": s.get("sensor_name", ""),
                        "channel_count": len(s.get("channels") or []),
                        "has_data": bool(stream_files_info),
                        "stream_files": stream_files_info,   # full info now
                        "stream_file_count": len(stream_files_info),
                    })
                transport = sj.get("transport") or {}
                sessions_out.append({
                    # Relative path — board_uid_X/session_ts — unique, self-locating
                    "session_id": f"{board_dir.name}/{session_dir.name}",
                    "created_at_utc": sj.get("created_at_utc"),
                    "transport_label": transport.get("label", ""),
                    "transport_driver": transport.get("driver", ""),
                    "sensors": sensors_summary,
                })

            if sessions_out:
                boards_out.append({
                    "board_uid_hex": board_uid,
                    "session_count": len(sessions_out),
                    "sessions": sessions_out,
                })

        return {"boards": boards_out}


    def get_session_sensor_history(
        self,
        *,
        session_id: str,
        sensor_runtime_id: int,
        limit: int = 10000,
        stream_file: str | None = None,  # rel_path; None = all files concatenated
    ) -> dict[str, Any]:
        session_dir = self._sessions_base_dir / session_id
        sj_path = session_dir / "session.json"

        if not session_dir.is_dir() or not sj_path.exists():
            raise PowerScopeError(f"Session '{session_id}' not found.")

        sj = load_session_json(sj_path)
        sensors = sj.get("sensors") or {}
        sensor = sensors.get(str(sensor_runtime_id))
        if not sensor:
            raise PowerScopeError(f"Sensor runtime_id={sensor_runtime_id} not in session '{session_id}'.")

        channel_specs = [
            {
                "channel_id": ch["id"],
                "name": ch.get("name", f"ch_{ch['id']}"),
                "unit": ch.get("unit", ""),
                "is_measured": ch.get("is_measured", True),
                "lsb": ch.get("lsb", 1.0),
                "scale": ch.get("scale", 1.0),
                "compute": ch.get("compute"),
            }
            for ch in (sensor.get("channels") or [])
        ]

        stream_files = sensor.get("stream_files") or []
        if not stream_files:
            return {"session_id": session_id, "sensor_runtime_id": sensor_runtime_id, "items": []}

        # Filter to specific file or use all
        if stream_file is not None:
            targets = [stream_file] if stream_file in stream_files else []
        else:
            targets = list(stream_files)

        all_items = []
        for rel_path in targets:
            csv_path = session_dir / rel_path
            if not csv_path.exists():
                continue
            rows = load_sensor_stream_csv(
                csv_path,
                sensor_type_id=sensor.get("sensor_type_id", 0),
                sensor_name=sensor.get("sensor_name", ""),
                channel_specs=channel_specs,
                max_rows=limit - len(all_items),
            )
            all_items.extend(rows)
            if len(all_items) >= limit:
                break

        return {
            "session_id": session_id,
            "sensor_runtime_id": sensor_runtime_id,
            "sensor_name": sensor.get("sensor_name", ""),
            "items": all_items,
        }

    def shutdown_all(self) -> None:
        with self._lock:
            entries = list(self._boards.values())
            self._boards.clear()

        for entry in entries:
            close_run(entry.run)

    def list_boards(self) -> dict[str, Any]:
        with self._lock:
            ids = sorted(self._boards.keys())
        return {"boards": [self.describe_board(board_id) for board_id in ids]}

    def describe_board(self, board_id: int) -> dict[str, Any]:
        entry = self._require(board_id)
        st = entry.run.controller.status()

        return {
            "board_id": entry.ref.board_id,
            "transport": {
                "type_id": entry.ref.transport_type_id,
                "label": entry.ref.transport_label,
                "overrides": dict(entry.ref.transport_overrides),
            },
            "session_dir": str(entry.run.session.root),
            "board_uid_hex": getattr(st, "board_uid_hex", None),
            "status": asdict(st),
        }

    def refresh_sensors(self, board_id: str) -> dict[str, Any]:
        entry = self._require(board_id)
        return self._guard_board_operation(
            entry,
            operation="refresh_sensors",
            fn=lambda: {
                "board_id": entry.ref.board_id,
                "sensors": [asdict(s) for s in entry.run.controller.refresh_sensors()],
            },
        )

    def set_period(self, board_id: str, *, sensor_runtime_id: int, period_ms: int) -> dict[str, Any]:
        entry = self._require(board_id)
        return self._guard_board_operation(
            entry,
            operation="set_period",
            fn=lambda: self._set_period_impl(entry, sensor_runtime_id=int(sensor_runtime_id), period_ms=int(period_ms)),
        )

    def get_period(self, board_id: str, *, sensor_runtime_id: int) -> dict[str, Any]:
        entry = self._require(board_id)
        return self._guard_board_operation(
            entry,
            operation="get_period",
            fn=lambda: self._get_period_impl(entry, sensor_runtime_id=int(sensor_runtime_id)),
        )

    def start_stream(self, board_id: str, *, sensor_runtime_id: int) -> dict[str, Any]:
        entry = self._require(board_id)
        return self._guard_board_operation(
            entry,
            operation="start_stream",
            fn=lambda: self._start_stream_impl(entry, sensor_runtime_id=int(sensor_runtime_id)),
        )

    def stop_stream(self, board_id: str, *, sensor_runtime_id: int) -> dict[str, Any]:
        entry = self._require(board_id)
        return self._guard_board_operation(
            entry,
            operation="stop_stream",
            fn=lambda: self._stop_stream_impl(entry, sensor_runtime_id=int(sensor_runtime_id)),
        )

    def read_sensor(self, board_id: str, *, sensor_runtime_id: int) -> dict[str, Any]:
        entry = self._require(board_id)
        return self._guard_board_operation(
            entry,
            operation="read_sensor",
            fn=lambda: self._read_sensor_impl(entry, sensor_runtime_id=int(sensor_runtime_id)),
        )

    def get_uptime(self, board_id: str) -> dict[str, Any]:
        entry = self._require(board_id)
        return self._guard_board_operation(
            entry,
            operation="uptime",
            fn=lambda: self._uptime_impl(entry),
        )

    def drain_readings(
        self,
        board_id: str,
        *,
        sensor_runtime_id: int | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        entry = self._require(board_id)
        items = entry.live_buffer.drain(sensor_runtime_id=sensor_runtime_id, limit=limit)
        return {
            "board_id": entry.ref.board_id,
            "items": items,
        }

    @staticmethod
    def _set_period_impl(entry: _BoardEntry, *, sensor_runtime_id: int, period_ms: int) -> dict[str, Any]:
        entry.run.controller.set_period(int(sensor_runtime_id), period_ms=int(period_ms))
        return {
            "board_id": entry.ref.board_id,
            "sensor_runtime_id": int(sensor_runtime_id),
            "period_ms": int(period_ms),
        }

    @staticmethod
    def _get_period_impl(entry: _BoardEntry, *, sensor_runtime_id: int) -> dict[str, Any]:
        period_ms = entry.run.controller.get_period(int(sensor_runtime_id))
        return {
            "board_id": entry.ref.board_id,
            "sensor_runtime_id": int(sensor_runtime_id),
            "period_ms": int(period_ms),
        }

    @staticmethod
    def _start_stream_impl(entry: _BoardEntry, *, sensor_runtime_id: int) -> dict[str, Any]:
        entry.run.controller.start_stream(int(sensor_runtime_id))
        return {
            "board_id": entry.ref.board_id,
            "sensor_runtime_id": int(sensor_runtime_id),
            "streaming": True,
        }

    @staticmethod
    def _stop_stream_impl(entry: _BoardEntry, *, sensor_runtime_id: int) -> dict[str, Any]:
        entry.run.controller.stop_stream(int(sensor_runtime_id))
        return {
            "board_id": entry.ref.board_id,
            "sensor_runtime_id": int(sensor_runtime_id),
            "streaming": False,
        }

    @staticmethod
    def _read_sensor_impl(entry: _BoardEntry, *, sensor_runtime_id: int) -> dict[str, Any]:
        reading = entry.run.controller.read_sensor(int(sensor_runtime_id))
        return {
            "board_id": entry.ref.board_id,
            "sensor_runtime_id": int(sensor_runtime_id),
            "reading": reading.as_dict() if reading is not None else None,
        }

    @staticmethod
    def _uptime_impl(entry: _BoardEntry) -> dict[str, Any]:
        uptime_ms = entry.run.controller.get_uptime()
        return {
            "board_id": entry.ref.board_id,
            "uptime_ms": int(uptime_ms),
        }

    def _guard_board_operation(self, entry: _BoardEntry, *, operation: str, fn) -> dict[str, Any]:
        try:
            return fn()
        except PowerScopeError:
            raise
        except (SendFailed, CommandTimeout, CommandFailed, TransportError, ProtocolError) as e:
            self._drop_dead_board(entry.ref.board_id, entry)

            message = str(e)
            is_disconnected = isinstance(e, (SendFailed, TransportError)) or (
                "not open" in message.lower() or "closed by peer" in message.lower()
            )

            if is_disconnected:
                raise DeviceDisconnectedError(
                    f"Board '{entry.ref.board_id}' disconnected during {operation}.",
                    hint=(
                        f"Reconnect it: powerscope ctl boards connect --board-id {entry.ref.board_id} "
                        f"--transport {entry.ref.transport_label} ..."
                    ),
                    details={
                        "board_id": entry.ref.board_id,
                        "operation": operation,
                        "cause": message,
                    },
                )

            raise ProtocolCommunicationError(
                f"Board '{entry.ref.board_id}' operation '{operation}' failed.",
                hint="Check target availability and reconnect board if needed.",
                details={
                    "board_id": entry.ref.board_id,
                    "operation": operation,
                    "cause": message,
                },
            )

    def _drop_dead_board(self, board_id: str, entry: _BoardEntry) -> None:
        with self._lock:
            current = self._boards.get(board_id)
            if current is entry:
                self._boards.pop(board_id, None)
        close_run(entry.run)

    def _require(self, board_id: int) -> _BoardEntry:
        with self._lock:
            entry = self._boards.get(board_id)
        if entry is None:
            raise PowerScopeError(f"Unknown board '{board_id}'.")
        return entry



from __future__ import annotations

from collections import deque
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from host.app.config import PowerScopeConfig
from host.app.runner import AppRun, close_run, start_run
from host.app.sinks import StreamRecordingSink
from host.app.transport_index import TransportIndex
from host.core.context import Context
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
        self._boards: Dict[str, _BoardEntry] = {}

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
        board_id: str,
        transport_type_id: int,
        transport_overrides: Dict[str, Any],
    ) -> dict[str, Any]:
        board_key = self._normalize_board_id(board_id)

        with self._lock:
            if board_key in self._boards:
                raise PowerScopeError(
                    f"Board '{board_key}' is already connected.",
                    hint="Use a different board_id or disconnect it first.",
                )

        cfg = PowerScopeConfig(
            metadata_dir=self._metadata_dir,
            protocol_dir=self._protocol_dir,
            transport_type_id=int(transport_type_id),
            transport_overrides=dict(transport_overrides),
        )

        run = start_run(
            cfg,
            sessions_base_dir=self._sessions_base_dir,
            prefix=self._session_prefix,
            context=self._context,
        )

        live_buffer = _LiveReadingBuffer()
        run.controller.add_sink(live_buffer)

        run.controller.add_sink(
            StreamRecordingSink(
                recorder=run.recorder,
                session_json_path=run.session.session_json,
                workspace_root=run.session.root,
            )
        )

        try:
            run.controller.start()
        except Exception:
            close_run(run)
            raise

        meta = self._tindex.meta_for_type_id(int(transport_type_id))
        entry = _BoardEntry(
            ref=BoardRef(
                board_id=board_key,
                transport_type_id=int(transport_type_id),
                transport_label=meta.label,
                transport_overrides=dict(transport_overrides),
            ),
            run=run,
            live_buffer=live_buffer,
        )

        with self._lock:
            self._boards[board_key] = entry

        return self.describe_board(board_key)

    def disconnect_board(self, board_id: str) -> dict[str, Any]:
        board_key = self._normalize_board_id(board_id)

        with self._lock:
            entry = self._boards.pop(board_key, None)

        if entry is None:
            raise PowerScopeError(f"Unknown board '{board_key}'.")

        close_run(entry.run)
        return {"board_id": board_key, "disconnected": True}

    def rename_board(self, board_id: str, *, new_board_id: str) -> dict[str, Any]:
        old_key = self._normalize_board_id(board_id)
        new_key = self._normalize_board_id(new_board_id)

        with self._lock:
            entry = self._boards.get(old_key)
            if entry is None:
                raise PowerScopeError(f"Unknown board '{old_key}'.")

            if old_key == new_key:
                return self.describe_board(old_key)

            if new_key in self._boards:
                raise PowerScopeError(
                    f"Board '{new_key}' already exists.",
                    hint="Pick a different board name.",
                )

            updated_entry = _BoardEntry(
                ref=BoardRef(
                    board_id=new_key,
                    transport_type_id=entry.ref.transport_type_id,
                    transport_label=entry.ref.transport_label,
                    transport_overrides=dict(entry.ref.transport_overrides),
                ),
                run=entry.run,
                live_buffer=entry.live_buffer,
            )
            self._boards.pop(old_key, None)
            self._boards[new_key] = updated_entry

        return self.describe_board(new_key)

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

    def describe_board(self, board_id: str) -> dict[str, Any]:
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

    def _require(self, board_id: str) -> _BoardEntry:
        board_key = self._normalize_board_id(board_id)
        with self._lock:
            entry = self._boards.get(board_key)
        if entry is None:
            raise PowerScopeError(f"Unknown board '{board_key}'.")
        return entry

    @staticmethod
    def _normalize_board_id(board_id: str) -> str:
        out = str(board_id).strip()
        if not out:
            raise PowerScopeError("board_id is required.")
        return out

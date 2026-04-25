from __future__ import annotations
import os
import json
import logging
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse, parse_qs

from host.core.session_store import load_session_json
from host.core.recording.history import load_sensor_stream_csv
from host.core.errors import PowerScopeError
from host.daemon.manager import BoardManager


class ControlApiServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], manager: BoardManager, logger: logging.Logger | None = None):
        self.manager = manager
        self.logger = logger or logging.getLogger(__name__)
        super().__init__(server_address, _make_handler())


class _ControlHandler(BaseHTTPRequestHandler):
    server: ControlApiServer

    def log_message(self, fmt: str, *args: Any) -> None:
        self.server.logger.info("CONTROL_API " + fmt, *args)

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        manager = self.server.manager

        try:
            # --- Historical readings endpoint ---
            # /boards/{board_id}/sensor/{sensor_runtime_id}/history
            if method == "GET" and path.startswith("/boards/") and "/sensor/" in path and path.endswith("/history"):
                parts = [p for p in path.split("/") if p]
                if len(parts) != 5 or parts[0] != "boards" or parts[2] != "sensor" or parts[4] != "history":
                    self._not_found()
                    return
                try:
                    board_id = int(parts[1])
                except Exception:
                    self._not_found()
                    return
                sensor_runtime_id = parts[3]

                query = parse_qs(urlparse(self.path).query)
                limit = None
                if "limit" in query:
                    try:
                        limit = int(query["limit"][0])
                    except Exception:
                        pass

                board_info = manager.describe_board(board_id)
                session_dir = board_info.get("session_dir")
                if not session_dir:
                    self._not_found()
                    return

                session_json = os.path.join(session_dir, "session.json")
                session = load_session_json(Path(session_json))
                sensors = session.get("sensors", {})
                sensor = sensors.get(str(sensor_runtime_id))
                if not sensor:
                    self._not_found()
                    return

                # Build channel specs directly from session.json — no encode needed
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
                    for ch in sensor.get("channels", [])
                ]

                stream_files = sensor.get("stream_files", [])
                if not stream_files:
                    self._ok({"items": []})
                    return

                stream_path = os.path.join(session_dir, stream_files[-1])
                readings = load_sensor_stream_csv(
                    Path(stream_path),
                    sensor_type_id=sensor.get("sensor_type_id", 0),
                    sensor_name=sensor.get("sensor_name", ""),
                    channel_specs=channel_specs,
                    max_rows=limit if limit else 10000,
                )
                self._ok({"items": readings})
                return

            if method == "GET" and path == "/sessions":
                self._ok(manager.list_sessions())
                return

            # /sessions/{board_uid_dir}/{session_dir}/sensor/{sensor_runtime_id}/history
            if method == "GET" and "/sensor/" in path and path.endswith("/history"):
                parts = [p for p in path.split("/") if p]
                # parts: ["sessions", "board_uid_X", "session_ts", "sensor", "rid", "history"]
                if len(parts) == 6 and parts[0] == "sessions" and parts[3] == "sensor" and parts[5] == "history":
                    query = parse_qs(urlparse(self.path).query)
                    limit = 10000
                    if "limit" in query:
                        try:
                            limit = int(query["limit"][0])
                        except Exception:
                            pass
                    stream_file = query.get("stream_file", [None])[0]  # None = all files
                    session_id = f"{parts[1]}/{parts[2]}"
                    self._ok(manager.get_session_sensor_history(
                        session_id=session_id,
                        sensor_runtime_id=int(parts[4]),
                        limit=limit,
                        stream_file=stream_file,
                    ))
                    return

                
            if method == "GET" and path == "/health":
                self._ok({"ok": True})
                return

            if method == "GET" and path == "/transports":
                self._ok(manager.transport_catalog())
                return

            if method == "GET" and path == "/boards":
                self._ok(manager.list_boards())
                return

            if method == "POST" and path == "/boards/connect":
                body = self._read_json_body()

                transport_type_id = body.get("transport_type_id")
                transport_label = body.get("transport") or body.get("transport_label")

                if transport_type_id is None:
                    if transport_label is None:
                        raise PowerScopeError("One of 'transport_type_id' or 'transport' is required.")
                    transport_type_id = manager.resolve_transport_type_id(str(transport_label))

                overrides = body.get("overrides") or {}
                if not isinstance(overrides, dict):
                    raise PowerScopeError("'overrides' must be a JSON object.")

                out = manager.connect_board(
                    transport_type_id=int(transport_type_id),
                    transport_overrides=dict(overrides),
                )
                self._ok(out, status=HTTPStatus.CREATED)
                return

            board_route = self._parse_board_route(path)
            if board_route is None:
                self._not_found()
                return

            board_id_str, action = board_route
            try:
                board_id = int(board_id_str)
            except Exception:
                self._not_found()
                return

            if method == "GET" and action == "status":
                self._ok(manager.describe_board(board_id))
                return

            if method == "POST" and action == "disconnect":
                self._ok(manager.disconnect_board(board_id))
                return

            if method == "POST" and action in {"refresh_sensors", "read_sensor", "set_period", "get_period", "start_stream", "stop_stream", "uptime", "drain_readings"}:
                body = self._read_json_body()
                self._ok(self._invoke_board_action(manager, board_id, action, body))
                return

            self._not_found()

        except PowerScopeError as e:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {
                    "ok": False,
                    "error": {
                        "code": e.code,
                        "message": e.message,
                        "hint": e.hint,
                        "details": e.details,
                    },
                },
            )
        except Exception as e:
            self.server.logger.exception("CONTROL_API_UNHANDLED_ERROR")
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "ok": False,
                    "error": {
                        "code": "internal_error",
                        "message": str(e),
                    },
                },
            )

    def _invoke_board_action(self, manager: BoardManager, board_id: str, action: str, body: dict[str, Any]) -> dict[str, Any]:
        actions: dict[str, Callable[[], dict[str, Any]]] = {
            "refresh_sensors": lambda: manager.refresh_sensors(board_id),
            "uptime": lambda: manager.get_uptime(board_id),
            "read_sensor": lambda: manager.read_sensor(
                board_id,
                sensor_runtime_id=int(self._require_int(body, "sensor_runtime_id")),
            ),
            "set_period": lambda: manager.set_period(
                board_id,
                sensor_runtime_id=int(self._require_int(body, "sensor_runtime_id")),
                period_ms=int(self._require_int(body, "period_ms")),
            ),
            "get_period": lambda: manager.get_period(
                board_id,
                sensor_runtime_id=int(self._require_int(body, "sensor_runtime_id")),
            ),
            "start_stream": lambda: manager.start_stream(
                board_id,
                sensor_runtime_id=int(self._require_int(body, "sensor_runtime_id")),
            ),
            "stop_stream": lambda: manager.stop_stream(
                board_id,
                sensor_runtime_id=int(self._require_int(body, "sensor_runtime_id")),
            ),
            "drain_readings": lambda: manager.drain_readings(
                board_id,
                sensor_runtime_id=self._optional_int(body, "sensor_runtime_id"),
                limit=int(body.get("limit", 200)),
            ),
        }
        fn = actions.get(action)
        if fn is None:
            raise PowerScopeError(f"Unsupported board action '{action}'.")
        return fn()

    def _read_json_body(self) -> dict[str, Any]:
        length_s = self.headers.get("Content-Length", "0")
        try:
            length = int(length_s)
        except ValueError:
            raise PowerScopeError("Invalid Content-Length header.") from None

        raw = self.rfile.read(max(length, 0)) if length > 0 else b"{}"

        if not raw:
            return {}

        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            raise PowerScopeError("Request body must be valid JSON.") from None

        if not isinstance(body, dict):
            raise PowerScopeError("Request body must be a JSON object.")

        return body

    @staticmethod
    def _parse_board_route(path: str) -> tuple[str, str] | None:
        parts = [p for p in path.split("/") if p]
        if len(parts) != 3 or parts[0] != "boards":
            return None
        return parts[1], parts[2]

    @staticmethod
    def _require_str(body: dict[str, Any], key: str) -> str:
        value = body.get(key)
        if value is None:
            raise PowerScopeError(f"'{key}' is required.")
        out = str(value).strip()
        if not out:
            raise PowerScopeError(f"'{key}' is required.")
        return out

    @staticmethod
    def _require_int(body: dict[str, Any], key: str) -> int:
        value = body.get(key)
        if value is None:
            raise PowerScopeError(f"'{key}' is required.")
        try:
            return int(value)
        except Exception:
            raise PowerScopeError(f"'{key}' must be an integer.") from None

    @staticmethod
    def _optional_int(body: dict[str, Any], key: str) -> int | None:
        value = body.get(key)
        if value is None:
            return None
        try:
            return int(value)
        except Exception:
            raise PowerScopeError(f"'{key}' must be an integer.") from None

    def _ok(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        self._json(status, {"ok": True, "data": data})

    def _not_found(self) -> None:
        self._json(
            HTTPStatus.NOT_FOUND,
            {
                "ok": False,
                "error": {
                    "code": "not_found",
                    "message": "Route not found.",
                },
            },
        )

    def _json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _make_handler() -> type[_ControlHandler]:
    return _ControlHandler
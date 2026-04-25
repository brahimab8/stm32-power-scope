from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from host.core.errors import PowerScopeError
from host.daemon.api import ControlApiServer


@dataclass
class _FakeStatus:
    connected: bool = True


class FakeManager:
    def __init__(self) -> None:
        self.connect_calls: list[tuple[int, dict]] = []
        self._next_board_id = 1

    def transport_catalog(self):
        return {"transports": [{"type_id": 1, "label": "uart", "driver": "uart"}]}

    def list_boards(self):
        return {"boards": []}

    def resolve_transport_type_id(self, label: str) -> int:
        if label == "uart":
            return 1
        raise PowerScopeError("unknown transport")

    def connect_board(self, *, transport_type_id: int, transport_overrides: dict):
        board_id = self._next_board_id
        self._next_board_id += 1
        self.connect_calls.append((transport_type_id, dict(transport_overrides)))
        return {
            "board_id": board_id,
            "transport": {"type_id": int(transport_type_id), "label": "uart", "overrides": dict(transport_overrides)},
            "session_dir": "tmp/session",
            "status": {"connected": True},
        }

    def describe_board(self, board_id: int):
        return {"board_id": board_id, "status": {"connected": True}}

    def disconnect_board(self, board_id: int):
        return {"board_id": board_id, "disconnected": True}

    def refresh_sensors(self, board_id: int):
        return {"board_id": board_id, "sensors": []}

    def get_uptime(self, board_id: int):
        return {"board_id": board_id, "uptime_ms": 123}

    def read_sensor(self, board_id: int, *, sensor_runtime_id: int):
        return {"board_id": board_id, "sensor_runtime_id": sensor_runtime_id, "reading": {}}

    def set_period(self, board_id: int, *, sensor_runtime_id: int, period_ms: int):
        return {"board_id": board_id, "sensor_runtime_id": sensor_runtime_id, "period_ms": period_ms}

    def get_period(self, board_id: int, *, sensor_runtime_id: int):
        return {"board_id": board_id, "sensor_runtime_id": sensor_runtime_id, "period_ms": 1000}

    def start_stream(self, board_id: int, *, sensor_runtime_id: int):
        return {"board_id": board_id, "sensor_runtime_id": sensor_runtime_id, "streaming": True}

    def stop_stream(self, board_id: int, *, sensor_runtime_id: int):
        return {"board_id": board_id, "sensor_runtime_id": sensor_runtime_id, "streaming": False}

    def drain_readings(self, board_id: int, *, sensor_runtime_id: int | None = None, limit: int = 200):
        return {"board_id": board_id, "items": [], "sensor_runtime_id": sensor_runtime_id, "limit": limit}


@contextmanager
def running_api(manager: FakeManager):
    server = ControlApiServer(("127.0.0.1", 0), manager=manager)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"
    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)


def _request_json(base_url: str, method: str, path: str, body: dict | None = None):
    raw = None
    if body is not None:
        raw = json.dumps(body).encode("utf-8")
    req = Request(f"{base_url}{path}", data=raw, method=method, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=2.0) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
        return resp.status, payload


def _request_json_error(base_url: str, method: str, path: str, body: dict | None = None):
    raw = None
    if body is not None:
        raw = json.dumps(body).encode("utf-8")
    req = Request(f"{base_url}{path}", data=raw, method=method, headers={"Content-Type": "application/json"})
    with pytest.raises(HTTPError) as exc:
        urlopen(req, timeout=2.0)
    payload = json.loads(exc.value.read().decode("utf-8"))
    return exc.value.code, payload


def test_health_ok():
    manager = FakeManager()
    with running_api(manager) as base_url:
        status, payload = _request_json(base_url, "GET", "/health")

    assert status == 200
    assert payload["ok"] is True
    assert payload["data"] == {"ok": True}


def test_connect_by_transport_label_resolves_and_passes_overrides():
    manager = FakeManager()
    with running_api(manager) as base_url:
        status, payload = _request_json(
            base_url,
            "POST",
            "/boards/connect",
            {
                "transport": "uart",
                "overrides": {"port": "COM4"},
            },
        )

    assert status == 201
    assert payload["ok"] is True
    assert payload["data"]["board_id"] == 1
    assert manager.connect_calls == [(1, {"port": "COM4"})]


def test_connect_rejects_non_object_overrides():
    manager = FakeManager()
    with running_api(manager) as base_url:
        status, payload = _request_json_error(
            base_url,
            "POST",
            "/boards/connect",
            {
                "transport": "uart",
                "overrides": ["not", "an", "object"],
            },
        )

    assert status == 400
    assert payload["ok"] is False
    assert "must be a JSON object" in payload["error"]["message"]


def test_read_sensor_requires_sensor_runtime_id():
    manager = FakeManager()
    with running_api(manager) as base_url:
        status, payload = _request_json_error(
            base_url,
            "POST",
            "/boards/1/read_sensor",
            {},
        )

    assert status == 400
    assert payload["ok"] is False
    assert "sensor_runtime_id" in payload["error"]["message"]


def test_unknown_route_returns_not_found():
    manager = FakeManager()
    with running_api(manager) as base_url:
        status, payload = _request_json_error(base_url, "GET", "/nope")

    assert status == 404
    assert payload["ok"] is False
    assert payload["error"]["code"] == "not_found"
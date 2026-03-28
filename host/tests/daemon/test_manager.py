from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

import host.daemon.manager as manager_mod
from host.core.errors import DeviceDisconnectedError, PowerScopeError, ProtocolCommunicationError
from host.protocol.errors import CommandTimeout, SendFailed


@dataclass
class FakeStatus:
    connected: bool = True


class FakeReading:
    def __init__(self, value: int):
        self.value = int(value)

    def as_dict(self):
        return {"value": self.value}


class FakeController:
    def __init__(self):
        self.sinks = []
        self.started = False
        self.raise_on_uptime: Exception | None = None

    def add_sink(self, sink):
        self.sinks.append(sink)

    def start(self):
        self.started = True

    def status(self):
        return FakeStatus(connected=True)

    def get_uptime(self):
        if self.raise_on_uptime is not None:
            raise self.raise_on_uptime
        return 123


class FakeTransportIndex:
    def catalog(self):
        return {1: SimpleNamespace(label="uart", driver="uart", key_param="port", params={"port": {"type": "str"}})}

    def resolve_type_id_by_label(self, label: str) -> int:
        if label == "uart":
            return 1
        raise PowerScopeError("unknown transport")

    def meta_for_type_id(self, type_id: int):
        if int(type_id) != 1:
            raise PowerScopeError("unknown transport")
        return SimpleNamespace(label="uart", driver="uart", key_param="port", params={"port": {"type": "str"}})


@pytest.fixture
def manager_env(monkeypatch, tmp_path: Path):
    close_calls = []

    monkeypatch.setattr(manager_mod.Context, "load", staticmethod(lambda *_a, **_k: object()))
    monkeypatch.setattr(manager_mod.TransportIndex, "from_context", staticmethod(lambda _ctx: FakeTransportIndex()))
    monkeypatch.setattr(manager_mod, "StreamRecordingSink", lambda **_kwargs: SimpleNamespace(kind="record_sink"))

    def fake_start_run(_cfg, *, sessions_base_dir, prefix, context):
        root = Path(sessions_base_dir) / f"{prefix}_fake"
        root.mkdir(parents=True, exist_ok=True)
        session = SimpleNamespace(root=root, session_json=root / "session.json")
        return SimpleNamespace(controller=FakeController(), recorder=SimpleNamespace(), session=session)

    def fake_close_run(run):
        close_calls.append(run)

    monkeypatch.setattr(manager_mod, "start_run", fake_start_run)
    monkeypatch.setattr(manager_mod, "close_run", fake_close_run)

    mgr = manager_mod.BoardManager(
        metadata_dir="meta",
        protocol_dir="proto",
        sessions_base_dir=tmp_path,
        session_prefix="session",
    )
    return mgr, close_calls


def test_connect_and_disconnect_board(manager_env):
    mgr, close_calls = manager_env

    out = mgr.connect_board(board_id="board1", transport_type_id=1, transport_overrides={"port": "COM4"})
    assert out["board_id"] == "board1"
    assert out["transport"]["label"] == "uart"

    disconnected = mgr.disconnect_board("board1")
    assert disconnected == {"board_id": "board1", "disconnected": True}
    assert len(close_calls) == 1


def test_connect_duplicate_board_id_raises(manager_env):
    mgr, _ = manager_env

    mgr.connect_board(board_id="board1", transport_type_id=1, transport_overrides={})
    with pytest.raises(PowerScopeError, match="already connected"):
        mgr.connect_board(board_id="board1", transport_type_id=1, transport_overrides={})


def test_guard_maps_send_failed_to_device_disconnected(manager_env):
    mgr, close_calls = manager_env

    mgr.connect_board(board_id="board1", transport_type_id=1, transport_overrides={})
    entry = mgr._require("board1")
    entry.run.controller.raise_on_uptime = SendFailed("GET_UPTIME", "not open")

    with pytest.raises(DeviceDisconnectedError, match="disconnected during uptime"):
        mgr.get_uptime("board1")

    assert len(close_calls) == 1
    with pytest.raises(PowerScopeError, match="Unknown board"):
        mgr.describe_board("board1")


def test_guard_maps_timeout_to_protocol_error(manager_env):
    mgr, close_calls = manager_env

    mgr.connect_board(board_id="board1", transport_type_id=1, transport_overrides={})
    entry = mgr._require("board1")
    entry.run.controller.raise_on_uptime = CommandTimeout("GET_UPTIME", 1.0)

    with pytest.raises(ProtocolCommunicationError, match="operation 'uptime' failed"):
        mgr.get_uptime("board1")

    assert len(close_calls) == 1


def test_drain_readings_filters_by_sensor_and_limit(manager_env):
    mgr, _ = manager_env

    mgr.connect_board(board_id="board1", transport_type_id=1, transport_overrides={})
    entry = mgr._require("board1")

    entry.live_buffer.on_reading(1, FakeReading(10))
    entry.live_buffer.on_reading(2, FakeReading(20))
    entry.live_buffer.on_reading(1, FakeReading(30))

    out = mgr.drain_readings("board1", sensor_runtime_id=1, limit=1)
    assert out["board_id"] == "board1"
    assert len(out["items"]) == 1
    assert out["items"][0]["runtime_id"] == 1

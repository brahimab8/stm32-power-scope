from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import host.app.runner as runner_mod
from host.core.errors import PowerScopeError


class FakeTransport:
    def __init__(self):
        self.transport = SimpleNamespace()
        self.params = {}
        self.meta = SimpleNamespace(type_id=1, driver="uart", label="uart")


class FakeTransportFactory:
    def create(self, *, type_id: int, overrides: dict):
        return FakeTransport()


class FakeContext:
    def __init__(self):
        self.transport_factory = FakeTransportFactory()
        self.protocol = SimpleNamespace()
        self.sensors = {}


@pytest.fixture
def fake_cfg(tmp_path: Path):
    return SimpleNamespace(
        metadata_dir="meta",
        protocol_dir="proto",
        transport_type_id=1,
        transport_overrides={"port": "COM4"},
        cmd_timeout_s=1.0,
    ), tmp_path


def test_start_run_fails_before_session_creation_when_uid_missing(monkeypatch, fake_cfg):
    cfg, tmp_path = fake_cfg

    monkeypatch.setattr(runner_mod.Context, "load", staticmethod(lambda *_a, **_k: FakeContext()))
    monkeypatch.setattr(
        runner_mod,
        "_probe_board_startup_identity",
        lambda **_kwargs: (None, [], []),  # uid=None, sensors=[], buffered_frames=[]
    )

    created_session_called = {"value": False}

    def fake_create_session_dir(*_args, **_kwargs):
        created_session_called["value"] = True
        raise AssertionError("create_session_dir should not be called when UID is missing")

    monkeypatch.setattr(runner_mod, "create_session_dir", fake_create_session_dir)

    with pytest.raises(PowerScopeError, match="Unable to read board UID"):
        runner_mod.start_run(cfg, sessions_base_dir=tmp_path, prefix="session")

    assert created_session_called["value"] is False
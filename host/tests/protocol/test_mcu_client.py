from __future__ import annotations

import pytest

from host.protocol.mcu_client import McuClient


class FakeEngine:
    def __init__(self, responses: dict[str, dict]):
        self._responses = responses

    def send_cmd(self, cmd_name: str, **_kwargs):
        return dict(self._responses[cmd_name])


def test_get_uptime_uses_payload_field():
    engine = FakeEngine({"GET_UPTIME": {"status": "ok", "payload": {"uptime_ms": 12345}}})
    client = McuClient(engine)  # type: ignore[arg-type]
    assert client.get_uptime() == 12345


def test_get_period_uses_payload_field():
    engine = FakeEngine({"GET_PERIOD": {"status": "ok", "payload": {"period_ms": 250}}})
    client = McuClient(engine)  # type: ignore[arg-type]
    assert client.get_period(sensor_runtime_id=1) == 250


def test_get_uptime_supports_top_level_field_for_compatibility():
    engine = FakeEngine({"GET_UPTIME": {"status": "ok", "uptime_ms": 777}})
    client = McuClient(engine)  # type: ignore[arg-type]
    assert client.get_uptime() == 777


def test_get_uptime_missing_field_raises():
    engine = FakeEngine({"GET_UPTIME": {"status": "ok", "payload": {}}})
    client = McuClient(engine)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="missing 'uptime_ms'"):
        client.get_uptime()

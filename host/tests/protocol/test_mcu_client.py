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


def test_get_board_uid_hex_from_words_payload():
    engine = FakeEngine(
        {
            "GET_BOARD_UID": {
                "status": "ok",
                "payload": {
                    "uid_w0": 0x04030201,
                    "uid_w1": 0x08070605,
                    "uid_w2": 0x0C0B0A09,
                },
            }
        }
    )
    client = McuClient(engine)  # type: ignore[arg-type]
    assert client.get_board_uid_hex() == "0102030405060708090a0b0c"


def test_get_board_uid_hex_from_raw_fallback_payload():
    engine = FakeEngine(
        {
            "GET_BOARD_UID": {
                "status": "ok",
                "payload": {"raw": "00112233445566778899aabb"},
            }
        }
    )
    client = McuClient(engine)  # type: ignore[arg-type]
    assert client.get_board_uid_hex() == "00112233445566778899aabb"


def test_get_board_uid_hex_missing_fields_raises():
    engine = FakeEngine({"GET_BOARD_UID": {"status": "ok", "payload": {"uid_w0": 1}}})
    client = McuClient(engine)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="missing"):
        client.get_board_uid_hex()

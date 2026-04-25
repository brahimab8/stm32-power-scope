from __future__ import annotations

import json
from pathlib import Path

from host.core.session_store import create_session_dir, find_latest_matching_session
from host.app.session_index import append_sensor_stream_file


IDENTITY = {
    "protocol_version": 1,
    "board_uid_hex": "aabbccddeeff",
    "startup_sensors": [
        {"runtime_id": 1, "type_id": 10},
        {"runtime_id": 2, "type_id": 20},
    ],
    "protocol_files_sha256": {"commands.yml": "p1"},
    "metadata_files_sha256": {"sensors.yml": "m1"},
}

TRANSPORT = {
    "type_id": 1,
    "driver": "uart",
    "label": "uart",
    "params": {"port": "COM4"},
}

INITIAL_SENSOR_SCHEMAS = {
    "1": {
        "sensor_runtime_id": 1,
        "sensor_type_id": 10,
        "sensor_name": "INA219",
        "channels": [
            {"id": 0, "name": "Voltage", "unit": "mV", "is_measured": True},
            {"id": 1, "name": "Current", "unit": "mA", "is_measured": True},
        ],
        "stream_files": [],
    },
    "2": {
        "sensor_runtime_id": 2,
        "sensor_type_id": 20,
        "sensor_name": "INA219",
        "channels": [
            {"id": 0, "name": "Voltage", "unit": "mV", "is_measured": True},
        ],
        "stream_files": [],
    },
}


def test_create_session_dir_uses_board_and_session_hierarchy(tmp_path: Path):
    sp = create_session_dir(
        tmp_path,
        identity=IDENTITY,
        transport=TRANSPORT,
        startup_sensors=IDENTITY["startup_sensors"],
        initial_sensor_schemas=INITIAL_SENSOR_SCHEMAS,
        prefix="session",
    )

    assert sp.root.parent.name == "board_uid_aabbccddeeff"
    assert sp.root.name.startswith("session_")
    assert sp.session_json.exists()

    session_data = json.loads(sp.session_json.read_text(encoding="utf-8"))
    assert session_data.get("protocol", {}).get("startup_sensors") == IDENTITY["startup_sensors"]
    assert session_data.get("sensors") == INITIAL_SENSOR_SCHEMAS
    assert "latest" not in session_data


def test_append_sensor_stream_file_stores_paths_per_sensor(tmp_path: Path):
    sp = create_session_dir(
        tmp_path,
        identity=IDENTITY,
        transport=TRANSPORT,
        startup_sensors=IDENTITY["startup_sensors"],
        initial_sensor_schemas=INITIAL_SENSOR_SCHEMAS,
        prefix="session",
    )

    append_sensor_stream_file(sp.session_json, sensor_runtime_id=1, csv_rel_path="streams/sensor_1/20260416T151401Z.csv")
    append_sensor_stream_file(sp.session_json, sensor_runtime_id=1, csv_rel_path="streams/sensor_1/20260416T151401Z.csv")
    append_sensor_stream_file(sp.session_json, sensor_runtime_id=2, csv_rel_path="streams/sensor_2/20260416T151404Z.csv")

    session_data = json.loads(sp.session_json.read_text(encoding="utf-8"))
    sensors = session_data.get("sensors", {})
    assert sensors["1"]["stream_files"] == ["streams/sensor_1/20260416T151401Z.csv"]
    assert sensors["2"]["stream_files"] == ["streams/sensor_2/20260416T151404Z.csv"]
    assert "latest" not in session_data


def test_find_latest_matching_session_returns_most_recent_in_board(tmp_path: Path):
    s1 = create_session_dir(
        tmp_path,
        identity=IDENTITY,
        transport=TRANSPORT,
        startup_sensors=IDENTITY["startup_sensors"],
        prefix="session",
    )
    s2 = create_session_dir(
        tmp_path,
        identity=IDENTITY,
        transport=TRANSPORT,
        startup_sensors=IDENTITY["startup_sensors"],
        prefix="session",
    )

    found = find_latest_matching_session(
        tmp_path,
        identity=IDENTITY,
        transport=TRANSPORT,
        prefix="session",
    )

    assert found == s2.root
    assert found != s1.root


def test_find_latest_matching_session_ignores_other_board_uid(tmp_path: Path):
    other_identity = {
        **IDENTITY,
        "board_uid_hex": "112233445566",
    }

    create_session_dir(
        tmp_path,
        identity=other_identity,
        transport=TRANSPORT,
        startup_sensors=IDENTITY["startup_sensors"],
        prefix="session",
    )

    found = find_latest_matching_session(
        tmp_path,
        identity=IDENTITY,
        transport=TRANSPORT,
        prefix="session",
    )

    assert found is None


def test_find_latest_matching_session_ignores_other_startup_sensors(tmp_path: Path):
    other_identity = {
        **IDENTITY,
        "startup_sensors": [
            {"runtime_id": 1, "type_id": 10},
            {"runtime_id": 2, "type_id": 21},
        ],
    }
    create_session_dir(
        tmp_path,
        identity=other_identity,
        transport=TRANSPORT,
        startup_sensors=other_identity["startup_sensors"],
        prefix="session",
    )

    found = find_latest_matching_session(
        tmp_path,
        identity=IDENTITY,
        transport=TRANSPORT,
        prefix="session",
    )

    assert found is None

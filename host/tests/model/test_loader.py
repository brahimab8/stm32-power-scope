from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from host.model.loader import MetadataLoader


def _write(p: Path, name: str, text: str) -> None:
    (p / name).write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def test_load_all_happy_path_populates_models_and_hashes(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "transports.yml",
        """
        transports:
          1:
            label: UART
            driver: uart
            key_param: port
            params:
              port: {type: str, required: true}
            supports_streaming: true
        """,
    )

    _write(
        tmp_path,
        "sensors.yml",
        """
        sensors:
          10:
            name: Demo
            channels:
              1:
                name: V
                is_measured: true
                encode: uint16
                display_unit: V
                scale: 1.0
                lsb: 1.0
              2:
                name: I
                is_measured: true
                encode: uint16
                display_unit: A
                scale: 1.0
                lsb: 1.0
        """,
    )

    loader = MetadataLoader(tmp_path)
    loader.load_all()

    assert set(loader.file_hashes.keys()) == {"transports.yml", "sensors.yml"}

    t = loader.get_transport(1)
    assert t is not None
    assert t.type_id == 1
    assert t.driver == "uart"
    assert t.key_param == "port"
    assert t.supports_streaming is True

    s = loader.get_sensor(10)
    assert s is not None
    assert s.type_id == 10
    assert s.name == "Demo"
    assert s.get_channel(1) is not None
    assert s.get_channel(2) is not None
    assert s.expected_payload_size() == 4


def test_load_transports_requires_transports_root(tmp_path: Path) -> None:
    _write(tmp_path, "transports.yml", "nope: 1\n")
    _write(tmp_path, "sensors.yml", "sensors: {}\n")

    loader = MetadataLoader(tmp_path)
    with pytest.raises(ValueError):
        loader.load_all()


def test_load_transports_requires_key_param_defined_in_params(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "transports.yml",
        """
        transports:
          1:
            label: UART
            driver: uart
            key_param: port
            params:
              baud: {type: int, required: false}
        """,
    )
    _write(tmp_path, "sensors.yml", "sensors: {}\n")

    loader = MetadataLoader(tmp_path)
    with pytest.raises(ValueError):
        loader.load_all()


def test_load_sensors_requires_sensors_root(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "transports.yml",
        """
        transports:
          1:
            label: UART
            driver: uart
            key_param: port
            params:
              port: {type: str, required: true}
        """,
    )
    _write(tmp_path, "sensors.yml", "nope: 1\n")

    loader = MetadataLoader(tmp_path)
    with pytest.raises(ValueError):
        loader.load_all()


def test_load_sensors_measured_channel_requires_encode(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "transports.yml",
        """
        transports:
          1:
            label: UART
            driver: uart
            key_param: port
            params:
              port: {type: str, required: true}
        """,
    )
    _write(
        tmp_path,
        "sensors.yml",
        """
        sensors:
          1:
            name: Bad
            channels:
              1:
                name: V
                is_measured: true
                display_unit: V
        """,
    )

    loader = MetadataLoader(tmp_path)
    with pytest.raises(ValueError):
        loader.load_all()

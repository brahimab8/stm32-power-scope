# host/model/loader.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from host.utils.hashing import sha256_file
from .channel import Channel
from .sensor import Sensor
from .transport import TransportType


class MetadataLoader:
    """
    Loads all static metadata from YAML into strongly-typed model classes.

    Loads:
        - transports.yml
        - sensors.yml

    After calling load_all(), exposes:
        self.transports : dict[int, TransportType]
        self.sensors    : dict[int, Sensor]

    Also exposes:
        self.file_hashes : dict[str, str]  (filename -> sha256)
    """

    def __init__(self, config_dir: str | Path):
        self.config_dir = Path(config_dir)
        self.transports: Dict[int, TransportType] = {}
        self.sensors: Dict[int, Sensor] = {}
        self.file_hashes: Dict[str, str] = {}

    # ---------------------------------------------------------------------
    # YAML utility
    # ---------------------------------------------------------------------
    def _load_yaml(self, filename: str) -> dict:
        full_path = self.config_dir / filename
        if not full_path.exists():
            raise FileNotFoundError(f"Missing metadata file: {full_path}")

        with open(full_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # ---------------------------------------------------------------------
    # Public entry point
    # ---------------------------------------------------------------------
    def load_all(self) -> None:
        """Load all metadata categories + compute file hashes."""
        self.transports.clear()
        self.sensors.clear()
        self.file_hashes.clear()

        # Fingerprints for reproducible recordings
        self.file_hashes["transports.yml"] = sha256_file(self.config_dir / "transports.yml")
        self.file_hashes["sensors.yml"] = sha256_file(self.config_dir / "sensors.yml")

        self._load_transports()
        self._load_sensors()

    # ---------------------------------------------------------------------
    # Transports
    # ---------------------------------------------------------------------
    def _load_transports(self) -> None:
        data = self._load_yaml("transports.yml")

        transports = data.get("transports")
        if not isinstance(transports, dict):
            raise ValueError("transports.yml is missing 'transports' root node")

        for tid_raw, tinfo in transports.items():
            tid = int(tid_raw)
            if not isinstance(tinfo, dict):
                raise ValueError(f"Transport {tid} entry must be a mapping")

            label = tinfo.get("label")
            if not label:
                raise ValueError(f"Transport {tid} is missing 'label'")

            driver = tinfo.get("driver")
            if not driver:
                raise ValueError(f"Transport {tid} is missing 'driver'")

            key_param = tinfo.get("key_param")
            if not key_param:
                raise ValueError(f"Transport {tid} is missing 'key_param'")

            params = tinfo.get("params") or {}
            if not isinstance(params, dict):
                raise ValueError(f"Transport {tid} 'params' must be a mapping")

            if key_param not in params:
                raise ValueError(
                    f"Transport {tid} key_param '{key_param}' not defined in params"
                )

            transport = TransportType(
                type_id=tid,
                label=str(label),
                driver=str(driver),
                params=params,  # schema validation lives in TransportParamResolver
                key_param=str(key_param),
                supports_streaming=bool(tinfo.get("supports_streaming", False)),
            )
            self.transports[tid] = transport

    # ---------------------------------------------------------------------
    # Sensors
    # ---------------------------------------------------------------------
    def _load_sensors(self) -> None:
        data = self._load_yaml("sensors.yml")

        sensors = data.get("sensors")
        if not isinstance(sensors, dict):
            raise ValueError("sensors.yml is missing 'sensors' root node")

        for sid_raw, sinfo in sensors.items():
            sid = int(sid_raw)
            if not isinstance(sinfo, dict):
                raise ValueError(f"Sensor {sid} entry must be a mapping")

            sensor = Sensor(type_id=sid, name=str(sinfo.get("name", "")))

            channels = sinfo.get("channels") or {}
            if not isinstance(channels, dict):
                raise ValueError(f"Sensor {sid} 'channels' must be a mapping")

            for chid_raw, chinfo in channels.items():
                chid = int(chid_raw)
                if not isinstance(chinfo, dict):
                    raise ValueError(f"Sensor {sid} channel {chid} entry must be a mapping")

                channel = Channel(
                    channel_id=chid,
                    name=str(chinfo.get("name", "")),
                    is_measured=bool(chinfo.get("is_measured", True)),
                    encode=chinfo.get("encode"),
                    display_unit=str(chinfo.get("display_unit", "")),
                    scale=float(chinfo.get("scale", 1.0)),
                    lsb=float(chinfo.get("lsb", 1.0)),
                    compute=chinfo.get("compute"),
                )

                if channel.is_measured and not channel.encode:
                    raise ValueError(f"Measured channel {channel.name} missing 'encode'")

                sensor.add_channel(channel)

            self.sensors[sid] = sensor

    # ---------------------------------------------------------------------
    # Accessors
    # ---------------------------------------------------------------------
    def get_transport(self, tid: int) -> Optional[TransportType]:
        return self.transports.get(tid)

    def get_transport_key_param(self, tid: int) -> str:
        t = self.transports.get(tid)
        if not t:
            raise ValueError(f"Transport {tid} not found")
        return t.key_param

    def get_sensor(self, sid: int) -> Optional[Sensor]:
        return self.sensors.get(sid)

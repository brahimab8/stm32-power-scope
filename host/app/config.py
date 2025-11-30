# host/app/config.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PowerScopeConfig:
    metadata_dir: str
    protocol_dir: str
    transport_type_id: int
    transport_overrides: dict
    cmd_timeout_s: float = 1.0

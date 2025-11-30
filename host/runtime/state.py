# host/runtime/session/state.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class TransportState:
    """
    Runtime state of the transport connection.
    """
    connected: bool
    driver: str
    key_param_value: str
    last_error: Optional[str] = None


@dataclass(frozen=True)
class McuState:
    """
    Runtime state of the MCU availability (responding to commands).
    """
    available: bool
    last_seen_s: Optional[float] = None
    uptime_s: Optional[float] = None
    last_error: Optional[str] = None


@dataclass(frozen=True)
class SensorState:
    """
    Runtime state for a discovered sensor instance on the MCU.
    """
    runtime_id: int
    type_id: int
    name: str
    streaming: bool = False
    period_ms: Optional[int] = None
    last_error: Optional[str] = None


@dataclass(frozen=True)
class SessionStatus:
    """
    A snapshot of the full session status, safe to share across threads.
    """
    transport: TransportState
    mcu: McuState
    sensors: List[SensorState]

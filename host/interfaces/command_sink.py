# host/interfaces/command_sink.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol


@dataclass(frozen=True, slots=True)
class CommandEvent:
    """
    Runtime command telemetry event (for tracing/recording/debugging).
    Keep this small + stable; put details into payload/meta.
    """
    name: str                   # e.g. "SET_PERIOD"
    kind: str                   # "send" | "ok" | "timeout" | "error" | "recv"
    payload: Optional[Mapping[str, Any]] = None
    request_id: Optional[str] = None
    ts_utc: Optional[str] = None


class CommandSink(Protocol):
    def on_command(self, event: CommandEvent) -> None: ...
    def close(self) -> None: ...

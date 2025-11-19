from __future__ import annotations

import struct
import threading
import time
from typing import ClassVar, Optional

from .base import Frame
from ..defs import Protocol
from host.protocol.core.types import YAML_TO_STRUCT


class CommandFrame(Frame):
    """Host → device command frame."""

    _seq_counter: ClassVar[int] = 1
    _seq_lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def next_seq(cls) -> int:
        with cls._seq_lock:
            s = cls._seq_counter
            cls._seq_counter = (s + 1) & 0xFFFFFFFF
            if cls._seq_counter == 0:
                cls._seq_counter = 1
            return s

    @staticmethod
    def build_payload(proto: Protocol, cmd_name: str, args: Optional[dict] = None) -> bytes:
        cmd_def = proto.get_command_def(cmd_name)
        args = args or {}

        payload_bytes: list[bytes] = []

        for field in cmd_def.get("payload", []):
            ftype = field["type"]
            if ftype not in YAML_TO_STRUCT:
                raise ValueError(f"Unknown field type '{ftype}' in command '{cmd_name}'")

            fmt = "<" + YAML_TO_STRUCT[ftype]

            val = field.get("value", args.get(field["name"]))
            if val is None:
                raise KeyError(f"Missing command argument '{field['name']}' for {cmd_name}")

            payload_bytes.append(struct.pack(fmt, val))

        full_payload = b"".join(payload_bytes)

        # Validate command payload length against CMD frame constraints
        frame_def = proto.frames["CMD"]
        min_len = proto.resolve_value(frame_def.get("min_payload", 0), 0)
        max_len = proto.resolve_value(
            frame_def.get("max_payload", proto.constants.get("max_payload", 1024)),
            proto.constants.get("max_payload", 1024),
        )
        if not (int(min_len) <= len(full_payload) <= int(max_len)):
            raise ValueError(
                f"Command payload length {len(full_payload)} outside [{min_len}, {max_len}]"
            )

        return full_payload

    def __init__(self, proto: Protocol, cmd_name: str, args: Optional[dict] = None, rsv: int = 0):
        payload = self.build_payload(proto, cmd_name, args)
        cmd_def = proto.get_command_def(cmd_name)
        cmd_id = proto.resolve_value(cmd_def.get("cmd_id"), proto.constants.get("cmd_none", 0))

        super().__init__(
            proto=proto,
            frame_type=proto.frames["CMD"]["code"],
            seq=self.next_seq(),
            payload=payload,
            cmd_id=int(cmd_id),
            ts_ms=int(time.time() * 1000),
            rsv=rsv,
        )
        self.cmd_name = cmd_name

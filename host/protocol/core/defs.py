from __future__ import annotations

import struct
from typing import Any, Dict

from .types import YAML_TO_STRUCT
from .header import parse_header, build_header
from .crc import crc16
from .decoder import decode_response, resolve_value
from .utils import command_requires_streaming
from ..loader import ProtocolLoader


class Protocol:
    """Runtime access to protocol metadata."""

    def __init__(self, loader: ProtocolLoader):
        self.constants: Dict[str, Any] = loader.constants
        self.frames: Dict[str, Dict[str, Any]] = loader.frames
        self.header_def: list[Dict[str, Any]] = loader.header
        self.commands: Dict[str, Dict[str, Any]] = loader.commands
        self.errors: Dict[str, Any] = loader.errors

        # Build header struct
        try:
            self.header_fields = [f["name"] for f in self.header_def]
            self.header_fmt = "<" + "".join(YAML_TO_STRUCT[f["type"]] for f in self.header_def)
        except KeyError as e:
            raise ValueError(f"Unknown header field type in header.yml: {e}") from e
        except Exception as e:
            raise ValueError(f"Invalid header definition in header.yml: {e}") from e

        self.header_struct = struct.Struct(self.header_fmt)

        # Fast lookup maps
        self.frame_types: Dict[str, int] = {name: f["code"] for name, f in self.frames.items()}
        self.frames_by_code: Dict[int, Dict[str, Any]] = {f["code"]: f for f in self.frames.values()}
        self.error_codes: Dict[int, str] = {int(v): str(k) for k, v in self.errors.items()}

        self.commands_by_id: Dict[int, Dict[str, Any]] = {}
        for name, cmd in self.commands.items():
            cid = self.resolve_value(cmd.get("cmd_id"), None)
            if cid is None:
                continue
            cid = int(cid)
            if cid in self.commands_by_id:
                raise ValueError(f"Duplicate cmd_id={cid} for commands '{name}' and '{self.commands_by_id[cid].get('name', '<unknown>')}'")
            self.commands_by_id[cid] = cmd

    # Payload length validation (used for response frames)
    def validate_payload_len(self, frame_type: int, payload_len: int) -> bool:
        frame_def = self.frames_by_code.get(frame_type)
        if not frame_def:
            return False

        min_len = self.resolve_value(frame_def.get("min_payload", 0), 0)
        max_len = self.resolve_value(
            frame_def.get("max_payload", self.constants.get("max_payload")),
            self.constants.get("max_payload"),
        )
        return int(min_len) <= int(payload_len) <= int(max_len)

    # Delegated
    def resolve_value(self, v: Any, default: Any = None) -> Any:
        return resolve_value(self, v, default)

    def get_command_def(self, cmd_name: str) -> Dict[str, Any]:
        if cmd_name not in self.commands:
            raise ValueError(f"Unknown command: {cmd_name}")
        return self.commands[cmd_name]

    def parse_header(self, raw: bytes) -> Dict[str, Any]:
        return parse_header(self, raw)

    def build_header(self, fields: Dict[str, Any]) -> bytes:
        return build_header(self, fields)

    def crc16(self, buf: bytes) -> int:
        return crc16(self, buf)

    def decode_response(self, cmd_id: int, payload: bytes) -> Dict[str, Any]:
        return decode_response(self, cmd_id, payload)

    def command_requires_streaming(self, cmd_name: str) -> bool:
        return command_requires_streaming(self, cmd_name)

from __future__ import annotations

import time
import struct
from dataclasses import dataclass
from typing import Optional

from ..defs import Protocol


@dataclass
class Frame:
    proto: Protocol
    frame_type: int
    seq: int
    payload: bytes = b""
    ts_ms: Optional[int] = None
    cmd_id: Optional[int] = None
    rsv: int = 0

    def __post_init__(self) -> None:
        # Timestamp default (wall clock ms)
        if self.ts_ms is None:
            self.ts_ms = int(time.time() * 1000) & 0xFFFFFFFF
        else:
            self.ts_ms = int(self.ts_ms) & 0xFFFFFFFF

        # seq validation
        self.seq = int(self.seq) & 0xFFFFFFFF
        if self.seq < 0:
            raise ValueError(f"Invalid seq={self.seq}; must be >= 0")

        # cmd_id default
        if self.cmd_id is None:
            self.cmd_id = int(self.proto.constants.get("cmd_none", 0))
        else:
            self.cmd_id = int(self.cmd_id)

        self.rsv = int(self.rsv) if self.rsv is not None else 0

        self._validate_payload_length()

    def _validate_payload_length(self) -> None:
        frame_def = getattr(self.proto, "frames_by_code", {}).get(self.frame_type)
        if not frame_def:
            raise ValueError(f"Unknown frame_type={self.frame_type}")

        min_len = self.proto.resolve_value(frame_def.get("min_payload", 0), 0)
        max_len = self.proto.resolve_value(
            frame_def.get("max_payload", self.proto.constants.get("max_payload", 1024)),
            self.proto.constants.get("max_payload", 1024),
        )

        plen = len(self.payload)
        if plen < int(min_len):
            raise ValueError(f"Payload too short: {plen} < min_payload {min_len}")
        if plen > int(max_len):
            raise ValueError(f"Payload too long: {plen} > max_payload {max_len}")

    def encode(self) -> bytes:
        hdr_dict = {
            "magic": self.proto.constants.get("magic", 0xABCD),
            "type": self.frame_type,
            "ver": 0,
            "len": len(self.payload),
            "cmd_id": self.cmd_id,
            "rsv": self.rsv,
            "seq": self.seq,
            "ts_ms": self.ts_ms,
        }
        header_bytes = self.proto.build_header(hdr_dict)
        crc = self.proto.crc16(header_bytes + self.payload)
        return header_bytes + self.payload + struct.pack("<H", crc)

    @property
    def type_name(self) -> str:
        for k, v in self.proto.frames.items():
            if v["code"] == self.frame_type:
                return k
        return f"TYPE_{self.frame_type}"

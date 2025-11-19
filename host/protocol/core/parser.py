from __future__ import annotations

import logging
from typing import Optional

from .frames import ResponseFrame, StreamFrame, Frame
from .defs import Protocol


class FrameParser:
    def __init__(self, proto: Protocol, logger: Optional[logging.Logger] = None):
        self.proto = proto
        self.buffer = bytearray()
        self._log = logger or logging.getLogger(__name__)

    # ---------------- Public API ----------------
    def feed(self, data: bytes) -> None:
        """Feed raw bytes into the parser buffer."""
        self.buffer.extend(data)
        self._log.debug(
            "Parser fed %d bytes, buffer_len=%d",
            len(data),
            len(self.buffer),
        )

    def get_frame(self) -> Optional[Frame]:
        """Parse and return the next complete frame, if available."""
        while True:
            hdr_size = self.proto.header_struct.size
            if len(self.buffer) < hdr_size:
                return None  # Not enough bytes for header

            magic_idx = self._sync_magic()
            if magic_idx < 0 or len(self.buffer) < hdr_size:
                return None  # Wait for more bytes

            hdr_bytes = self.buffer[:hdr_size]
            try:
                hdr = self.proto.parse_header(hdr_bytes)
            except Exception:
                self._log.debug("Header parse failed, skipping first 2 bytes")
                del self.buffer[:2]
                continue

            payload_len = hdr.get("len", 0)
            max_payload = self.proto.constants.get("max_payload", 1024)
            if payload_len > max_payload:
                self._log.warning(
                    "Payload length too large: %d (max=%d), skipping magic",
                    payload_len,
                    max_payload,
                )
                del self.buffer[:2]
                continue

            crc_len = 2  # 16-bit CRC
            total_len = hdr_size + payload_len + crc_len
            if len(self.buffer) < total_len:
                return None  # Wait for more bytes

            frame_bytes = self.buffer[:total_len]
            payload = frame_bytes[hdr_size: hdr_size + payload_len]
            rx_crc = int.from_bytes(frame_bytes[-crc_len:], "little")
            calc_crc = self.proto.crc16(frame_bytes[:-crc_len])

            if calc_crc != rx_crc:
                self._log.warning(
                    "CRC mismatch: calc=%04X rx=%04X, skipping magic",
                    calc_crc,
                    rx_crc,
                )
                del self.buffer[:2]
                continue

            # Extract Frame-type
            ftype = hdr["type"]

            # Enforce frame-level payload constraints
            if not self.proto.validate_payload_len(ftype, payload_len):
                self._log.warning(
                    "Invalid payload length %d for frame type %s, dropping frame",
                    payload_len,
                    ftype,
                )
                del self.buffer[:total_len]
                continue

            # Remove processed bytes
            del self.buffer[:total_len]

            # Extract header fields
            cmd_id = hdr.get("cmd_id", self.proto.constants.get("cmd_none", 0))
            rsv = hdr.get("rsv", 0)

            # Instantiate proper frame
            if ftype == self.proto.frames["STREAM"]["code"]:
                frame = StreamFrame(
                    proto=self.proto,
                    seq=hdr["seq"],
                    payload=payload,
                    ts_ms=hdr["ts_ms"],
                    rsv=rsv,
                )
            else:
                frame = ResponseFrame.from_bytes(self.proto, hdr_bytes, payload)
                frame.cmd_id = cmd_id
                frame.rsv = rsv

            # Store raw header for diagnostics
            frame._raw_header = bytes(hdr_bytes)
            frame._hdr = hdr

            self._log.debug(
                "Parsed frame type=%s seq=%s cmd_id=%s payload_len=%d total_len=%d",
                ftype,
                hdr.get("seq"),
                cmd_id,
                payload_len,
                total_len,
            )

            return frame

    # ---------------- Helpers ----------------
    def _sync_magic(self) -> int:
        """Locate the first magic word in the buffer and discard preceding bytes."""
        magic_val = self.proto.constants.get("magic", 0xABCD)
        magic_bytes = magic_val.to_bytes(2, "little")
        idx = self.buffer.find(magic_bytes)
        if idx > 0:
            del self.buffer[:idx]
        return idx

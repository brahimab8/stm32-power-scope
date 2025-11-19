from __future__ import annotations

from typing import Any, ClassVar, Dict, Optional

from .base import Frame
from ..defs import Protocol


# ---------------------------
# Response Frames
# ---------------------------
class ResponseFrame(Frame):
    """
    Base class for non-stream frames (ACK/NACK/other responses).
    """

    @classmethod
    def from_bytes(cls, proto: Protocol, raw_header: bytes, payload: bytes) -> "ResponseFrame":
        hdr = proto.parse_header(raw_header)
        ftype = hdr["type"]
        rsv = hdr.get("rsv", 0)

        if ftype == proto.frames["ACK"]["code"]:
            return AckFrame(
                proto=proto,
                seq=hdr["seq"],
                payload=payload,
                ts_ms=hdr["ts_ms"],
                cmd_id=hdr.get("cmd_id"),
                rsv=rsv,
            )

        if ftype == proto.frames["NACK"]["code"]:
            return NackFrame(
                proto=proto,
                seq=hdr["seq"],
                payload=payload,
                ts_ms=hdr["ts_ms"],
                cmd_id=hdr.get("cmd_id"),
                rsv=rsv,
            )

        # Generic fallback
        return cls(
            proto=proto,
            frame_type=ftype,
            seq=hdr["seq"],
            payload=payload,
            ts_ms=hdr["ts_ms"],
            cmd_id=hdr.get("cmd_id"),
            rsv=rsv,
        )


class AckFrame(ResponseFrame):
    TYPE_ACK: ClassVar[int]

    def __init__(
        self,
        *,
        proto: Protocol,
        seq: int,
        payload: bytes,
        ts_ms: int,
        cmd_id: Optional[int] = None,
        rsv: int = 0,
    ):
        super().__init__(
            proto=proto,
            frame_type=proto.frames["ACK"]["code"],
            seq=seq,
            payload=payload,
            ts_ms=ts_ms,
            cmd_id=cmd_id,
            rsv=rsv,
        )

    @property
    def data(self) -> bytes:
        return self.payload

    @property
    def decoded(self) -> Dict[str, Any]:
        # cmd_id is always set by Frame.__post_init__ defaulting to cmd_none
        return self.proto.decode_response(int(self.cmd_id), self.payload)  # type: ignore[arg-type]


class NackFrame(ResponseFrame):
    TYPE_NACK: ClassVar[int]  # optional, not required

    def __init__(
        self,
        *,
        proto: Protocol,
        seq: int,
        payload: bytes,
        ts_ms: int,
        cmd_id: Optional[int] = None,
        rsv: int = 0,
    ):
        super().__init__(
            proto=proto,
            frame_type=proto.frames["NACK"]["code"],
            seq=seq,
            payload=payload,
            ts_ms=ts_ms,
            cmd_id=cmd_id,
            rsv=rsv,
        )

    @property
    def error_code(self) -> int:
        if not self.payload:
            return int(self.proto.errors.get("UNKNOWN", 255))  # fallback
        return self.payload[0]

    @property
    def error(self) -> Dict[str, Any]:
        code = int(self.error_code)
        name = self.proto.error_codes.get(code, "UNKNOWN")
        return {"code": code, "name": name}


class StreamFrame(Frame):
    """
    Represents a streaming frame from device.

    Raw STREAM payload format:
        [sensor_runtime_id (1 byte)] + [raw measured bytes...]
    """

    def __init__(
        self,
        *,
        proto: Protocol,
        seq: int,
        payload: bytes,
        ts_ms: int,
        rsv: int = 0,
    ):
        if not payload:
            raise ValueError("Stream payload missing sensor runtime ID byte")

        self.sensor_runtime_id: int = payload[0]
        sensor_payload = payload[1:]

        super().__init__(
            proto=proto,
            frame_type=proto.frames["STREAM"]["code"],
            seq=seq,
            payload=sensor_payload,
            ts_ms=ts_ms,
            cmd_id=proto.constants.get("cmd_none", 0),
            rsv=rsv,
        )

    def get_raw_payload(self) -> bytes:
        """Return the raw sensor payload excluding the runtime ID byte."""
        return self.payload

# host/model/codec.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import struct


@dataclass(frozen=True)
class PrimitiveCodec:
    fmt_le: str  # little-endian struct format
    fmt_be: str  # big-endian struct format
    size: int


PRIMITIVES: Dict[str, PrimitiveCodec] = {
    "uint8":  PrimitiveCodec(fmt_le="B",  fmt_be="B",  size=1),
    "int8":   PrimitiveCodec(fmt_le="b",  fmt_be="b",  size=1),
    "uint16": PrimitiveCodec(fmt_le="<H", fmt_be=">H", size=2),
    "int16":  PrimitiveCodec(fmt_le="<h", fmt_be=">h", size=2),
    "uint32": PrimitiveCodec(fmt_le="<I", fmt_be=">I", size=4),
    "int32":  PrimitiveCodec(fmt_le="<i", fmt_be=">i", size=4),
    "float":  PrimitiveCodec(fmt_le="<f", fmt_be=">f", size=4),
    "double": PrimitiveCodec(fmt_le="<d", fmt_be=">d", size=8),
}


def decode_primitive(encode: str, raw_bytes: bytes, *, endian: str = "little") -> float:
    enc = encode.lower()
    if enc not in PRIMITIVES:
        raise NotImplementedError(f"Unknown encode type '{encode}'")

    codec = PRIMITIVES[enc]
    if len(raw_bytes) != codec.size:
        raise ValueError(f"Raw bytes length {len(raw_bytes)} != expected {codec.size} for '{encode}'")

    fmt = codec.fmt_le if endian == "little" else codec.fmt_be
    return struct.unpack(fmt, raw_bytes)[0]


def primitive_size(encode: str) -> int:
    enc = encode.lower()
    if enc not in PRIMITIVES:
        raise NotImplementedError(f"Unknown encode type '{encode}'")
    return PRIMITIVES[enc].size

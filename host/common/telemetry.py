# telemetry.py
from dataclasses import dataclass
from struct import unpack_from
from typing import Dict

CHAN_I = "I"  # µA
CHAN_V = "V"  # mV
CHAN_P = "P"  # mW

@dataclass(frozen=True)
class Sample:
    seq: int
    ts_ms: int
    values: Dict[str, int]

def decode_payload_v0(payload: bytes) -> Dict[str, int]:
    """
    v0 payload layout (little-endian, EXACTLY 6 bytes):
      [0..1]  u16 bus_mV
      [2..5]  i32 current_uA
    """
    if len(payload) != 6:
        raise ValueError(f"v0 payload must be 6 bytes, got {len(payload)}")
    (bus_mV,) = unpack_from("<H", payload, 0)
    (cur_uA,) = unpack_from("<i", payload, 2)
    return {CHAN_V: int(bus_mV), CHAN_I: int(cur_uA)}

def add_derived(values: Dict[str, int]) -> Dict[str, int]:
    i_uA = int(values.get(CHAN_I, 0))   # µA (can be negative)
    v_mV = int(values.get(CHAN_V, 0))   # mV (unsigned)

    prod = i_uA * v_mV  # µA*mV (signed)

    # mW = (µA * mV) / 1_000_000, truncated toward zero
    if prod >= 0:
        p_mW = prod // 1_000_000
    else:
        p_mW = - ((-prod) // 1_000_000)

    # Always-positive power by convention
    p_mW = abs(p_mW)

    out = dict(values)
    out[CHAN_P] = int(p_mW)
    return out

def decode_data_frame(hdr: dict, payload: bytes) -> Sample:
    ver = int(hdr.get("ver", 0))
    if ver != 0:
        raise ValueError(f"unsupported protocol version: {ver}")
    base = decode_payload_v0(payload)
    vals = add_derived(base)
    return Sample(seq=int(hdr["seq"]), ts_ms=int(hdr["ts_ms"]), values=vals)

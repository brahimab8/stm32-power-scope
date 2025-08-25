# telemetry.py
from dataclasses import dataclass
from struct import unpack_from
from typing import Dict

CHAN_I = "I"  # mA
CHAN_V = "V"  # mV
CHAN_P = "P"  # mW

@dataclass(frozen=True)
class Sample:
    seq: int
    ts_ms: int
    values: Dict[str, int]

def decode_payload_v0(payload: bytes) -> Dict[str, int]:
    # v0: uint16 I_mA, uint16 V_mV (LE)
    i_ma = v_mv = 0
    if len(payload) >= 2:
        (i_ma,) = unpack_from("<H", payload, 0)
    if len(payload) >= 4:
        (v_mv,) = unpack_from("<H", payload, 2)
    return {CHAN_I: int(i_ma), CHAN_V: int(v_mv)}

def add_derived(values: Dict[str, int]) -> Dict[str, int]:
    i = int(values.get(CHAN_I, 0))
    v = int(values.get(CHAN_V, 0))
    out = dict(values)
    out[CHAN_P] = (i * v) // 1000  # mA*mV -> mW
    return out

def decode_data_frame(hdr: dict, payload: bytes) -> Sample:
    ver = int(hdr.get("ver", 0))
    if ver != 0:
        raise ValueError(f"unsupported payload version: {ver}")
    base = decode_payload_v0(payload)
    vals = add_derived(base)
    return Sample(seq=int(hdr["seq"]), ts_ms=int(hdr["ts_ms"]), values=vals)

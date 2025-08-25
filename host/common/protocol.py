# protocol.py
import struct
import time
from .serial_link import read_exact, resync

MAGIC = 0x5AA5
PROTO_VER = 0
HDR = struct.Struct("<HBBHHII")  # magic,u16 | type,u8 | ver,u8 | len,u16 | rsv,u16 | seq,u32 | ts_ms,u32

PROTO_TYPE_STREAM = 0
PROTO_TYPE_CMD    = 1
PROTO_TYPE_ACK    = 2
PROTO_TYPE_NACK   = 3

CRC_LEN = 2
PROTO_MAX_PAYLOAD = 46

CMD_START = 0x01
CMD_STOP  = 0x02

def _crc16_ccitt_false(buf: bytes, seed: int = 0xFFFF) -> int:
    crc = seed
    for b in buf:
        crc ^= (b & 0xFF) << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else ((crc << 1) & 0xFFFF)
    return crc

def write_frame(ser, typ: int, payload: bytes, seq: int, ts_ms: int = 0) -> None:
    if payload is None:
        payload = b""
    if len(payload) > PROTO_MAX_PAYLOAD:
        raise ValueError("payload too large")
    hdr = HDR.pack(MAGIC, typ, PROTO_VER, len(payload), 0, seq, ts_ms)
    span = hdr + payload
    crc = _crc16_ccitt_false(span)
    ser.write(span + struct.pack("<H", crc))
    ser.flush()

def read_frame(ser):
    raw = resync(ser, MAGIC, HDR.size)
    if not raw:
        return (None, None)
    magic, typ, ver, length, rsv, seq, ts_ms = HDR.unpack(raw)
    if magic != MAGIC or ver != PROTO_VER or length > PROTO_MAX_PAYLOAD:
        return (None, None)
    rest = read_exact(ser, length + CRC_LEN)
    if rest is None:
        return (None, None)
    payload = rest[:length]
    got_crc = struct.unpack_from("<H", rest, length)[0]
    if got_crc != _crc16_ccitt_false(raw + payload):
        return (None, None)
    return ({"magic": magic, "type": typ, "ver": ver, "len": length,
             "rsv": rsv, "seq": seq, "ts_ms": ts_ms}, payload)

_seq = 1
def _next_seq():
    global _seq
    s = _seq
    _seq = (s + 1) & 0xFFFFFFFF or 1
    return s

def send_cmd(ser, opcode: int, *, wait_reply: bool = True, timeout_s: float = 1.0):
    req_id = _next_seq()
    write_frame(ser, PROTO_TYPE_CMD, bytes([opcode]), seq=req_id, ts_ms=0)
    if not wait_reply:
        return ("SENT", req_id)
    end = time.time() + timeout_s
    while time.time() < end:
        hdr, payload = read_frame(ser)
        if hdr is None:
            continue
        if hdr["type"] in (PROTO_TYPE_ACK, PROTO_TYPE_NACK) and hdr["seq"] == req_id:
            return ("ACK" if hdr["type"] == PROTO_TYPE_ACK else "NACK", req_id)
        # non-reply frames are consumed here
    return ("TIMEOUT", req_id)

def send_start(ser, *, wait_reply: bool = True, timeout_s: float = 1.0):
    return send_cmd(ser, CMD_START, wait_reply=wait_reply, timeout_s=timeout_s)

def send_stop(ser, *, wait_reply: bool = True, timeout_s: float = 1.0):
    return send_cmd(ser, CMD_STOP, wait_reply=wait_reply, timeout_s=timeout_s)

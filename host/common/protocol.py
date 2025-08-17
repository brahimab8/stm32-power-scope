# protocol.py
import struct

from .serial_link import read_exact, resync

# Protocol constants
MAGIC = 0x5AA5
HDR = struct.Struct("<HBBHHII")  # little-endian: magic, type, ver, len, rsv, seq, ts_ms
PROTO_TYPE_STREAM = 0
PROTO_VER = 0
PROTO_MAX_PAYLOAD = 512

# 1-byte commands
CMD_START = 0x01
CMD_STOP  = 0x02

def send_start(ser):
    ser.write(bytes([CMD_START])); ser.flush()

def send_stop(ser):
    ser.write(bytes([CMD_STOP])); ser.flush()

def read_frame(ser):
    """
    Returns (hdr_dict, payload_bytes) or (None, None) on timeout/bad frame.
    hdr_dict keys: magic, type, ver, len, rsv, seq, ts_ms
    """
    raw = resync(ser, MAGIC, HDR.size)
    if not raw:
        return (None, None)

    magic, typ, ver, length, rsv, seq, ts_ms = HDR.unpack(raw)
    if magic != MAGIC or typ != PROTO_TYPE_STREAM or ver != PROTO_VER:
        return (None, None)
    if length > PROTO_MAX_PAYLOAD:
        return (None, None)

    payload = read_exact(ser, length)
    if payload is None:
        return (None, None)

    hdr = dict(magic=magic, type=typ, ver=ver, len=length,
               rsv=rsv, seq=seq, ts_ms=ts_ms)
    return (hdr, payload)

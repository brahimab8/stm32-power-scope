# host/common/control.py

PROTO_TYPE_ACK  = 2
PROTO_TYPE_NACK = 3

def parse_control_frame(hdr: dict, payload: bytes):
    t = int(hdr.get("type", -1))
    seq = int(hdr.get("seq", 0))
    return {"type": t, "seq": seq, "len": len(payload)}

def format_control_event(ev: dict) -> str:
    t = ev.get("type")
    if t == PROTO_TYPE_ACK:
        return f"ACK seq={ev.get('seq')}"
    if t == PROTO_TYPE_NACK:
        return f"NACK seq={ev.get('seq')}"
    return f"OTHER type={t} len={ev.get('len')} seq={ev.get('seq')}"

from typing import Dict, Any

def parse_header(proto, raw: bytes) -> Dict[str, Any]:
    if len(raw) != proto.header_struct.size:
        raise ValueError(f"Header size mismatch: {len(raw)} != {proto.header_struct.size}")
    return dict(zip(proto.header_fields, proto.header_struct.unpack(raw)))

def build_header(proto, fields: Dict[str, Any]) -> bytes:
    values = [fields[name] for name in proto.header_fields]
    return proto.header_struct.pack(*values)

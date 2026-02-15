from __future__ import annotations

from struct import calcsize, unpack
from typing import Any, Dict, List

from host.protocol.core.types import YAML_TO_STRUCT


def resolve_value(proto, v: Any, default: Any = None) -> Any:
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.startswith("constants:"):
        const_name = v.split(":", 1)[1]
        return proto.constants.get(const_name, default)
    return default


# -------------------------- Field-based decoding --------------------------
def decode_fields(proto, payload: bytes, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    pos = 0
    endian = "<"

    for field in fields:
        ftype = field["type"]

        if ftype in YAML_TO_STRUCT:
            fmt = endian + YAML_TO_STRUCT[ftype]
            size = calcsize(fmt)
            if pos + size > len(payload):
                raise ValueError(f"Payload too short for field {field['name']}")
            result[field["name"]] = unpack(fmt, payload[pos: pos + size])[0]
            pos += size
            continue

        if ftype == "array":
            items_def = field.get("items", {})
            if items_def.get("type") == "struct":
                struct_fields = items_def.get("fields", [])
                # precompute struct entry size
                struct_size = 0
                for f in struct_fields:
                    t = f["type"]
                    if t not in YAML_TO_STRUCT:
                        raise ValueError(f"Unknown struct field type '{t}' in array '{field['name']}'")
                    struct_size += calcsize(endian + YAML_TO_STRUCT[t])

                items = []
                while pos + struct_size <= len(payload):
                    entry_bytes = payload[pos: pos + struct_size]
                    entry: Dict[str, Any] = {}
                    offset = 0
                    for f in struct_fields:
                        fmt = endian + YAML_TO_STRUCT[f["type"]]
                        size = calcsize(fmt)
                        entry[f["name"]] = unpack(fmt, entry_bytes[offset: offset + size])[0]
                        offset += size
                    items.append(entry)
                    pos += struct_size

                result[field["name"]] = items
            else:
                # fallback for unknown array types: just keep remaining bytes
                result[field["name"]] = payload[pos:]
                pos = len(payload)
            continue

        if ftype == "bytes":
            result[field["name"]] = payload[pos:]
            pos = len(payload)
            continue

        # unknown type -> return remaining bytes
        result[field["name"]] = payload[pos:]
        pos = len(payload)

    return result


# -------------------------- Payload-Type-based decoding --------------------------
def decode_payload_type(proto, payload: bytes, payload_type_name: str) -> Dict[str, Any]:
    payload_def = proto.payload_types.get(payload_type_name)
    if not payload_def:
        return {"raw": payload}

    fields = payload_def.get("fields", [])
    return decode_fields(proto, payload, fields)


# -------------------------- Sensor-packet specific decoder --------------------------
def decode_sensor_packet(proto, payload: bytes) -> Dict[str, Any]:
    """
    Decode a STREAM payload as a sensor_packet.
    Returns dict with 'sensor_runtime_id' and 'raw_readings'.
    """
    return decode_payload_type(proto, payload, "sensor_packet")


# -------------------------- Main command/response decoder --------------------------
def decode_response(proto, cmd_id: int, payload: bytes) -> Dict[str, Any]:
    cmd_def = getattr(proto, "commands_by_id", {}).get(int(cmd_id))
    if not cmd_def:
        return {"raw": payload}

    resp = cmd_def.get("response_payload")
    payload_type_name = resp.get("payload_type") if isinstance(resp, dict) else None

    if payload_type_name:
        return decode_payload_type(proto, payload, payload_type_name)
    else:
        fields = resp if isinstance(resp, list) else []
        return decode_fields(proto, payload, fields)

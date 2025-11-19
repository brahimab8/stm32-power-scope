from __future__ import annotations

from struct import calcsize, unpack
from typing import Any, Dict, Optional

from host.protocol.core.types import YAML_TO_STRUCT


def resolve_value(proto, v: Any, default: Any = None) -> Any:
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.startswith("constants:"):
        const_name = v.split(":", 1)[1]
        return proto.constants.get(const_name, default)
    return default


def decode_response(proto, cmd_id: int, payload: bytes) -> Dict[str, Any]:
    cmd_def = getattr(proto, "commands_by_id", {}).get(int(cmd_id))
    if not cmd_def:
        return {"raw": payload}

    result: Dict[str, Any] = {}
    pos = 0
    endian = "<"

    for field in cmd_def.get("response_payload", []):
        ftype = field["type"]

        if ftype in YAML_TO_STRUCT:
            fmt = endian + YAML_TO_STRUCT[ftype]
            size = calcsize(fmt)
            if pos + size > len(payload):
                raise ValueError(f"Payload too short for field {field['name']}")
            val_bytes = payload[pos: pos + size]
            result[field["name"]] = unpack(fmt, val_bytes)[0]
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
                    entry = {}
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
                # unknown array format -> return remaining bytes
                result[field["name"]] = payload[pos:]
                pos = len(payload)
            continue

        # unknown type -> return remaining bytes
        result[field["name"]] = payload[pos:]
        pos = len(payload)

    return result

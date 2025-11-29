# host/transport/params.py
from __future__ import annotations

from typing import Any, Dict, Optional, Mapping

from host.model.transport import TransportType
from host.core.errors import TransportConfigError


class TransportParamResolver:
    """
    Resolve concrete transport kwargs from a TransportType param schema + overrides.
    """

    def __init__(self, transports: Mapping[int, TransportType]):
        self._transports = transports

    def resolve(self, type_id: int, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        overrides = overrides or {}
        meta = self._transports.get(int(type_id))
        if not meta:
            raise TransportConfigError(
                f"No transport metadata id={type_id}.",
                hint="Check transport_type_id against your metadata.",
                details={"type_id": int(type_id)},
            ) from None

        return self._resolve_from_meta(meta, overrides)

    def _resolve_from_meta(self, meta: TransportType, overrides: Dict[str, Any]) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}

        # Validate override keys
        for key in overrides:
            if key not in meta.params:
                raise TransportConfigError(
                    f"Unknown transport param '{key}' for transport '{meta.label}'.",
                    hint=f"Valid params: {sorted(meta.params.keys())}",
                    details={"label": meta.label, "driver": meta.driver, "param": key},
                ) from None

        for name, spec in meta.params.items():
            if name in overrides:
                value = overrides[name]
            elif "default" in spec:
                value = spec["default"]
            elif spec.get("required", False):
                raise TransportConfigError(
                    f"Missing required transport param '{name}' for transport '{meta.label}'.",
                    hint="Provide it as a CLI flag / config override.",
                    details={"label": meta.label, "driver": meta.driver, "param": name},
                ) from None
            else:
                continue

            try:
                resolved[name] = self._cast_param(value, spec.get("type"))
            except (TypeError, ValueError) as e:
                raise TransportConfigError(
                    f"Invalid value for transport '{meta.label}' param '{name}'.",
                    hint=str(e),
                    details={
                        "label": meta.label,
                        "driver": meta.driver,
                        "param": name,
                        "value": value,
                        "expected_type": spec.get("type"),
                    },
                ) from None

        return resolved

    @staticmethod
    def _cast_param(value: Any, type_name: Any) -> Any:
        if value is None:
            return None

        if type_name == "str":
            if not isinstance(value, str):
                raise TypeError(f"Expected str, got {type(value).__name__}")
            return value

        if type_name == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"Expected int, got {type(value).__name__}")
            return value

        if type_name == "float":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"Expected float, got {type(value).__name__}")
            return float(value)

        if type_name == "bool":
            if isinstance(value, bool):
                return value
            # accept 0/1 int
            if isinstance(value, int) and value in (0, 1):
                return bool(value)
            raise TypeError(f"Expected bool (or 0/1), got {type(value).__name__}")

        # unknown schema type
        raise TypeError(f"Unknown schema type '{type_name}'")

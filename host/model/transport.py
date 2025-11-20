# host/model/transport.py
from __future__ import annotations

from typing import Any, Dict, Optional


class TransportType:
    """
    Static model of a transport type (catalog entry).

    Contains only metadata — no runtime state.

    Attributes:
        type_id: Unique numeric ID of this transport type.
        label: Human-readable label for display/logging.
        driver: Stable driver key used by the runtime registry (e.g. "uart", "usb").
        params: Parameter schema: param_name -> {type, default, required, ...}
        key_param: Param that uniquely identifies a concrete instance (e.g. "port").
        supports_streaming: True if streaming mode is supported/allowed for this type.
    """

    def __init__(
        self,
        type_id: int,
        label: str,
        driver: str,
        params: Optional[Dict[str, Dict[str, Any]]] = None,
        *,
        key_param: str = "port",
        supports_streaming: bool = False,
    ):
        self.type_id: int = int(type_id)
        self.label: str = str(label)
        self.driver: str = str(driver)
        self.params: Dict[str, Dict[str, Any]] = params or {}
        self.key_param: str = str(key_param)
        self.supports_streaming: bool = bool(supports_streaming)

    def as_dict(self) -> dict:
        return {
            "type_id": self.type_id,
            "label": self.label,
            "driver": self.driver,
            "params": self.params,
            "key_param": self.key_param,
            "supports_streaming": self.supports_streaming,
        }

    def __repr__(self) -> str:
        return (
            f"TransportType(type_id={self.type_id}, label='{self.label}', "
            f"driver='{self.driver}')"
        )

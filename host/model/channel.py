# host/model/channel.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .codec import decode_primitive, primitive_size
from .compute import eval_op


@dataclass(frozen=True)
class ChannelReading:
    channel_id: int
    name: str
    is_measured: bool
    raw: Optional[float]      # raw decoded (measured) or raw-like intermediate (computed)
    value: Optional[float]    # display value
    unit: str


class Channel:
    """
    Static metadata + pure logic.

    - Measured channels:
        - decode bytes -> raw (numeric)
        - raw -> display via lsb*scale
    - Computed channels:
        - compute uses inputs from dependencies
        - supports compute.inputs = "value" | "raw"
        - supports compute.factor (post-op scaling in compute space)
        - final display conversion uses lsb*scale too (recommend keep at 1.0 for computed)
    """

    def __init__(
        self,
        channel_id: int,
        name: str,
        *,
        is_measured: bool = True,
        encode: Optional[str] = None,
        display_unit: str = "",
        scale: float = 1.0,
        lsb: float = 1.0,
        compute: Optional[Dict[str, Any]] = None,
        endian: str = "little",  # for measured channels
    ):
        self.channel_id = int(channel_id)
        self.name = name
        self.is_measured = bool(is_measured)
        self.encode = encode.lower() if encode else None
        self.display_unit = display_unit or ""
        self.scale = float(scale)
        self.lsb = float(lsb)
        self.compute = compute
        self.endian = endian

        self._validate()

    def _validate(self) -> None:
        if self.endian not in {"little", "big"}:
            raise ValueError(f"Invalid endian '{self.endian}' for channel '{self.name}'")

        if self.is_measured:
            if not self.encode:
                raise ValueError(f"Measured channel '{self.name}' must have 'encode'")
            if self.compute is not None:
                raise ValueError(f"Measured channel '{self.name}' must not define 'compute'")
            # validates encode exists
            _ = primitive_size(self.encode)
        else:
            if self.encode is not None:
                raise ValueError(f"Computed channel '{self.name}' must not define 'encode'")
            if not self.compute:
                raise ValueError(f"Computed channel '{self.name}' must define 'compute'")
            if "operation" not in self.compute:
                raise ValueError(f"Computed channel '{self.name}' missing compute.operation")
            if "channels" not in self.compute or not isinstance(self.compute["channels"], list):
                raise ValueError(f"Computed channel '{self.name}' missing compute.channels list")

            inputs = self.compute.get("inputs", "value")
            if inputs not in {"value", "raw"}:
                raise ValueError(f"Computed channel '{self.name}' compute.inputs must be 'value' or 'raw'")

            factor = self.compute.get("factor", 1.0)
            if not isinstance(factor, (int, float)):
                raise ValueError(f"Computed channel '{self.name}' compute.factor must be numeric")

        if not isinstance(self.scale, (int, float)) or not isinstance(self.lsb, (int, float)):
            raise ValueError(f"Channel '{self.name}' scale/lsb must be numeric")

    def as_dict(self) -> dict:
        d = {
            "channel_id": self.channel_id,
            "name": self.name,
            "is_measured": self.is_measured,
            "encode": self.encode,
            "display_unit": self.display_unit,
            "scale": self.scale,
            "lsb": self.lsb,
        }
        if self.compute:
            d["compute"] = dict(self.compute)
        if self.is_measured:
            d["endian"] = self.endian
        return d

    # --- measured ---
    @property
    def size(self) -> int:
        if not self.is_measured:
            return 0
        assert self.encode is not None
        return primitive_size(self.encode)

    def decode_raw_bytes(self, raw_bytes: bytes) -> float:
        if not self.is_measured:
            raise RuntimeError(f"Cannot decode bytes for computed channel '{self.name}'")
        assert self.encode is not None
        return float(decode_primitive(self.encode, raw_bytes, endian=self.endian))

    def to_display_units(self, raw_value: float) -> float:
        return float(raw_value) * self.lsb * self.scale

    # --- computed ---
    def evaluate_computed(self, deps: Dict[int, ChannelReading]) -> float:
        """
        Returns raw-like computed result before lsb*scale.
        Apply compute.factor here.
        """
        if self.is_measured:
            raise RuntimeError(f"Measured channel '{self.name}' cannot be computed")

        assert self.compute is not None
        op = str(self.compute["operation"])
        dep_ids: List[int] = list(self.compute["channels"])

        inputs = self.compute.get("inputs", "value")
        factor = float(self.compute.get("factor", 1.0))

        missing = [cid for cid in dep_ids if cid not in deps]
        if missing:
            raise ValueError(f"Cannot compute '{self.name}': missing deps {missing}")

        vals: List[float] = []
        for cid in dep_ids:
            r = deps[cid]
            src = r.value if inputs == "value" else r.raw
            if src is None:
                raise ValueError(f"Cannot compute '{self.name}': dep {cid} has no {inputs}")
            vals.append(float(src))

        result = eval_op(op, vals)
        return float(result * factor)

    def __repr__(self) -> str:
        return f"Channel(id={self.channel_id}, name='{self.name}', measured={self.is_measured})"

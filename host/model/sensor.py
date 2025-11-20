# host/model/sensor.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .channel import Channel, ChannelReading


@dataclass(frozen=True)
class DecodedReading:
    """
    A decoded reading for a sensor payload.

    measured: decoded measured channels
    computed: computed channels (if requested)
    all: convenience merged dict of both
    """
    sensor_type_id: int
    sensor_name: str
    measured: Dict[int, ChannelReading]
    computed: Dict[int, ChannelReading]

    @property
    def all(self) -> Dict[int, ChannelReading]:
        out = dict(self.measured)
        out.update(self.computed)
        return out

    def as_dict(self, *, include_raw: bool = True) -> dict:
        def _cr_to_dict(cr: ChannelReading) -> dict:
            d = {
                "channel_id": cr.channel_id,
                "name": cr.name,
                "is_measured": cr.is_measured,
                "value": cr.value,
                "unit": cr.unit,
            }
            if include_raw:
                d["raw"] = cr.raw
            return d

        return {
            "sensor_type_id": self.sensor_type_id,
            "sensor_name": self.sensor_name,
            "measured": {cid: _cr_to_dict(cr) for cid, cr in self.measured.items()},
            "computed": {cid: _cr_to_dict(cr) for cid, cr in self.computed.items()},
        }


class Sensor:
    """
    Static model of a sensor type.

    - Holds channel metadata (measured + computed).
    - Provides pure decoding of STREAM payloads into per-channel readings.
    - Useful even without the runtime layer.

    Payload rule:
      STREAM payload contains *measured channels only*, packed sequentially.
      Ordering controlled by payload_order:
        - "channel_id" (default): measured channels sorted by channel_id
        - "insertion": measured channels in the order they were added (YAML order)
    """

    def __init__(
        self,
        type_id: int,
        name: str,
        channels: Optional[List[Channel]] = None,
        *,
        payload_order: str = "channel_id",
    ):
        self.type_id: int = int(type_id)
        self.name: str = name
        self.channels: List[Channel] = channels or []
        self.payload_order: str = payload_order

        self._validate()

    # ------------------------------------------------------------------
    # Channel management / access
    # ------------------------------------------------------------------
    def add_channel(self, channel: Channel) -> None:
        if any(ch.channel_id == channel.channel_id for ch in self.channels):
            raise ValueError(
                f"Channel ID '{channel.channel_id}' already exists in sensor '{self.name}'"
            )
        self.channels.append(channel)
        self._validate()

    @property
    def channels_by_id(self) -> Dict[int, Channel]:
        return {ch.channel_id: ch for ch in self.channels}

    def get_channel(self, channel_id: int) -> Optional[Channel]:
        return self.channels_by_id.get(channel_id)

    def measured_channels(self) -> List[Channel]:
        chans = [ch for ch in self.channels if ch.is_measured]
        if self.payload_order == "insertion":
            return chans
        return sorted(chans, key=lambda c: c.channel_id)

    def computed_channels(self) -> List[Channel]:
        return sorted([ch for ch in self.channels if not ch.is_measured], key=lambda c: c.channel_id)

    # ------------------------------------------------------------------
    # Payload decoding
    # ------------------------------------------------------------------
    def expected_payload_size(self) -> int:
        return sum(ch.size for ch in self.measured_channels())

    def decode_payload(
        self,
        payload: bytes,
        *,
        compute: bool = True,
        strict_length: bool = False,
    ) -> DecodedReading:
        """
        Decode measured channels from payload and optionally compute derived channels.

        ChannelReading:
          - raw: decoded MCU numeric value (measured) or computed intermediate (computed)
          - value: display value after applying lsb*scale
          - unit: display_unit

        strict_length:
          If True, raises if payload length != expected measured payload length.
        """
        measured: Dict[int, ChannelReading] = {}

        expected = self.expected_payload_size()
        if len(payload) < expected:
            raise ValueError(
                f"Payload too short for sensor '{self.name}' (type_id={self.type_id}): "
                f"expected at least {expected} bytes, got {len(payload)}."
            )
        if strict_length and len(payload) != expected:
            raise ValueError(
                f"Payload length mismatch for sensor '{self.name}' (type_id={self.type_id}): "
                f"expected {expected} bytes, got {len(payload)}."
            )

        offset = 0
        for ch in self.measured_channels():
            size = ch.size
            raw_bytes = payload[offset: offset + size]
            offset += size

            raw = float(ch.decode_raw_bytes(raw_bytes))
            val = float(ch.to_display_units(raw))
            measured[ch.channel_id] = ChannelReading(
                channel_id=ch.channel_id,
                name=ch.name,
                is_measured=True,
                raw=raw,
                value=val,
                unit=ch.display_unit,
            )

        computed: Dict[int, ChannelReading] = {}
        if compute:
            computed = self.compute_channels(measured)

        return DecodedReading(
            sensor_type_id=self.type_id,
            sensor_name=self.name,
            measured=measured,
            computed=computed,
        )

    def compute_channels(self, measured: Dict[int, ChannelReading]) -> Dict[int, ChannelReading]:
        """
        Compute computed channels using the decoded context (measured + already computed).

        Computation policy:
          - evaluate_computed() returns a raw-like intermediate that may already include compute.factor
          - to_display_units() applies lsb*scale (recommended: keep computed channels lsb/scale at 1.0)
        """
        out: Dict[int, ChannelReading] = {}
        context: Dict[int, ChannelReading] = dict(measured)  # supports chained computed channels

        for ch in self.computed_channels():
            raw_result = float(ch.evaluate_computed(context))
            value = float(ch.to_display_units(raw_result))
            cr = ChannelReading(
                channel_id=ch.channel_id,
                name=ch.name,
                is_measured=False,
                raw=raw_result,
                value=value,
                unit=ch.display_unit,
            )
            out[ch.channel_id] = cr
            context[ch.channel_id] = cr

        return out

    # ------------------------------------------------------------------
    # Serialization / API helpers
    # ------------------------------------------------------------------
    def as_dict(self) -> dict:
        return {
            "type_id": self.type_id,
            "name": self.name,
            "payload_order": self.payload_order,
            "channels": {ch.channel_id: ch.as_dict() for ch in self.channels},
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate(self) -> None:
        if self.payload_order not in {"channel_id", "insertion"}:
            raise ValueError("payload_order must be 'channel_id' or 'insertion'")

        ids = [ch.channel_id for ch in self.channels]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate channel_id in sensor '{self.name}'")

        all_ids = set(ids)

        for ch in self.channels:
            # ensure compute deps are valid
            if not ch.is_measured:
                if not ch.compute:
                    raise ValueError(f"Computed channel '{ch.name}' missing compute block")

                deps = list(ch.compute.get("channels", []))
                for d in deps:
                    if d not in all_ids:
                        raise ValueError(
                            f"Channel '{ch.name}' compute dependency {d} not found in sensor '{self.name}'"
                        )

                # validate new compute keys
                inputs = ch.compute.get("inputs", "value")
                if inputs not in {"value", "raw"}:
                    raise ValueError(
                        f"Channel '{ch.name}' compute.inputs must be 'value' or 'raw' (got {inputs})"
                    )

                factor = ch.compute.get("factor", 1.0)
                if not isinstance(factor, (int, float)):
                    raise ValueError(
                        f"Channel '{ch.name}' compute.factor must be numeric (got {factor})"
                    )

    def __repr__(self) -> str:
        return f"Sensor(type_id={self.type_id}, name='{self.name}', channels={len(self.channels)})"

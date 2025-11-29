# host/transport/factory.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Mapping

from host.model.transport import TransportType
from host.transport.base import Transport as HwTransport
from host.transport.registry import TransportDriverRegistry
from host.transport.params import TransportParamResolver
from host.transport.errors import TransportError
from host.core.errors import TransportConfigError


@dataclass(frozen=True)
class DeviceTransport:
    transport: HwTransport
    params: Dict[str, Any]
    meta: TransportType


class TransportFactory:
    """
    Constructs a transport instance from metadata + overrides.
    Note: does NOT open the transport.
    """

    def __init__(
        self,
        transports: Mapping[int, TransportType],
        drivers: TransportDriverRegistry,
    ):
        self._transports = transports
        self._drivers = drivers
        self._params = TransportParamResolver(transports)

    def transports(self) -> Mapping[int, TransportType]:
        return dict(self._transports)

    def create(self, type_id: int, overrides: Optional[Dict[str, Any]] = None) -> DeviceTransport:
        overrides = overrides or {}
        meta = self._transports.get(int(type_id))
        if not meta:
            raise TransportConfigError(
                f"No transport metadata id={type_id}.",
                hint="Check transport_type_id against your metadata.",
                details={"type_id": int(type_id)},
            ) from None

        try:
            params = self._params.resolve(type_id, overrides)
            hw = self._drivers.create(meta.driver, **params)
            return DeviceTransport(transport=hw, params=params, meta=meta)

        except TransportConfigError:
            raise

        except (TransportError, TypeError) as e:
            # unknown driver key or constructor mismatch
            raise TransportConfigError(
                f"Failed to construct transport '{meta.label}' (driver='{meta.driver}').",
                hint=str(e),
                details={
                    "type_id": int(type_id),
                    "driver": meta.driver,
                    "overrides": dict(overrides),
                },
            ) from None

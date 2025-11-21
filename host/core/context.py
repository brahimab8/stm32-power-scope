# host/core/context.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml

from host.model.loader import MetadataLoader
from host.model.sensor import Sensor
from host.model.transport import TransportType

from host.protocol.loader import ProtocolLoader
from host.protocol.core.defs import Protocol

from host.transport.registry import TransportDriverRegistry
from host.transport.factory import TransportFactory

from host.core.errors import TransportConfigError


@dataclass(frozen=True)
class Context:
    transports: Dict[int, TransportType]
    sensors: Dict[int, Sensor]
    protocol: Protocol
    protocol_version: int
    metadata_hashes: Dict[str, str]
    protocol_hashes: Dict[str, str]
    transport_factory: TransportFactory

    @classmethod
    def load(
        cls,
        metadata_dir: str | Path,
        protocol_dir: str | Path,
        *,
        drivers: Optional[TransportDriverRegistry] = None,
    ) -> "Context":
        """
        Load metadata + protocol definitions and construct a transport factory.

        `drivers` is injectable to support testing and custom driver registries.
        If not provided, the default built-in registry is used.
        """
        metadata_dir = Path(metadata_dir)
        protocol_dir = Path(protocol_dir)

        ml = MetadataLoader(metadata_dir)
        try:
            ml.load_all()
        except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
            raise TransportConfigError(
                "Failed to load metadata.",
                hint=str(e),
                details={"metadata_dir": str(metadata_dir)},
            ) from None
        except Exception as e:
            raise TransportConfigError(
                "Unexpected error while loading metadata.",
                hint=str(e),
                details={"metadata_dir": str(metadata_dir)},
            ) from None

        pl = ProtocolLoader(protocol_dir)
        try:
            pl.load_all()
            proto = Protocol(pl)
        except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
            raise TransportConfigError(
                "Failed to load protocol definition.",
                hint=str(e),
                details={"protocol_dir": str(protocol_dir)},
            ) from None
        except Exception as e:
            raise TransportConfigError(
                "Unexpected error while loading protocol definition.",
                hint=str(e),
                details={"protocol_dir": str(protocol_dir)},
            ) from None

        drivers = drivers or TransportDriverRegistry.default()
        factory = TransportFactory(ml.transports, drivers)

        return cls(
            transports=ml.transports,
            sensors=ml.sensors,
            protocol=proto,
            protocol_version=pl.protocol_version(),
            metadata_hashes=dict(ml.file_hashes),
            protocol_hashes=dict(pl.file_hashes),
            transport_factory=factory,
        )

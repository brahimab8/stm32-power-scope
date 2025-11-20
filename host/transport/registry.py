from __future__ import annotations

from typing import Dict, Type

from .base import Transport
from .uart import UARTTransport
from .usb import USBTransport
from .errors import TransportError


class TransportDriverRegistry:
    """
    Adapter-only registry that maps driver keys -> concrete HW transport classes.

    - NO metadata loading
    - NO YAML
    - NO model imports
    """

    def __init__(self, drivers: Dict[str, Type[Transport]]):
        # normalize keys to be case-insensitive
        self._drivers: Dict[str, Type[Transport]] = {k.lower(): v for k, v in drivers.items()}

    @classmethod
    def default(cls) -> "TransportDriverRegistry":
        return cls(
            drivers={
                "uart": UARTTransport,
                "usb": USBTransport,
            }
        )

    def has(self, driver: str) -> bool:
        return driver.lower() in self._drivers

    def get_class(self, driver: str) -> Type[Transport]:
        key = driver.lower()
        if key not in self._drivers:
            raise TransportError(f"Transport driver '{driver}' not registered")
        return self._drivers[key]

    def create(self, driver: str, **params) -> Transport:
        """
        Instantiate a HW transport by driver key.
        """
        transport_cls = self.get_class(driver)
        return transport_cls(**params)

from __future__ import annotations

import pytest

from host.transport.registry import TransportDriverRegistry
from host.transport.base import Transport
from host.transport.errors import TransportError


class DummyTransport(Transport):
    def __init__(self, *, x: int = 0):
        self.x = x

    def open(self) -> None: ...
    def close(self) -> None: ...
    def read(self, n: int) -> bytes: return b""
    def write(self, data: bytes) -> int: return len(data)
    def flush(self) -> None: ...


def test_registry_has_and_get_class_case_insensitive():
    reg = TransportDriverRegistry({"DUMMY": DummyTransport})

    assert reg.has("dummy") is True
    assert reg.has("DUMMY") is True
    assert reg.has("DuMmY") is True

    cls = reg.get_class("dummy")
    assert cls is DummyTransport


def test_registry_get_class_unknown_raises():
    reg = TransportDriverRegistry({})
    with pytest.raises(TransportError):
        reg.get_class("uart")


def test_registry_create_instantiates_with_params():
    reg = TransportDriverRegistry({"dummy": DummyTransport})

    t = reg.create("DUMMY", x=42)
    assert isinstance(t, DummyTransport)
    assert t.x == 42

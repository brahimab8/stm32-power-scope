# host/transport/errors.py
from __future__ import annotations

class TransportError(Exception):
    """Base class for transport-layer failures."""

class TransportOpenError(TransportError):
    pass

class TransportIOError(TransportError):
    pass

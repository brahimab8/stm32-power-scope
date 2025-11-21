# host/runtime/errors.py
from __future__ import annotations


class PowerScopeError(Exception):
    """
    Base class for all expected operational errors in PowerScope.
    """

    #: Stable machine-readable identifier (for CLI exit mapping, daemon APIs, etc.)
    code: str = "unknown"

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.details = details or {}

    def __str__(self) -> str:
        return self.message


# ---------------------------------------------------------------------------
# Configuration / setup errors (no hardware access yet)
# ---------------------------------------------------------------------------

class TransportConfigError(PowerScopeError):
    """
    Transport configuration is invalid or inconsistent with metadata.

    Examples:
      - unknown transport type id
      - unknown driver key
      - invalid / missing transport parameters
      - metadata does not match transport constructor
    """
    code = "transport_config_error"


# ---------------------------------------------------------------------------
# Transport / connection lifecycle errors
# ---------------------------------------------------------------------------

class DeviceConnectError(PowerScopeError):
    """
    Transport could not be opened or initialized.

    Examples:
      - COM port not found
      - permission denied
      - device already in use
      - USB CDC open failure
    """
    code = "device_connect_error"


class DeviceDisconnectedError(PowerScopeError):
    """
    Device was previously connected but is no longer reachable.

    Examples:
      - USB unplugged
      - UART cable removed
      - OS-level I/O error during read/write
    """
    code = "device_disconnected"


# ---------------------------------------------------------------------------
# Protocol / communication errors
# ---------------------------------------------------------------------------

class ProtocolCommunicationError(PowerScopeError):
    """
    Protocol-level communication failure.

    Examples:
      - command send failed
      - command timeout
      - framing errors
      - protocol desynchronization
    """
    code = "protocol_communication_error"


class McuNotRespondingError(PowerScopeError):
    """
    MCU is reachable at transport level but not responding correctly.

    Examples:
      - PING returns not-ok
      - commands consistently fail
      - protocol is running but firmware is not behaving as expected
    """
    code = "mcu_not_responding"


# ---------------------------------------------------------------------------
# Sensor / data errors
# ---------------------------------------------------------------------------

class SensorDecodeError(PowerScopeError):
    """
    Sensor data was received but could not be decoded.

    Examples:
      - malformed payload
      - firmware / host protocol mismatch
      - decode exception in sensor metadata
    """
    code = "sensor_decode_error"


class SensorOperationError(PowerScopeError):
    """
    Sensor-related command failed.

    Examples:
      - start_stream / stop_stream rejected
      - set_period failed
      - invalid runtime_id
    """
    code = "sensor_operation_error"

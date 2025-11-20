# host/transport/uart.py
from __future__ import annotations

from typing import Optional

import serial
from serial import SerialException

from .base import Transport
from .errors import TransportIOError, TransportOpenError


class UARTTransport(Transport):
    """
    UART transport implemented via pyserial.

    read(n) attempts to read up to n bytes and may return fewer due to timeout.
    """

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.05):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    def open(self) -> None:
        try:
            self.ser = serial.Serial(
                self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except SerialException as e:
            self.ser = None
            raise TransportOpenError(str(e)) from None

    def close(self) -> None:
        if self.ser is not None:
            try:
                self.ser.close()
            finally:
                self.ser = None

    def is_open(self) -> bool:
        return self.ser is not None and self.ser.is_open

    def read(self, n: int) -> bytes:
        if self.ser is None:
            raise TransportIOError("read while transport not open")

        try:
            buf = b""
            while len(buf) < n:
                chunk = self.ser.read(n - len(buf))
                if not chunk:
                    # timeout reached → return whatever is collected
                    break
                buf += chunk
            return buf
        except SerialException as e:
            self.ser = None
            raise TransportIOError(f"UART read failed: {e}") from None

    def write(self, data: bytes) -> int:
        if self.ser is None:
            raise TransportIOError("write while transport not open")

        try:
            return self.ser.write(data)
        except SerialException as e:
            self.ser = None
            raise TransportIOError(f"UART write failed: {e}") from None

    def flush(self) -> None:
        if self.ser is None:
            raise TransportIOError("flush while transport not open")

        try:
            self.ser.flush()
        except SerialException as e:
            self.ser = None
            raise TransportIOError(f"UART flush failed: {e}") from None

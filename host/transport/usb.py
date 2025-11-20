# host/transport/usb.py
from __future__ import annotations

import time
from typing import Optional

import serial
from serial import SerialException

from .base import Transport
from .errors import TransportIOError, TransportOpenError


class USBTransport(Transport):
    """
    USB CDC transport implemented via pyserial.

    Notes:
      - Uses the Transport.read(n) contract: returns 0..n bytes.
      - Optionally toggles DTR/RTS on open to reset some MCU CDC implementations.
    """

    def __init__(
        self,
        port: str,
        timeout: float = 1.0,
        assert_dtr: bool = True,
        baudrate: int = 115200,
        reset_delay_s: float = 0.1,
        post_reset_delay_s: float = 0.5,
    ):
        self.port = port
        self.timeout = timeout
        self.assert_dtr = assert_dtr
        self.baudrate = baudrate
        self.reset_delay_s = reset_delay_s
        self.post_reset_delay_s = post_reset_delay_s
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

            if self.assert_dtr:
                # Toggle DTR/RTS to reset some MCU CDC firmwares (e.g., STM32).
                self.ser.dtr = False
                self.ser.rts = False
                time.sleep(self.reset_delay_s)

                self.ser.dtr = True
                self.ser.rts = True
                # Allow MCU reboot to settle / start streaming.
                time.sleep(self.post_reset_delay_s)

        except SerialException as e:
            self.ser = None
            raise TransportOpenError(f"could not open USB CDC port {self.port!r}: {e}") from None

    def close(self) -> None:
        if self.ser is not None:
            try:
                self.ser.close()
            finally:
                self.ser = None

    def read(self, n: int) -> bytes:
        if self.ser is None:
            raise TransportIOError("read while transport not open")

        try:
            # attempt up to n bytes, may return fewer due to timeout.
            buf = b""
            while len(buf) < n:
                chunk = self.ser.read(n - len(buf))
                if not chunk:
                    break
                buf += chunk
            return buf
        except SerialException as e:
            self.ser = None
            raise TransportIOError(f"USB read failed (device disconnected or unavailable): {e}") from None

    def write(self, data: bytes) -> int:
        if self.ser is None:
            raise TransportIOError("write while transport not open")

        try:
            return self.ser.write(data)
        except SerialException as e:
            self.ser = None
            raise TransportIOError(f"USB write failed (device disconnected?): {e}") from None

    def flush(self) -> None:
        if self.ser is None:
            raise TransportIOError("flush while transport not open")

        try:
            self.ser.flush()
        except SerialException as e:
            self.ser = None
            raise TransportIOError(f"USB flush failed (device disconnected?): {e}") from None

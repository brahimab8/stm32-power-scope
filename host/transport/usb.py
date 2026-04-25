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
        read_timeout: float = 0.05,
        write_timeout: float = 1.0,
        assert_dtr: bool = True,
        baudrate: int = 115200,
        reset_delay_s: float = 0.1,
        post_reset_delay_s: float = 0.5,
    ):
        self.port = port
        self.read_timeout = read_timeout
        self.write_timeout = write_timeout
        self.assert_dtr = assert_dtr
        self.baudrate = baudrate
        self.reset_delay_s = reset_delay_s
        self.post_reset_delay_s = post_reset_delay_s
        self.ser: Optional[serial.Serial] = None

    def open(self) -> None:
        if self.ser is not None:
            return  # already open, skip

        # Wait for port to appear — handles Windows re-enumeration after probe closes
        from serial.tools import list_ports
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if self.port in [p.device for p in list_ports.comports()]:
                break
            time.sleep(0.2)
        else:
            raise TransportOpenError(
                f"USB CDC port {self.port!r} did not appear within 5s."
            )

        # Retry opening — Windows may hold handle briefly after probe closes
        last_exc: Exception | None = None
        for _ in range(10):
            try:
                self.ser = serial.Serial(
                    self.port,
                    baudrate=self.baudrate,
                    timeout=self.read_timeout,
                    write_timeout=self.write_timeout,
                )
                break
            except SerialException as e:
                last_exc = e
                self.ser = None
                time.sleep(0.3)
        else:
            raise TransportOpenError(
                f"could not open USB CDC port {self.port!r}: {last_exc}"
            ) from None

        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            if self.assert_dtr:
                self.ser.dtr = False
                self.ser.rts = False
                time.sleep(self.reset_delay_s)
                self.ser.dtr = True
                self.ser.rts = True
                time.sleep(self.post_reset_delay_s)
            else:
                self.ser.dtr = True
                time.sleep(self.post_reset_delay_s)

        except SerialException as e:
            self.ser = None
            raise TransportOpenError(
                f"could not open USB CDC port {self.port!r}: {e}"
            ) from None
    
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
            return self.ser.read(n)
        except SerialException as e:
            self.ser = None
            raise TransportIOError(f"USB read failed: {e}") from None

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

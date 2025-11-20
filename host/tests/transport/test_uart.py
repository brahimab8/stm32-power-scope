from __future__ import annotations

import pytest

import host.transport.uart as uart_mod
from host.transport.errors import TransportIOError, TransportOpenError


class FakeSerial:
    def __init__(self, port, baudrate, timeout, write_timeout):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.is_open = True

        self._read_chunks = []
        self._write_ret = 0
        self._raise_on_read = None
        self._raise_on_write = None
        self._raise_on_flush = None

        self.reset_in_called = 0
        self.reset_out_called = 0
        self.flush_called = 0
        self.close_called = 0

    def reset_input_buffer(self):
        self.reset_in_called += 1

    def reset_output_buffer(self):
        self.reset_out_called += 1

    def read(self, n: int) -> bytes:
        if self._raise_on_read is not None:
            raise self._raise_on_read
        if not self._read_chunks:
            return b""
        return self._read_chunks.pop(0)

    def write(self, data: bytes) -> int:
        if self._raise_on_write is not None:
            raise self._raise_on_write
        return self._write_ret

    def flush(self) -> None:
        self.flush_called += 1
        if self._raise_on_flush is not None:
            raise self._raise_on_flush

    def close(self) -> None:
        self.close_called += 1
        self.is_open = False


def test_open_success_resets_buffers(monkeypatch):
    created = {}

    def fake_serial_ctor(port, baudrate, timeout, write_timeout):
        s = FakeSerial(port, baudrate, timeout, write_timeout)
        created["ser"] = s
        return s

    monkeypatch.setattr(uart_mod.serial, "Serial", fake_serial_ctor)

    t = uart_mod.UARTTransport("COM5", baudrate=9600, timeout=0.1)
    t.open()

    assert t.ser is created["ser"]
    assert t.is_open() is True
    assert created["ser"].reset_in_called == 1
    assert created["ser"].reset_out_called == 1


def test_open_serial_exception_raises_transport_open_error(monkeypatch):
    def fake_serial_ctor(*a, **k):
        raise uart_mod.SerialException("no port")

    monkeypatch.setattr(uart_mod.serial, "Serial", fake_serial_ctor)

    t = uart_mod.UARTTransport("COM404")
    with pytest.raises(TransportOpenError):
        t.open()

    assert t.ser is None


def test_read_not_open_raises():
    t = uart_mod.UARTTransport("COM1")
    with pytest.raises(TransportIOError):
        t.read(1)


def test_write_not_open_raises():
    t = uart_mod.UARTTransport("COM1")
    with pytest.raises(TransportIOError):
        t.write(b"\x00")


def test_flush_not_open_raises():
    t = uart_mod.UARTTransport("COM1")
    with pytest.raises(TransportIOError):
        t.flush()


def test_read_collects_until_n_or_timeout(monkeypatch):
    s = FakeSerial("COM1", 115200, 0.05, 0.05)
    s._read_chunks = [b"\x01", b"\x02\x03", b""]  # last empty simulates timeout
    monkeypatch.setattr(uart_mod.serial, "Serial", lambda *a, **k: s)

    t = uart_mod.UARTTransport("COM1")
    t.open()

    out = t.read(5)
    assert out == b"\x01\x02\x03"  # stopped early due to empty chunk


def test_read_serial_exception_clears_ser_and_raises(monkeypatch):
    s = FakeSerial("COM1", 115200, 0.05, 0.05)
    s._raise_on_read = uart_mod.SerialException("read fail")
    monkeypatch.setattr(uart_mod.serial, "Serial", lambda *a, **k: s)

    t = uart_mod.UARTTransport("COM1")
    t.open()

    with pytest.raises(TransportIOError):
        t.read(1)

    assert t.ser is None


def test_write_returns_bytes_written(monkeypatch):
    s = FakeSerial("COM1", 115200, 0.05, 0.05)
    s._write_ret = 4
    monkeypatch.setattr(uart_mod.serial, "Serial", lambda *a, **k: s)

    t = uart_mod.UARTTransport("COM1")
    t.open()

    assert t.write(b"abcd") == 4


def test_write_serial_exception_clears_ser_and_raises(monkeypatch):
    s = FakeSerial("COM1", 115200, 0.05, 0.05)
    s._raise_on_write = uart_mod.SerialException("write fail")
    monkeypatch.setattr(uart_mod.serial, "Serial", lambda *a, **k: s)

    t = uart_mod.UARTTransport("COM1")
    t.open()

    with pytest.raises(TransportIOError):
        t.write(b"x")

    assert t.ser is None


def test_flush_calls_underlying_flush(monkeypatch):
    s = FakeSerial("COM1", 115200, 0.05, 0.05)
    monkeypatch.setattr(uart_mod.serial, "Serial", lambda *a, **k: s)

    t = uart_mod.UARTTransport("COM1")
    t.open()

    t.flush()
    assert s.flush_called == 1


def test_flush_serial_exception_clears_ser_and_raises(monkeypatch):
    s = FakeSerial("COM1", 115200, 0.05, 0.05)
    s._raise_on_flush = uart_mod.SerialException("flush fail")
    monkeypatch.setattr(uart_mod.serial, "Serial", lambda *a, **k: s)

    t = uart_mod.UARTTransport("COM1")
    t.open()

    with pytest.raises(TransportIOError):
        t.flush()

    assert t.ser is None


def test_close_closes_and_clears(monkeypatch):
    s = FakeSerial("COM1", 115200, 0.05, 0.05)
    monkeypatch.setattr(uart_mod.serial, "Serial", lambda *a, **k: s)

    t = uart_mod.UARTTransport("COM1")
    t.open()
    t.close()

    assert s.close_called == 1
    assert t.ser is None

from __future__ import annotations

import pytest

import host.transport.usb as usb_mod
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

        self.dtr = None
        self.rts = None

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
    s = FakeSerial("COM9", 115200, 1.0, 1.0)
    monkeypatch.setattr(usb_mod.serial, "Serial", lambda *a, **k: s)
    monkeypatch.setattr(usb_mod.time, "sleep", lambda _t: None)

    t = usb_mod.USBTransport("COM9", assert_dtr=False)
    t.open()

    assert t.ser is s
    assert s.reset_in_called == 1
    assert s.reset_out_called == 1


def test_open_with_dtr_toggle_sets_lines_and_sleeps(monkeypatch):
    s = FakeSerial("COM9", 115200, 1.0, 1.0)
    monkeypatch.setattr(usb_mod.serial, "Serial", lambda *a, **k: s)

    sleeps = []
    monkeypatch.setattr(usb_mod.time, "sleep", lambda t: sleeps.append(t))

    t = usb_mod.USBTransport(
        "COM9",
        assert_dtr=True,
        reset_delay_s=0.11,
        post_reset_delay_s=0.22,
    )
    t.open()

    assert s.dtr is True
    assert s.rts is True
    assert sleeps == [0.11, 0.22]


def test_open_serial_exception_raises_transport_open_error(monkeypatch):
    def bad_ctor(*a, **k):
        raise usb_mod.SerialException("no port")

    monkeypatch.setattr(usb_mod.serial, "Serial", bad_ctor)

    t = usb_mod.USBTransport("COM404")
    with pytest.raises(TransportOpenError):
        t.open()

    assert t.ser is None


def test_read_write_flush_not_open_raise():
    t = usb_mod.USBTransport("COM1")
    with pytest.raises(TransportIOError):
        t.read(1)
    with pytest.raises(TransportIOError):
        t.write(b"\x00")
    with pytest.raises(TransportIOError):
        t.flush()


def test_read_collects_until_n_or_timeout(monkeypatch):
    s = FakeSerial("COM1", 115200, 1.0, 1.0)
    s._read_chunks = [b"\x01", b"\x02\x03", b""]  # timeout
    monkeypatch.setattr(usb_mod.serial, "Serial", lambda *a, **k: s)
    monkeypatch.setattr(usb_mod.time, "sleep", lambda _t: None)

    t = usb_mod.USBTransport("COM1", assert_dtr=False)
    t.open()

    out = t.read(5)
    assert out == b"\x01\x02\x03"


def test_read_serial_exception_clears_ser_and_raises(monkeypatch):
    s = FakeSerial("COM1", 115200, 1.0, 1.0)
    s._raise_on_read = usb_mod.SerialException("read fail")
    monkeypatch.setattr(usb_mod.serial, "Serial", lambda *a, **k: s)
    monkeypatch.setattr(usb_mod.time, "sleep", lambda _t: None)

    t = usb_mod.USBTransport("COM1", assert_dtr=False)
    t.open()

    with pytest.raises(TransportIOError):
        t.read(1)

    assert t.ser is None


def test_write_returns_bytes_written(monkeypatch):
    s = FakeSerial("COM1", 115200, 1.0, 1.0)
    s._write_ret = 3
    monkeypatch.setattr(usb_mod.serial, "Serial", lambda *a, **k: s)
    monkeypatch.setattr(usb_mod.time, "sleep", lambda _t: None)

    t = usb_mod.USBTransport("COM1", assert_dtr=False)
    t.open()

    assert t.write(b"abc") == 3


def test_write_serial_exception_clears_ser_and_raises(monkeypatch):
    s = FakeSerial("COM1", 115200, 1.0, 1.0)
    s._raise_on_write = usb_mod.SerialException("write fail")
    monkeypatch.setattr(usb_mod.serial, "Serial", lambda *a, **k: s)
    monkeypatch.setattr(usb_mod.time, "sleep", lambda _t: None)

    t = usb_mod.USBTransport("COM1", assert_dtr=False)
    t.open()

    with pytest.raises(TransportIOError):
        t.write(b"x")

    assert t.ser is None


def test_flush_calls_underlying_flush(monkeypatch):
    s = FakeSerial("COM1", 115200, 1.0, 1.0)
    monkeypatch.setattr(usb_mod.serial, "Serial", lambda *a, **k: s)
    monkeypatch.setattr(usb_mod.time, "sleep", lambda _t: None)

    t = usb_mod.USBTransport("COM1", assert_dtr=False)
    t.open()

    t.flush()
    assert s.flush_called == 1


def test_flush_serial_exception_clears_ser_and_raises(monkeypatch):
    s = FakeSerial("COM1", 115200, 1.0, 1.0)
    s._raise_on_flush = usb_mod.SerialException("flush fail")
    monkeypatch.setattr(usb_mod.serial, "Serial", lambda *a, **k: s)
    monkeypatch.setattr(usb_mod.time, "sleep", lambda _t: None)

    t = usb_mod.USBTransport("COM1", assert_dtr=False)
    t.open()

    with pytest.raises(TransportIOError):
        t.flush()

    assert t.ser is None


def test_close_closes_and_clears(monkeypatch):
    s = FakeSerial("COM1", 115200, 1.0, 1.0)
    monkeypatch.setattr(usb_mod.serial, "Serial", lambda *a, **k: s)
    monkeypatch.setattr(usb_mod.time, "sleep", lambda _t: None)

    t = usb_mod.USBTransport("COM1", assert_dtr=False)
    t.open()
    t.close()

    assert s.close_called == 1
    assert t.ser is None

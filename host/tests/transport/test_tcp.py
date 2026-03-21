from __future__ import annotations

import pytest

import host.transport.tcp as tcp_mod
from host.transport.errors import TransportIOError, TransportOpenError


class FakeSocket:
    def __init__(self):
        self.timeout = None
        self.sockopt_calls = []
        self.recv_chunks = []
        self.raise_on_recv = None
        self.raise_on_sendall = None
        self.raise_on_shutdown = None

        self.sendall_calls = []
        self.shutdown_called = 0
        self.close_called = 0

    def settimeout(self, timeout):
        self.timeout = timeout

    def setsockopt(self, level, optname, value):
        self.sockopt_calls.append((level, optname, value))

    def recv(self, n: int) -> bytes:
        if self.raise_on_recv is not None:
            raise self.raise_on_recv
        if not self.recv_chunks:
            return b""
        return self.recv_chunks.pop(0)

    def sendall(self, data: bytes) -> None:
        if self.raise_on_sendall is not None:
            raise self.raise_on_sendall
        self.sendall_calls.append(data)

    def shutdown(self, how) -> None:
        self.shutdown_called += 1
        if self.raise_on_shutdown is not None:
            raise self.raise_on_shutdown

    def close(self) -> None:
        self.close_called += 1


def test_open_success_sets_timeout_and_nodelay(monkeypatch):
    fake = FakeSocket()
    monkeypatch.setattr(tcp_mod.socket, "create_connection", lambda *a, **k: fake)

    t = tcp_mod.TCPTransport("127.0.0.1", 9000, timeout=0.2, connect_timeout=2.5, tcp_nodelay=True)
    t.open()

    assert t.sock is fake
    assert fake.timeout == 0.2
    assert fake.sockopt_calls == [(tcp_mod.socket.IPPROTO_TCP, tcp_mod.socket.TCP_NODELAY, 1)]


def test_open_connection_error_raises_transport_open_error(monkeypatch):
    def bad_create_connection(*a, **k):
        raise OSError("connect failed")

    monkeypatch.setattr(tcp_mod.socket, "create_connection", bad_create_connection)

    t = tcp_mod.TCPTransport("127.0.0.1", 9000)
    with pytest.raises(TransportOpenError):
        t.open()
    assert t.sock is None


def test_read_write_flush_not_open_raise():
    t = tcp_mod.TCPTransport("127.0.0.1", 9000)
    with pytest.raises(TransportIOError):
        t.read(1)
    with pytest.raises(TransportIOError):
        t.write(b"x")
    with pytest.raises(TransportIOError):
        t.flush()


def test_read_collects_until_n_or_timeout(monkeypatch):
    fake = FakeSocket()
    fake.recv_chunks = [b"\x01", b"\x02\x03"]
    monkeypatch.setattr(tcp_mod.socket, "create_connection", lambda *a, **k: fake)

    t = tcp_mod.TCPTransport("127.0.0.1", 9000)
    t.open()

    def recv_with_timeout(_n):
        if fake.recv_chunks:
            return fake.recv_chunks.pop(0)
        raise tcp_mod.socket.timeout()

    fake.recv = recv_with_timeout

    out = t.read(5)
    assert out == b"\x01\x02\x03"


def test_read_peer_closed_clears_sock_and_raises(monkeypatch):
    fake = FakeSocket()
    fake.recv_chunks = [b""]
    monkeypatch.setattr(tcp_mod.socket, "create_connection", lambda *a, **k: fake)

    t = tcp_mod.TCPTransport("127.0.0.1", 9000)
    t.open()

    with pytest.raises(TransportIOError):
        t.read(1)

    assert t.sock is None


def test_write_success_returns_len(monkeypatch):
    fake = FakeSocket()
    monkeypatch.setattr(tcp_mod.socket, "create_connection", lambda *a, **k: fake)

    t = tcp_mod.TCPTransport("127.0.0.1", 9000)
    t.open()

    n = t.write(b"abcd")
    assert n == 4
    assert fake.sendall_calls == [b"abcd"]


def test_write_oserror_clears_sock_and_raises(monkeypatch):
    fake = FakeSocket()
    fake.raise_on_sendall = OSError("send failed")
    monkeypatch.setattr(tcp_mod.socket, "create_connection", lambda *a, **k: fake)

    t = tcp_mod.TCPTransport("127.0.0.1", 9000)
    t.open()

    with pytest.raises(TransportIOError):
        t.write(b"x")

    assert t.sock is None


def test_flush_open_is_noop(monkeypatch):
    fake = FakeSocket()
    monkeypatch.setattr(tcp_mod.socket, "create_connection", lambda *a, **k: fake)

    t = tcp_mod.TCPTransport("127.0.0.1", 9000)
    t.open()
    t.flush()


def test_close_shutdown_and_close_then_clear(monkeypatch):
    fake = FakeSocket()
    monkeypatch.setattr(tcp_mod.socket, "create_connection", lambda *a, **k: fake)

    t = tcp_mod.TCPTransport("127.0.0.1", 9000)
    t.open()
    t.close()

    assert fake.shutdown_called == 1
    assert fake.close_called == 1
    assert t.sock is None

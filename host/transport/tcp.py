from __future__ import annotations

import socket
from typing import Optional

from .base import Transport
from .errors import TransportIOError, TransportOpenError


class TCPTransport(Transport):
    """
    TCP transport implemented with Python sockets.

    read(n) attempts to read up to n bytes and may return fewer due to timeout.
    """

    def __init__(
        self,
        ip: str,
        port: int = 9000,
        timeout: float = 0.1,
        connect_timeout: float = 3.0,
        tcp_nodelay: bool = True,
    ):
        self.ip = ip
        self.port = int(port)
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.tcp_nodelay = tcp_nodelay
        self.sock: Optional[socket.socket] = None

    def open(self) -> None:
        try:
            sock = socket.create_connection(
                (self.ip, self.port),
                timeout=self.connect_timeout,
            )
            sock.settimeout(self.timeout)

            if self.tcp_nodelay:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            self.sock = sock
        except OSError as e:
            self.sock = None
            raise TransportOpenError(f"could not open TCP connection to {self.ip}:{self.port}: {e}") from None

    def close(self) -> None:
        if self.sock is not None:
            try:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.sock.close()
            finally:
                self.sock = None

    def read(self, n: int) -> bytes:
        if self.sock is None:
            raise TransportIOError("read while transport not open")

        if n <= 0:
            return b""

        try:
            buf = b""
            while len(buf) < n:
                try:
                    chunk = self.sock.recv(n - len(buf))
                except socket.timeout:
                    break

                if not chunk:
                    self.sock = None
                    raise TransportIOError("TCP read failed: connection closed by peer")

                buf += chunk
            return buf
        except TransportIOError:
            raise
        except OSError as e:
            self.sock = None
            raise TransportIOError(f"TCP read failed: {e}") from None

    def write(self, data: bytes) -> int:
        if self.sock is None:
            raise TransportIOError("write while transport not open")

        if not data:
            return 0

        try:
            self.sock.sendall(data)
            return len(data)
        except OSError as e:
            self.sock = None
            raise TransportIOError(f"TCP write failed: {e}") from None

    def flush(self) -> None:
        if self.sock is None:
            raise TransportIOError("flush while transport not open")

        # No buffering at this layer for TCP sockets.
        return None

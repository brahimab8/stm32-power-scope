from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Transport(ABC):
    """
    Abstract transport interface (USB, UART, TCP, etc.).

    Contract:
      - open()/close() manage the underlying connection.
      - read(n) returns 0..n bytes. It may return fewer than n bytes due to timeouts
        or non-blocking behavior, and may return b"" when no data is available.
      - write(data) returns the number of bytes written.
      - flush() forces pending output to be transmitted.
    """

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def read(self, n: int) -> bytes: ...

    @abstractmethod
    def write(self, data: bytes) -> int: ...

    @abstractmethod
    def flush(self) -> None: ...

    def __enter__(self) -> "Transport":
        self.open()
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        self.close()

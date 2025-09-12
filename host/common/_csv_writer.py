# host/common/_csv_writer.py
from __future__ import annotations
from typing import Dict, Tuple, Optional, TextIO
import os

class CsvLogWriter:
    """Line-buffered CSV writer with fixed channel order."""
    def __init__(self, path: str, channels: Tuple[str, ...]) -> None:
        self._path = os.fspath(path)
        self._channels = tuple(channels)
        self._f: Optional[TextIO] = None
        self._bytes_written = 0
        self._open()

    def _open(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        self._f = open(self._path, "w", buffering=1, encoding="utf-8", newline="")
        header = ",".join(["idx", "seq", "ts_ms", *self._channels]) + "\n"
        self._f.write(header)
        self._bytes_written += len(header.encode("utf-8", errors="ignore"))

    def close(self) -> None:
        f, self._f = self._f, None
        if f:
            try:
                f.flush()
            finally:
                try: f.close()
                except Exception: pass

    def __del__(self) -> None:
        try: self.close()
        except Exception: pass

    @property
    def path(self) -> str: return self._path
    @property
    def bytes_written(self) -> int: return self._bytes_written

    def write(self, idx: int, seq: int, ts_ms: int, values: Dict[str, int]) -> None:
        if not self._f:
            raise RuntimeError("CsvLogWriter is closed")
        parts = [str(int(idx)), str(int(seq)), str(int(ts_ms))]
        for ch in self._channels:
            parts.append(str(int(values.get(ch, 0))))
        line = ",".join(parts) + "\n"
        self._f.write(line)
        self._bytes_written += len(line.encode("utf-8", errors="ignore"))

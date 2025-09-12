# host/common/logging.py
"""
Main logging entry for CLI & GUI.

- Exposes LogController.
- Re-exports DEFAULTS, make_log_path, logs_root from logging_config.
"""

from __future__ import annotations
from typing import Dict, Tuple, Optional, Callable
import time
from pathlib import Path

from .logging_config import DEFAULTS, make_log_path, logs_root  # re-exported
from ._csv_writer import CsvLogWriter
from ._file_lock import FileLock


def _global_lock_file() -> Path:
    return logs_root() / DEFAULTS.lock_filename


class LogController:
    """
    Small stateful logger with single-instance enforcement (file lock).

    on_stop(reason) is called once with:
      'stopped' | 'max_seconds' | 'max_frames' | 'max_bytes' | 'error' | 'disconnected'
    """
    def __init__(self, channels: Tuple[str, ...], on_stop: Optional[Callable[[str], None]] = None) -> None:
        self._channels = tuple(channels)
        self._on_stop = on_stop

        self._writer: Optional[CsvLogWriter] = None
        self._frames_written = 0

        self._max_seconds: Optional[float] = None
        self._max_frames:  Optional[int]   = None
        self._max_bytes:   Optional[int]   = None

        self._t0_device_ms: Optional[int] = None
        self._t0_wall_s:    Optional[float] = None

        self._stopped_reason: Optional[str] = None

        self._lock = FileLock(_global_lock_file())
        self._lock_held = False

        self._last_path: Optional[str] = None  # returned by .path even after stop()

    # --- state ---
    @property
    def active(self) -> bool:
        return self._writer is not None and self._stopped_reason is None

    @property
    def path(self) -> Optional[str]:
        return self._writer.path if self._writer else self._last_path

    @property
    def frames_written(self) -> int:
        return self._frames_written

    @property
    def bytes_written(self) -> int:
        return self._writer.bytes_written if self._writer else 0

    # --- control ---
    def start(self,
              path: str,
              *,
              max_seconds: Optional[float] = None,
              max_frames:  Optional[int]   = None,
              max_bytes:   Optional[int]   = None) -> None:
        if self.active:
            raise RuntimeError("LogController already active")

        self._lock.acquire(nonblocking=True)  # fail fast if another process logs
        self._lock_held = True

        self._writer = CsvLogWriter(path, self._channels)
        self._last_path = path
        self._frames_written = 0

        self._max_seconds = max_seconds if (max_seconds is None or max_seconds > 0) else None
        self._max_frames  = max_frames  if (max_frames  is None or max_frames  > 0) else None
        self._max_bytes   = max_bytes   if (max_bytes   is None or max_bytes   > 0) else None

        self._t0_device_ms = None
        self._t0_wall_s    = time.time()
        self._stopped_reason = None

    def stop(self, reason: str = "stopped") -> None:
        if self._writer is None and not self._lock_held:
            return

        if self._writer:
            self._writer.close()
            self._writer = None

        if self._lock_held:
            try: self._lock.release()
            finally: self._lock_held = False

        if self._stopped_reason is None:
            self._stopped_reason = reason
            if self._on_stop:
                try: self._on_stop(reason)
                except Exception: pass

    # --- data path ---
    def append(self, idx: int, seq: int, ts_ms: int, values: Dict[str, int]) -> bool:
        if not self.active:
            return False

        if self._t0_device_ms is None:
            self._t0_device_ms = int(ts_ms)

        try:
            self._writer.write(idx, seq, ts_ms, values)  # type: ignore[union-attr]
            self._frames_written += 1
        except Exception:
            self.stop("error")
            return False

        # Time limit
        if self._max_seconds is not None:
            if self._t0_device_ms is not None:
                elapsed_s = max(0.0, (float(ts_ms) - float(self._t0_device_ms)) / 1000.0)
            else:
                elapsed_s = max(0.0, time.time() - (self._t0_wall_s or time.time()))
            if elapsed_s >= self._max_seconds:
                self.stop("max_seconds")
                return False

        # Frames limit
        if self._max_frames is not None and self._frames_written >= self._max_frames:
            self.stop("max_frames")
            return False

        # Bytes limit
        if self._max_bytes is not None and self.bytes_written >= self._max_bytes:
            self.stop("max_bytes")
            return False

        return True

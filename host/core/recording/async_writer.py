# host/runtime/recording/async_writer.py
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from queue import Queue, Empty
from typing import Optional, Dict, Any, Callable, List


class AsyncWriter:
    """
    Threaded, batched writer for text or CSV files.
    """

    def __init__(
        self,
        path: Path,
        write_func: Optional[Callable[[Path, List[Any]], None]] = None,
        flush_interval: float = 0.5,
        *,
        logger: Optional[logging.Logger] = None,
    ):
        self._path = path
        self._write_func = write_func
        self._flush_interval = float(flush_interval)

        self._log = logger or logging.getLogger(__name__)

        self._queue: Queue[Any] = Queue()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    # ---------------- Public API ----------------
    def write(self, item: Any) -> None:
        """Queue an item for writing (no-op after close())."""
        if self._stop_event.is_set():
            return
        self._queue.put(item)

    def set_path(self, new_path: Path) -> None:
        if new_path is None:
            raise ValueError("AsyncWriter path cannot be None")
        with self._lock:
            self._path = new_path

    def close(self) -> None:
        """Flush remaining rows and stop the writer thread."""
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        self._thread.join(timeout=None)

    # ---------------- Internal ----------------
    def _worker(self) -> None:
        batch: List[Any] = []
        last_flush = time.time()

        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                item = self._queue.get(timeout=0.1)
                batch.append(item)
            except Empty:
                pass

            now = time.time()
            if batch and (now - last_flush >= self._flush_interval or self._stop_event.is_set()):
                self._flush_safe(batch)
                batch.clear()
                last_flush = now

        if batch:
            self._flush_safe(batch)

    def _flush_safe(self, batch: List[Any]) -> None:
        """Flush with exception safety (never kill the worker thread)."""
        try:
            self._flush(batch)
        except Exception:
            # If flush fails, log once with traceback and drop this batch.
            with self._lock:
                path = self._path
            self._log.exception("ASYNC_WRITER_FLUSH_FAILED path=%s batch_len=%d", path, len(batch))

    def _flush(self, batch: List[Any]) -> None:
        """Flush batch to disk using custom write function or default."""
        if not batch:
            return

        with self._lock:
            path = self._path
            write_func = self._write_func

        if write_func is not None:
            write_func(path, batch)
            return

        # Default: CSV if .csv, else simple line-by-line text
        if path.suffix.lower() == ".csv":
            self._default_write(path, batch)  # type: ignore[arg-type]
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                for row in batch:
                    f.write(str(row) + "\n")

    @staticmethod
    def _default_write(path: Path, batch: List[Dict[str, Any]]) -> None:
        """Append batch of dicts to CSV, writing header if new file."""
        import csv

        if not batch:
            return

        new_file = not path.exists()
        fieldnames = sorted(batch[0].keys())

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if new_file:
                writer.writeheader()
            writer.writerows(batch)

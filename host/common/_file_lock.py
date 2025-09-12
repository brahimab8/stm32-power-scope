# host/common/_file_lock.py
from __future__ import annotations
from typing import Optional, TextIO
from pathlib import Path
import os, time, json, sys

class FileLock:
    """Minimal advisory lock via a lock file (POSIX flock / Windows msvcrt.locking)."""
    def __init__(self, path: Path) -> None:
        self._path = path
        self._fh: Optional[TextIO] = None

    def acquire(self, *, nonblocking: bool = True) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self._path, "a+")
        try:
            if os.name == "nt":
                import msvcrt
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK if nonblocking else msvcrt.LK_LOCK, 1)
                except OSError:
                    fh.close()
                    raise RuntimeError("another logging session is active")
            else:
                import fcntl
                flags = fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0)
                try:
                    fcntl.flock(fh.fileno(), flags)
                except OSError:
                    fh.close()
                    raise RuntimeError("another logging session is active")

            fh.seek(0); fh.truncate()
            fh.write(json.dumps({"pid": os.getpid(), "argv": sys.argv, "ts": time.time()}) + "\n")
            fh.flush()
        except Exception:
            try: fh.close()
            except Exception: pass
            raise
        self._fh = fh

    def release(self) -> None:
        fh, self._fh = self._fh, None
        if fh:
            try:
                if os.name == "nt":
                    import msvcrt; msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl; fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try: fh.close()
            except Exception: pass

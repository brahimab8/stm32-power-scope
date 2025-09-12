# host/common/logging_config.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class LogDefaults:
    max_seconds: Optional[float] = 60.0   # device-time cap; 0/None disables
    max_frames:  Optional[int]   = 0      # 0 = no cap
    max_bytes:   Optional[int]   = 0      # 0 = no cap
    filename_prefix: str = "PowerScope"
    filename_ext:    str = ".csv"
    lock_filename:   str = ".logging.lock"

DEFAULTS = LogDefaults()

def repo_host_root() -> Path:
    # <repo>/host — based on this file's location
    return Path(__file__).resolve().parents[1]

def logs_root() -> Path:
    root = repo_host_root() / "logs"
    root.mkdir(parents=True, exist_ok=True)
    return root

def make_log_path(*, suffix: str | None = None, directory: Path | None = None) -> Path:
    from datetime import datetime
    root = directory if directory else logs_root()
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base = f"{DEFAULTS.filename_prefix}_{ts}"
    if suffix:
        base += f"_{suffix}"
    return root / f"{base}{DEFAULTS.filename_ext}"

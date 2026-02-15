# host/runtime/recording/stream.py
from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Tuple

from host.core.recording.async_writer import AsyncWriter
from host.model.sensor import DecodedReading


@dataclass(frozen=True)
class StreamKey:
    sensor_runtime_id: int


def _safe_name(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_]+", "_", name.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "channel"


def _utc_compact_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class StreamRecorder:
    """
    Records decoded readings to per-sensor CSV files.

    Policy:
      - One CSV per "run" per sensor (created when first reading arrives)
      - Files live under: base_dir/sensor_<rid>/<start_ts>.csv
    """

    def __init__(self, base_dir: Path, *, flush_interval_s: float = 0.5):
        self._lock = RLock()
        self._base_dir = Path(base_dir)
        self._flush_interval_s = float(flush_interval_s)

        self._writers: Dict[StreamKey, AsyncWriter] = {}
        self._paths: Dict[StreamKey, Path] = {}
        self._fieldnames: Dict[StreamKey, List[str]] = {}

        # per-key run id (timestamp string) assigned once when file is created
        self._run_ts: Dict[StreamKey, str] = {}

        self._active = True

    def close(self) -> None:
        with self._lock:
            self._active = False
            writers = list(self._writers.values())
            self._writers.clear()
            self._paths.clear()
            self._fieldnames.clear()
            self._run_ts.clear()

        for w in writers:
            w.close()

    def on_reading(self, runtime_id: int, reading: DecodedReading) -> None:
        key = StreamKey(int(runtime_id))

        with self._lock:
            if not self._active:
                return

            writer = self._writers.get(key)
            if writer is None:
                path = self._get_path(key)
                writer = AsyncWriter(
                    path=path,
                    flush_interval=self._flush_interval_s,
                    write_func=self._write_batch,
                )
                self._writers[key] = writer

            fieldnames = self._fieldnames.get(key)
            if fieldnames is None:
                fieldnames = self._build_fieldnames(reading)
                self._fieldnames[key] = fieldnames

        row = self._build_row(fieldnames, reading)
        writer.write((fieldnames, row))

    def _get_path(self, key: StreamKey) -> Path:
        # one file per key per run
        if key in self._paths:
            return self._paths[key]

        run_ts = self._run_ts.get(key)
        if run_ts is None:
            run_ts = _utc_compact_ts()
            self._run_ts[key] = run_ts

        folder = self._base_dir / f"sensor_{key.sensor_runtime_id}"
        folder.mkdir(parents=True, exist_ok=True)

        path = folder / f"{run_ts}.csv"
        self._paths[key] = path
        return path

    @staticmethod
    def _build_fieldnames(reading: DecodedReading) -> List[str]:
        channels = reading.all
        cids = sorted(channels.keys())

        fieldnames = ["timestamp", "unix_ns", "source", "stream_seq"]
        for cid in cids:
            ch = channels[cid]
            safe = _safe_name(ch.name)
            fieldnames.append(f"{cid}_{safe}")
        return fieldnames

    @staticmethod
    def _build_row(fieldnames: List[str], reading: DecodedReading) -> Dict[str, Any]:
        ts = datetime.now(timezone.utc).isoformat()
        ns = time.time_ns()

        source = getattr(reading, "source", "stream")
        if source == "read_sensor" and getattr(reading, "cmd_seq", None) is not None:
            source = f"READ_SENSOR (cmd_seq:{reading.cmd_seq})"

        row: Dict[str, Any] = {
            "timestamp": ts,
            "unix_ns": ns,
            "source": source,
            "stream_seq": getattr(reading, "stream_seq", None),
        }

        channels = reading.all
        for k in fieldnames:
            if k in ("timestamp", "unix_ns", "source", "stream_seq"):
                continue
            cid = int(k.split("_", 1)[0])
            ch = channels.get(cid)
            row[k] = ch.value if (ch is not None and ch.value is not None) else (ch.raw if ch is not None else None)

        return row

    @staticmethod
    def _write_batch(path: Path, batch: List[Tuple[List[str], Dict[str, Any]]]) -> None:
        if not batch:
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not path.exists()
        fieldnames = batch[0][0]

        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            if new_file:
                w.writeheader()
            for _, row in batch:
                w.writerow(row)

    def get_stream_path_for(self, sensor_runtime_id: int) -> Path:
        key = StreamKey(int(sensor_runtime_id))
        return self._get_path(key)

    def build_schema_from_reading(self, *, sensor_runtime_id: int, reading: DecodedReading) -> Dict[str, Any]:
        key = StreamKey(int(sensor_runtime_id))
        with self._lock:
            run_ts = self._run_ts.get(key)

        channels = reading.all
        return {
            "sensor_runtime_id": int(sensor_runtime_id),
            "sensor_type_id": int(reading.sensor_type_id),
            "sensor_name": reading.sensor_name,
            "run_started_at_utc": run_ts,
            "channels": [
                {
                    "id": int(cid),
                    "name": ch.name,
                    "unit": ch.unit,
                    "is_measured": bool(ch.is_measured),
                }
                for cid, ch in sorted(channels.items(), key=lambda kv: kv[0])
            ],
        }

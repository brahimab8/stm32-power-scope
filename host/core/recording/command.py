# host/runtime/recording/command.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from host.interfaces.command_sink import CommandEvent, CommandSink
from host.core.recording.async_writer import AsyncWriter


@dataclass
class CommandTraceLogger(CommandSink):
    logger: logging.Logger
    file_path: Optional[Path] = None
    flush_interval_s: float = 0.5

    def __post_init__(self) -> None:
        self._writer: Optional[AsyncWriter] = None
        if self.file_path is not None:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._writer = AsyncWriter(
                path=self.file_path,
                flush_interval=self.flush_interval_s,
                write_func=self._write_batch,
                logger=self.logger,
            )

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    def on_command(self, event: CommandEvent) -> None:
        if self._writer is None:
            return

        ts_utc = event.ts_utc or datetime.now(timezone.utc).isoformat()

        out = {
            "name": event.name,
            "kind": event.kind,
            "request_id": event.request_id,
            "payload": event.payload,
            "ts_utc": ts_utc,
        }

        out = {k: v for k, v in out.items() if v is not None}

        self._writer.write(json.dumps(out, ensure_ascii=False))

    @staticmethod
    def _write_batch(path: Path, batch: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for line in batch:
                f.write(line + "\n")

# host/app/sinks.py
from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

from host.interfaces.reading_sink import ReadingSink
from host.model import DecodedReading
from host.core.recording.stream import StreamRecorder
from host.app.session_index import (
    upsert_sensor_schema,
    append_sensor_stream_file,
)


class StreamRecordingSink(ReadingSink):
    """
    Records readings to CSV via StreamRecorder and updates session.json:

    - Writes one CSV per run per sensor
    - Updates per-sensor schema and stream file list in session.json
    """

    def __init__(
        self,
        *,
        recorder: StreamRecorder,
        session_json_path: Path,
        workspace_root: Path,
    ):
        self._recorder = recorder
        self._session_json_path = Path(session_json_path)
        self._workspace_root = Path(workspace_root)

        self._log = logging.getLogger(__name__)
        self._seen_paths: set[str] = set()
        self._lock = Lock()

    def on_reading(self, runtime_id: int, reading: DecodedReading) -> None:
        runtime_id = int(runtime_id)

        # Ensure path/run_ts exists for this stream (one file per run per sensor)
        csv_path = self._recorder.get_stream_path_for(runtime_id)

        try:
            rel_path = csv_path.relative_to(self._workspace_root).as_posix()
        except Exception:
            rel_path = csv_path.as_posix()

        with self._lock:
            first_time = rel_path not in self._seen_paths
            if first_time:
                self._seen_paths.add(rel_path)

        if first_time:
            try:
                schema = self._recorder.build_schema_from_reading(
                    sensor_runtime_id=runtime_id,
                    reading=reading,
                )

                # schema per sensor (only if changed)
                upsert_sensor_schema(
                    self._session_json_path,
                    sensor_runtime_id=runtime_id,
                    schema=schema,
                )

                # append the stream file path for this sensor run
                append_sensor_stream_file(
                    self._session_json_path,
                    sensor_runtime_id=runtime_id,
                    csv_rel_path=rel_path,
                )


            except Exception:
                self._log.exception("SESSION_MANIFEST_UPDATE_FAILED path=%s", rel_path)

        # Always record
        self._recorder.on_reading(runtime_id, reading)

    def register_pre_created_stream(
        self,
        runtime_id: int,
        *,
        sensor_type_id: int,
        sensor_name: str,
        channels: list[dict],
    ) -> None:
        """
        Called after ensure_stream_file to register the pre-created CSV
        in session.json — schema and stream file path — without needing a reading.
        """
        runtime_id = int(runtime_id)
        csv_path = self._recorder.get_stream_path_for(runtime_id)

        try:
            rel_path = csv_path.relative_to(self._workspace_root).as_posix()
        except Exception:
            rel_path = csv_path.as_posix()

        with self._lock:
            if rel_path in self._seen_paths:
                return
            self._seen_paths.add(rel_path)

        try:
            schema = {
                "sensor_runtime_id": runtime_id,
                "sensor_type_id": sensor_type_id,
                "sensor_name": sensor_name,
                "channels": channels,
            }
            upsert_sensor_schema(
                self._session_json_path,
                sensor_runtime_id=runtime_id,
                schema=schema,
            )
            append_sensor_stream_file(
                self._session_json_path,
                sensor_runtime_id=runtime_id,
                csv_rel_path=rel_path,
            )
        except Exception:
            self._log.exception("SESSION_MANIFEST_PRECREATE_FAILED path=%s", rel_path)
        
    def close(self) -> None:
        self._recorder.close()

# host/app/runner.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

from host.core.context import Context
from host.core.errors import PowerScopeError
from host.core.session_store import SessionPaths, create_session_dir, find_latest_matching_session
from host.core.session_identity import (
    transport_fingerprint,
    context_identity_with_board_uid,
    normalize_startup_sensors,
    session_matches,
)
from host.transport.factory import DeviceTransport
from host.runtime.device_link import DeviceLink
from host.core.recording.command import CommandTraceLogger
from host.core.recording.stream import StreamRecorder
from host.interfaces.command_sink import CommandSink
from host.interfaces.reading_sink import ReadingSink
from host.app.controller import PowerScopeController
from host.app.config import PowerScopeConfig
from host.app.sinks import StreamRecordingSink
from host.protocol.core.frames import StreamFrame


@dataclass(frozen=True)
class AppRun:
    controller: PowerScopeController
    context: Context
    device_transport: DeviceTransport
    session: SessionPaths
    cmd_sink: CommandSink
    recorder: StreamRecorder


def close_run(run: AppRun) -> None:
    try:
        run.controller.stop()
    except Exception:
        pass
    try:
        run.recorder.close()
    except Exception:
        pass
    try:
        run.cmd_sink.close()
    except Exception:
        pass


def ensure_session(
    *,
    sessions_base_dir: Path,
    prefix: str,
    context: Context,
    device_transport: DeviceTransport,
    board_uid_hex: str | None,
    startup_sensors: list[dict[str, int]] | None,
    initial_sensor_schemas: dict[str, dict[str, object]] | None,
) -> SessionPaths:
    identity = context_identity_with_board_uid(
        context,
        board_uid_hex=board_uid_hex,
        startup_sensors=startup_sensors,
    )
    tfp = transport_fingerprint(device_transport)
    existing_session_dir = find_latest_matching_session(
        sessions_base_dir,
        identity=identity,
        transport=tfp,
        prefix=prefix,
    )

    if existing_session_dir is not None:
        root = Path(existing_session_dir)
        sj = root / "session.json"
        if root.exists() and sj.exists() and session_matches(sj, identity=identity, transport_fp=tfp):
            sp = SessionPaths(
                root=root,
                commands_jsonl=root / "commands.jsonl",
                streams_dir=root / "streams",
                session_json=sj,
            )
            sp.streams_dir.mkdir(parents=True, exist_ok=True)
            return sp

    return create_session_dir(
        sessions_base_dir,
        identity=identity,
        transport=tfp,
        startup_sensors=startup_sensors,
        initial_sensor_schemas=initial_sensor_schemas,
        prefix=prefix,
    )


def _build_initial_sensor_schemas(
    *,
    context: Context,
    startup_sensors: list[dict[str, int]] | None,
) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}

    for item in startup_sensors or []:
        try:
            runtime_id = int(item["runtime_id"])
            type_id = int(item["type_id"])
        except Exception:
            continue

        sensor_meta = context.sensors.get(type_id)
        sensor_name = sensor_meta.name if sensor_meta is not None else f"type_id={type_id}"
        channels: list[dict[str, object]] = []

        if sensor_meta is not None:
            channels = [
                {
                    "id": int(ch.channel_id),
                    "name": ch.name,
                    "unit": ch.display_unit,
                    "is_measured": bool(ch.is_measured),
                }
                for ch in sorted(sensor_meta.channels, key=lambda c: int(c.channel_id))
            ]

        out[str(runtime_id)] = {
            "sensor_runtime_id": runtime_id,
            "sensor_type_id": type_id,
            "sensor_name": sensor_name,
            "channels": channels,
            "stream_files": [],
        }

    return out


def _probe_board_startup_identity(
    *,
    context: Context,
    device_transport: DeviceTransport,
    cmd_timeout_s: float,
    logger: logging.Logger,
) -> tuple[str | None, list[dict[str, int]], list[StreamFrame]]:
    buffered_frames: list[StreamFrame] = []

    link = DeviceLink(
        proto=context.protocol,
        transport=device_transport.transport,
        cmd_timeout_s=float(cmd_timeout_s),
        logger=logger,
        on_stream=buffered_frames.append,
    )

    try:
        link.start()
        uid = link.client.get_board_uid_hex()
        sensors = link.client.get_sensors()
        startup_sensors = normalize_startup_sensors(
            {"runtime_id": s.runtime_id, "type_id": s.type_id} for s in sensors
        )
        return str(uid).lower(), startup_sensors, buffered_frames
    except Exception as e:
        logger.warning("BOARD_STARTUP_PROBE_FAILED err=%s", e)
        return None, [], buffered_frames
    finally:
        try:
            link.stop()
        except Exception:
            pass


def start_run(
    cfg: PowerScopeConfig,
    *,
    sessions_base_dir: Path,
    prefix: str = "session",
    context: Context | None = None,
    extra_sinks: list[ReadingSink] | None = None,
) -> AppRun:
    log = logging.getLogger(__name__)

    context = context or Context.load(cfg.metadata_dir, cfg.protocol_dir)
    created = context.transport_factory.create(
        type_id=cfg.transport_type_id,
        overrides=dict(cfg.transport_overrides),
    )

    board_uid_hex, startup_sensors, buffered_frames = _probe_board_startup_identity(
        context=context,
        device_transport=created,
        cmd_timeout_s=cfg.cmd_timeout_s,
        logger=log,
    )

    if not board_uid_hex:
        raise PowerScopeError(
            "Unable to read board UID.",
            hint="Connect a board and retry. A session is only created after the UID is available.",
        )

    if startup_sensors is None:
        startup_sensors = []

    initial_sensor_schemas = _build_initial_sensor_schemas(
        context=context,
        startup_sensors=startup_sensors,
    )

    session = ensure_session(
        sessions_base_dir=sessions_base_dir,
        prefix=prefix,
        context=context,
        device_transport=created,
        board_uid_hex=board_uid_hex,
        startup_sensors=startup_sensors,
        initial_sensor_schemas=initial_sensor_schemas,
    )

    cmd_logger = logging.getLogger("commands")
    cmd_sink = CommandTraceLogger(
        logger=cmd_logger,
        file_path=session.commands_jsonl,
        flush_interval_s=0.5,
    )

    recorder = StreamRecorder(
        base_dir=session.streams_dir,
        flush_interval_s=0.5,
    )

    controller = PowerScopeController(
        cfg,
        cmd_sink=cmd_sink,
        context=context,
        device_transport=created,
        logger=log,
    )

    recording_sink = StreamRecordingSink(
        recorder=recorder,
        session_json_path=session.session_json,
        workspace_root=session.root,
    )
    controller.add_sink(recording_sink)
    
    # Attach any extra sinks (e.g. live_buffer from BoardManager)
    for sink in (extra_sinks or []):
        controller.add_sink(sink)

    # Start controller — transport opens, handshake runs, sensors discovered
    try:
        controller.start()
    except Exception:
        try:
            controller.stop()
        except Exception:
            pass
        try:
            recorder.close()
        except Exception:
            pass
        try:
            cmd_sink.close()
        except Exception:
            pass
        raise

    # Pre-create stream CSVs for all known sensors from catalog
    # so files exist immediately on connect, not lazily on first reading
    status = controller.status()
    for sensor in status.sensors:
        sensor_meta = context.sensors.get(sensor.type_id)
        if sensor_meta is None:
            continue
        channels = [
            {
                "id": int(ch.channel_id),
                "name": ch.name,
                "unit": ch.display_unit,       # add
                "is_measured": bool(ch.is_measured),  # add
            }
            for ch in sorted(sensor_meta.channels, key=lambda c: int(c.channel_id))
        ]
        try:
            recorder.ensure_stream_file(
                sensor_runtime_id=sensor.runtime_id,
                channels=channels,
            )
            recording_sink.register_pre_created_stream(
                sensor.runtime_id,
                sensor_type_id=sensor.type_id,
                sensor_name=sensor.name,
                channels=channels,
            )
        except Exception:
            log.warning(
                "STREAM_FILE_PRECREATE_FAILED sensor_runtime_id=%d", sensor.runtime_id
            )

    # Reconstruct timestamps for buffered frames using uptime as reference
    reconnect_wall: datetime | None = None
    current_uptime_ms: int | None = None
    if buffered_frames:
        reconnect_wall = datetime.now(timezone.utc)
        try:
            current_uptime_ms = controller.get_uptime()
        except Exception:
            log.warning("UPTIME_FETCH_FAILED_FOR_REPLAY — buffered frames will have no timestamp")

    # Replay frames captured during probe window into all attached sinks
    for frame in buffered_frames:
        capture_ts: datetime | None = None
        if reconnect_wall is not None and current_uptime_ms is not None:
            try:
                frame_uptime_ms = frame.header.ts_ms
                delta_ms = current_uptime_ms - frame_uptime_ms
                capture_ts = reconnect_wall - timedelta(milliseconds=delta_ms)
            except Exception:
                pass
        try:
            controller.replay_stream_frame(
                frame,
                capture_ts=capture_ts,
                is_buffered=True,
            )
        except Exception:
            log.warning("BUFFERED_FRAME_REPLAY_FAILED")

    return AppRun(
        controller=controller,
        context=context,
        device_transport=created,
        session=session,
        cmd_sink=cmd_sink,
        recorder=recorder,
    )
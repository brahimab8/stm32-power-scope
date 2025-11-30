# host/app/runner.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from host.core.context import Context
from host.core.session_store import SessionPaths, create_session_dir
from host.core.session_identity import (
    transport_fingerprint,
    context_identity,
    session_matches,
)
from host.transport.factory import DeviceTransport
from host.core.recording.command import CommandTraceLogger
from host.core.recording.stream import StreamRecorder
from host.interfaces.command_sink import CommandSink
from host.app.controller import PowerScopeController
from host.app.config import PowerScopeConfig


@dataclass(frozen=True)
class AppRun:
    controller: PowerScopeController
    context: Context
    device_transport: DeviceTransport
    session: SessionPaths
    cmd_sink: CommandSink
    recorder: StreamRecorder


def ensure_session(
    *,
    sessions_base_dir: Path,
    prefix: str,
    context: Context,
    device_transport: DeviceTransport,
    existing_session_dir: Optional[Path] = None,
) -> SessionPaths:
    identity = context_identity(context)
    tfp = transport_fingerprint(device_transport)

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
        prefix=prefix,
    )


def start_run(
    cfg: PowerScopeConfig,
    *,
    sessions_base_dir: Path,
    existing_session_dir: Optional[Path] = None,
    prefix: str = "session",
    context: Optional[Context] = None,
) -> AppRun:
    log = logging.getLogger(__name__)

    context = context or Context.load(cfg.metadata_dir, cfg.protocol_dir)
    created = context.transport_factory.create(
        type_id=cfg.transport_type_id,
        overrides=dict(cfg.transport_overrides),
    )

    session = ensure_session(
        sessions_base_dir=sessions_base_dir,
        prefix=prefix,
        context=context,
        device_transport=created,
        existing_session_dir=existing_session_dir,
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

    return AppRun(
        controller=controller,
        context=context,
        device_transport=created,
        session=session,
        cmd_sink=cmd_sink,
        recorder=recorder,
    )

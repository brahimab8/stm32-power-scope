from __future__ import annotations

import argparse
import logging
import signal
import threading
from pathlib import Path
from typing import Optional

from host.cli.args import METADATA_DIR, PROTOCOL_DIR, SESSIONS_BASE_DIR
from host.daemon.api import ControlApiServer
from host.daemon.manager import BoardManager


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="powerscope-daemon")
    p.add_argument("--host", default="127.0.0.1", help="Control API bind host (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8765, help="Control API port (default: 8765)")
    p.add_argument("--metadata-dir", default=METADATA_DIR)
    p.add_argument("--protocol-dir", default=PROTOCOL_DIR)
    p.add_argument("--sessions-dir", default=str(SESSIONS_BASE_DIR))
    p.add_argument("--session-prefix", default="session")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


def run(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger(__name__)

    manager = BoardManager(
        metadata_dir=args.metadata_dir,
        protocol_dir=args.protocol_dir,
        sessions_base_dir=Path(args.sessions_dir),
        session_prefix=args.session_prefix,
    )

    server = ControlApiServer((args.host, int(args.port)), manager=manager, logger=log)

    stop_event = threading.Event()
    shutdown_requested = threading.Event()

    def _request_server_shutdown() -> None:
        if shutdown_requested.is_set():
            return
        shutdown_requested.set()

        def _worker() -> None:
            try:
                server.shutdown()
            except Exception:
                log.exception("DAEMON_SERVER_SHUTDOWN_FAILED")

        threading.Thread(target=_worker, name="daemon-server-shutdown", daemon=True).start()

    def _shutdown() -> None:
        if stop_event.is_set():
            return
        stop_event.set()
        log.info("DAEMON_SHUTDOWN")
        _request_server_shutdown()

    def _signal_handler(_sig, _frame) -> None:
        _shutdown()

    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            signal.signal(sig, _signal_handler)

    log.info("DAEMON_STARTED host=%s port=%d", args.host, int(args.port))

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        _shutdown()
    finally:
        try:
            server.server_close()
        except Exception:
            log.exception("DAEMON_SERVER_CLOSE_FAILED")
        manager.shutdown_all()
        log.info("DAEMON_STOPPED")

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    return run(argv)

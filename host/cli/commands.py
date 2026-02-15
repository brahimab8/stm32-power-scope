# host/cli/commands.py
from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Lock
from typing import Mapping, Any

from host.app.config import PowerScopeConfig
from host.app.runner import start_run, AppRun
from host.app.sinks import StreamRecordingSink
from host.app.transport_index import TransportIndex
from host.core.session_store import find_latest_session
from host.interfaces import ReadingSink

from host.cli.args import METADATA_DIR, PROTOCOL_DIR, SESSIONS_BASE_DIR, is_effectively_required


# ---------------- Sensor-stream sink ----------------

class PrintReadingSink(ReadingSink):
    """Print decoded readings to stdout."""

    # Fixed widths for alignment
    NAME_WIDTH = 8
    VALUE_WIDTH = 9
    UNIT_WIDTH = 3

    def __init__(self, *, include_raw: bool = True):
        self._include_raw = include_raw

    def on_reading(self, runtime_id: int, reading) -> None:
        d = reading.as_dict()  # full dict

        sensor_name = d.get("sensor_name", f"id={runtime_id}")

        measured = d.get("measured", {})
        computed = d.get("computed", {})

        # Start line with runtime ID and sensor name
        line = f"{runtime_id:<3} {sensor_name} | "

        # Add measured channels
        parts = []
        for ch in measured.values():
            name = ch["name"][:self.NAME_WIDTH].ljust(self.NAME_WIDTH)
            value = f"{ch['value']:.2f}".rjust(self.VALUE_WIDTH)
            unit = ch["unit"][:self.UNIT_WIDTH].ljust(self.UNIT_WIDTH)
            parts.append(f"{name}={value}{unit}")

        # Add computed channels
        for ch in computed.values():
            name = ch["name"][:self.NAME_WIDTH].ljust(self.NAME_WIDTH)
            value = f"{ch['value']:.5f}".rjust(self.VALUE_WIDTH)
            unit = ch["unit"][:self.UNIT_WIDTH].ljust(self.UNIT_WIDTH)
            parts.append(f"{name}={value}{unit}")

        # Join all columns with separator
        line += " | ".join(parts)
        print(line)

    def close(self) -> None:
        return None

# ---------------- Logging ----------------

def configure_file_logging(app_log_path: Path) -> None:
    """
    Add a file handler to the root logger (idempotent).
    Kept in CLI (presentation-layer concern).
    """
    root = logging.getLogger()
    app_log_path.parent.mkdir(parents=True, exist_ok=True)
    target = str(app_log_path.resolve())

    for h in root.handlers:
        if isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == target:
            return

    fh = logging.FileHandler(app_log_path, encoding="utf-8", delay=True)
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(fh)

    if root.level > logging.INFO:
        root.setLevel(logging.INFO)

# ---------------- Status printing ----------------

def print_status(st) -> None:
    t = st.transport
    m = st.mcu
    print(f"Transport: connected={t.connected} driver={t.driver} key={t.key_param_value or '-'}")
    print(f"MCU:       available={m.available}")
    if m.last_error:
        print(f"MCU err:   {m.last_error}")
    if t.last_error:
        print(f"TX err:    {t.last_error}")

    if not st.sensors:
        print("Sensors:   (none)")
        return

    print("Sensors:")
    for s in st.sensors:
        stream = "ON" if s.streaming else "off"
        per = s.period_ms if s.period_ms is not None else "-"
        err = f" err={s.last_error}" if s.last_error else ""
        print(f"  - id={s.runtime_id} type={s.type_id} name={s.name} stream={stream} period_ms={per}{err}")

# ---------------- Commands ----------------

def cmd_transports(*, tindex: TransportIndex) -> int:
    catalog = tindex.catalog()

    print("Available transports:\n")
    print("Usage:")
    print("  powerscope <status|sensors|stream> --transport <label> --<key> <value> [--<param> <value> ...]\n")

    first = next(iter(sorted(catalog.keys())), None)
    if first is not None:
        t0 = catalog[first]
        key0 = getattr(t0, "key_param", None) or "<key>"
        print("Example:")
        print(f"  powerscope status --transport {t0.label} --{key0} <value>\n")

    for type_id in sorted(catalog.keys()):
        t = catalog[type_id]
        key = getattr(t, "key_param", None)
        params: Mapping[str, Mapping[str, Any]] = getattr(t, "params", {}) or {}

        print(f"{t.label} (id={type_id}, driver={t.driver})")
        if key:
            print(f"  key: {key}")

        others = [n for n in params.keys() if n != key]
        if others:
            opts = []
            for name in others:
                spec = params[name]
                if "default" in spec:
                    opts.append(f"{name}={spec['default']!r}")
                elif is_effectively_required(spec):
                    opts.append(f"{name}=<required>")
                else:
                    opts.append(f"{name}=<optional>")
            print("  options: " + ", ".join(opts))
        print()

    return 0


def _start_app_run(
    *,
    transport_type_id: int,
    transport_overrides: dict,
    reuse_latest_session: bool,
) -> AppRun:
    cfg = PowerScopeConfig(
        metadata_dir=METADATA_DIR,
        protocol_dir=PROTOCOL_DIR,
        transport_type_id=int(transport_type_id),
        transport_overrides=dict(transport_overrides),
    )

    existing = find_latest_session(SESSIONS_BASE_DIR) if reuse_latest_session else None

    run = start_run(
        cfg,
        sessions_base_dir=SESSIONS_BASE_DIR,
        existing_session_dir=existing,
        prefix="session",
    )

    configure_file_logging(run.session.root / "app.log")
    return run


def cmd_status(*, transport_type_id: int, transport_overrides: dict) -> int:
    run = _start_app_run(
        transport_type_id=transport_type_id,
        transport_overrides=transport_overrides,
        reuse_latest_session=True,
    )
    try:
        with run.controller:
            print_status(run.controller.status())
        return 0
    finally:
        _close_run(run)


def cmd_sensors(*, transport_type_id: int, transport_overrides: dict, args=None) -> int:
    run = _start_app_run(
        transport_type_id=transport_type_id,
        transport_overrides=transport_overrides,
        reuse_latest_session=True,
    )
    try:
        with run.controller:
            # Print MCU and sensors
            st = run.controller.status()
            print(
                f"MCU: available={st.mcu.available}"
                + (f" err={st.mcu.last_error}" if st.mcu.last_error else "")
            )
            print("Sensors:")
            for s in st.sensors:
                print(f"runtime_id={s.runtime_id} type_id={s.type_id} name={s.name}")

            # --- ONE-SHOT READ ---
            if args and getattr(args, "read", None):
                print("\nOne-shot sensor readings:")

                # Attach sinks
                print_sink = PrintReadingSink()
                run.controller.add_sink(print_sink)

                record_sink = None
                if getattr(args, "record", False):
                    record_sink = StreamRecordingSink(
                        recorder=run.recorder,
                        session_json_path=run.session.session_json,
                        workspace_root=run.session.root,
                    )
                    run.controller.add_sink(record_sink)
                    print(f"Recording one-shot reading to: {run.session.streams_dir}")

                # Read sensors
                for rid in args.read:
                    reading = run.controller.read_sensor(rid)
                    if reading is None:
                        sensor_state = next((s for s in run.controller.status().sensors if s.runtime_id == rid), None)
                        last_error = sensor_state.last_error if sensor_state else "(unknown)"
                        print(f"Sensor {rid} read failed: {last_error}")

                # Remove temporary sinks
                run.controller.remove_sink(print_sink)
                if record_sink:
                    run.controller.remove_sink(record_sink)
            # ----------------------

        return 0
    finally:
        _close_run(run)


def cmd_stream(args, *, transport_type_id: int, transport_overrides: dict) -> int:
    run = _start_app_run(
        transport_type_id=transport_type_id,
        transport_overrides=transport_overrides,
        reuse_latest_session=True,
    )

    try:
        with run.controller:
            st = run.controller.status()
            print(f"Session:   {run.session.root}")
            print(f"Transport: {st.transport.driver} {st.transport.key_param_value or ''}".rstrip())
            print(
                f"MCU:       available={st.mcu.available} "
                f"last_seen_s={st.mcu.last_seen_s if st.mcu.last_seen_s is not None else '-'}"
            )
            if st.mcu.last_error:
                print(f"MCU err:   {st.mcu.last_error}")
            print(f"Sensors:   {[s.runtime_id for s in st.sensors]}")

            sensor_ids = [s.runtime_id for s in st.sensors] if not args.sensor else [int(x) for x in args.sensor]
            if not sensor_ids:
                print("No sensors reported by device.")
                return 0

            run.controller.add_sink(PrintReadingSink())

            if args.record:
                run.controller.add_sink(
                    StreamRecordingSink(
                        recorder=run.recorder,
                        session_json_path=run.session.session_json,
                        workspace_root=run.session.root,
                    )
                )
                print(f"Recording: {run.session.streams_dir}")

            for rid in sensor_ids:
                run.controller.set_period(rid, period_ms=args.period_ms)

            for rid in sensor_ids:
                run.controller.start_stream(rid)
                print(f"START_STREAM: sensor_id={rid} period_ms={args.period_ms}")

            t0 = time.time()
            while args.secs is None or time.time() - t0 < args.secs:
                time.sleep(0.2)

            for rid in reversed(sensor_ids):
                run.controller.stop_stream(rid)
                print("STOP_STREAM:", rid)

            drain_s = max(0.0, float(args.drain_ms) / 1000.0)
            if drain_s > 0:
                print(f"Waiting {drain_s:.3f}s for buffered readings...")
                time.sleep(drain_s)

            return 0
    finally:
        _close_run(run)


# Helper function to close a run
def _close_run(run) -> None:
    try:
        run.recorder.close()
    except Exception:
        pass
    try:
        run.cmd_sink.close()
    except Exception:
        pass

from __future__ import annotations

import re
import time
from typing import Any

from host.clients.sdk import DaemonApiClient


def _print_json_like(value: Any) -> None:
    import json

    print(json.dumps(value, ensure_ascii=False, indent=2))


_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+)$")


def _coerce_cli_value(value: str) -> Any:
    text = str(value).strip()
    lowered = text.lower()

    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if _INT_RE.fullmatch(text):
        return int(text)
    if _FLOAT_RE.fullmatch(text):
        return float(text)
    return text


def cmd_health(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    out = client.health()
    _print_json_like(out)
    return 0


def cmd_transports(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    out = client.transports()

    transports = out.get("transports", [])
    if not transports:
        print("No transports available.")
        return 0

    print("Available transports:\n")
    for item in transports:
        print(f"- {item.get('label')} (id={item.get('type_id')}, driver={item.get('driver')})")
        params = item.get("params", {}) or {}
        for name, spec in params.items():
            t = spec.get("type", "str")
            req = bool(spec.get("required", False))
            default = spec.get("default", None)
            default_s = f"default={default}" if default is not None else ""
            req_s = "required" if req else "optional"
            suffix = f" [{req_s}{', ' + default_s if default_s else ''}]"
            print(f"    --{name}: {t}{suffix}")

    return 0


def cmd_boards_list(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    out = client.list_boards()
    boards = out.get("boards", [])
    if not boards:
        print("No boards connected.")
        return 0

    for board in boards:
        bid = board.get("board_id")
        tr = (board.get("transport") or {}).get("label")
        print(f"- {bid} transport={tr}")
    return 0


def cmd_boards_connect(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)

    overrides: dict[str, Any] = {}
    for kv in args.transport_args or []:
        key, value = kv
        overrides[str(key)] = _coerce_cli_value(value)

    out = client.connect_board(
        board_id=args.board_id,
        transport=args.transport,
        overrides=overrides,
    )
    print(f"Connected: {out.get('board_id')}")
    return 0


def cmd_boards_disconnect(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    out = client.disconnect_board(board_id=args.board_id)
    print(f"Disconnected: {out.get('board_id')}")
    return 0


def cmd_board_status(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    out = client.describe_board(board_id=args.board_id)
    _print_json_like(out)
    return 0


def cmd_board_sensors(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    out = client.refresh_sensors(board_id=args.board_id)
    sensors = out.get("sensors", [])
    if not sensors:
        print("No sensors.")
        return 0

    for sensor in sensors:
        sid = sensor.get("runtime_id")
        name = sensor.get("name")
        print(f"- [{sid}] {name}")
    return 0


def cmd_board_read(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    out = client.read_sensor(board_id=args.board_id, sensor_runtime_id=int(args.sensor))
    _print_json_like(out)
    return 0


def cmd_board_set_period(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    client.set_period(
        board_id=args.board_id,
        sensor_runtime_id=int(args.sensor),
        period_ms=int(args.period_ms),
    )
    print(f"Set period: sensor={int(args.sensor)} period_ms={int(args.period_ms)}")
    return 0


def cmd_board_get_period(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    out = client.get_period(board_id=args.board_id, sensor_runtime_id=int(args.sensor))
    period_ms = int(out.get("period_ms", 0))
    print(f"period_ms={period_ms}")
    return 0


def cmd_board_start(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    client.start_stream(board_id=args.board_id, sensor_runtime_id=int(args.sensor))
    print(f"Started stream: sensor={int(args.sensor)}")
    return 0


def cmd_board_stop(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    client.stop_stream(board_id=args.board_id, sensor_runtime_id=int(args.sensor))
    print(f"Stopped stream: sensor={int(args.sensor)}")
    return 0


def cmd_board_uptime(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    out = client.uptime(board_id=args.board_id)
    uptime_ms = int(out.get("uptime_ms", 0))
    print(f"uptime_ms={uptime_ms}")
    return 0


def cmd_board_stream(args) -> int:
    client = DaemonApiClient(base_url=args.daemon_url)
    board_id = str(args.board_id)
    sensor_id = int(args.sensor)
    duration_s = max(0.1, float(args.duration))
    poll_s = max(0.05, float(args.poll_ms) / 1000.0)

    client.start_stream(board_id=board_id, sensor_runtime_id=sensor_id)
    print(f"Streaming board={board_id} sensor={sensor_id} for {duration_s:.2f}s")

    deadline = time.time() + duration_s
    try:
        while time.time() < deadline:
            out = client.drain_readings(board_id=board_id, sensor_runtime_id=sensor_id, limit=200)
            items = out.get("items", [])
            for item in items:
                reading = item.get("reading") or {}
                measured = reading.get("measured") or {}
                computed = reading.get("computed") or {}

                parts: list[str] = []
                for _, ch in measured.items():
                    parts.append(f"{ch.get('name')}={ch.get('value')} {ch.get('unit')}")
                for _, ch in computed.items():
                    parts.append(f"{ch.get('name')}={ch.get('value')} {ch.get('unit')}")

                prefix = str(item.get("ts_utc") or "")
                if parts:
                    print(f"{prefix} | " + " | ".join(parts))
                else:
                    print(f"{prefix} | (no channels)")
            time.sleep(poll_s)
    finally:
        try:
            client.stop_stream(board_id=board_id, sensor_runtime_id=sensor_id)
            print("Stream stopped")
        except Exception as e:
            print(f"WARN: failed to stop stream cleanly: {e}")

    return 0

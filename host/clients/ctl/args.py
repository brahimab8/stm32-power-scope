from __future__ import annotations

import argparse

from host.clients.period_presets import SENSOR_PERIOD_OPTIONS_MS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="powerscope-ctl")
    parser.add_argument("--daemon-url", default="http://127.0.0.1:8765")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health")
    sub.add_parser("transports")

    boards = sub.add_parser("boards")
    boards_sub = boards.add_subparsers(dest="boards_cmd", required=True)
    boards_sub.add_parser("list")

    connect = boards_sub.add_parser("connect")
    connect.add_argument("--transport", required=True)
    connect.add_argument(
        "--transport-arg",
        action="append",
        nargs=2,
        metavar=("KEY", "VALUE"),
        dest="transport_args",
    )

    disconnect = boards_sub.add_parser("disconnect")
    disconnect.add_argument("--board-id", required=True)

    board = sub.add_parser("board")
    board.add_argument("board_id")
    board_sub = board.add_subparsers(dest="board_cmd", required=True)

    board_sub.add_parser("status")
    board_sub.add_parser("sensors")
    board_sub.add_parser("uptime")

    read = board_sub.add_parser("read")
    read.add_argument("--sensor", required=True, type=int)

    set_period = board_sub.add_parser("set-period")
    set_period.add_argument("--sensor", required=True, type=int)
    set_period.add_argument(
        "--period-ms",
        required=True,
        type=int,
        choices=[int(v) for v in SENSOR_PERIOD_OPTIONS_MS],
        help=f"Sensor period in ms. Allowed: {', '.join(str(v) for v in SENSOR_PERIOD_OPTIONS_MS)}",
    )

    get_period = board_sub.add_parser("get-period")
    get_period.add_argument("--sensor", required=True, type=int)

    start = board_sub.add_parser("start")
    start.add_argument("--sensor", required=True, type=int)

    stop = board_sub.add_parser("stop")
    stop.add_argument("--sensor", required=True, type=int)

    stream = board_sub.add_parser("stream")
    stream.add_argument("--sensor", required=True, type=int)
    stream.add_argument("--duration", type=float, default=5.0)
    stream.add_argument("--poll-ms", type=int, default=250)

    return parser

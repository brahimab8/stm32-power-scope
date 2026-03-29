from __future__ import annotations

from typing import Optional

from host.core.errors import PowerScopeError

from .args import build_parser
from .commands import (
    cmd_board_get_period,
    cmd_board_read,
    cmd_board_sensors,
    cmd_board_set_period,
    cmd_board_start,
    cmd_board_status,
    cmd_board_stop,
    cmd_board_stream,
    cmd_board_uptime,
    cmd_boards_connect,
    cmd_boards_disconnect,
    cmd_boards_list,
    cmd_health,
    cmd_transports,
)


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.cmd == "health":
            return cmd_health(args)

        if args.cmd == "transports":
            return cmd_transports(args)

        if args.cmd == "boards":
            if args.boards_cmd == "list":
                return cmd_boards_list(args)
            if args.boards_cmd == "connect":
                return cmd_boards_connect(args)
            if args.boards_cmd == "disconnect":
                return cmd_boards_disconnect(args)
            return 2

        if args.cmd == "board":
            if args.board_cmd == "status":
                return cmd_board_status(args)
            if args.board_cmd == "sensors":
                return cmd_board_sensors(args)
            if args.board_cmd == "read":
                return cmd_board_read(args)
            if args.board_cmd == "set-period":
                return cmd_board_set_period(args)
            if args.board_cmd == "get-period":
                return cmd_board_get_period(args)
            if args.board_cmd == "start":
                return cmd_board_start(args)
            if args.board_cmd == "stop":
                return cmd_board_stop(args)
            if args.board_cmd == "stream":
                return cmd_board_stream(args)
            if args.board_cmd == "uptime":
                return cmd_board_uptime(args)
            return 2

        return 2
    except PowerScopeError as e:
        print(f"ERROR: {e.message}")
        if e.hint:
            print(f"Hint: {e.hint}")
        return 1

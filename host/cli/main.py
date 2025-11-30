# host/cli/main.py
from __future__ import annotations

from typing import Optional

from host.core.errors import PowerScopeError

from host.cli.args import parse_args
from host.cli.commands import (
    cmd_transports,
    cmd_status,
    cmd_sensors,
    cmd_stream,
)


def main(argv: Optional[list[str]] = None) -> int:
    try:
        args, tindex, transport_type_id, overrides = parse_args(argv)

        if args.cmd == "transports":
            assert tindex is not None
            return cmd_transports(tindex=tindex)

        assert transport_type_id is not None

        if args.cmd == "status":
            return cmd_status(transport_type_id=transport_type_id, transport_overrides=overrides)
        if args.cmd == "sensors":
            return cmd_sensors(transport_type_id=transport_type_id, transport_overrides=overrides)
        if args.cmd == "stream":
            return cmd_stream(args, transport_type_id=transport_type_id, transport_overrides=overrides)

        return 2
    except PowerScopeError as e:
        print(f"ERROR: {e.message}")
        if e.hint:
            print(f"Hint: {e.hint}")
        return 1

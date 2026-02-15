# host/cli/args.py
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

from host.app.transport_index import TransportIndex


METADATA_DIR = "host/metadata"
PROTOCOL_DIR = "host/metadata/protocol"
SESSIONS_BASE_DIR = Path("data") / "sessions"


# ---------------- transport helpers (CLI-local) ----------------

def cast_type_name(type_name: Any):
    """
    Cast argparse values based on metadata schema type strings.

    NOTE: This only affects CLI parsing. The transport param resolver in the
    transport layer should still validate/cast strictly.
    """
    if type_name == "str":
        return str
    if type_name == "int":
        return int
    if type_name == "float":
        return float
    if type_name == "bool":

        def _to_bool(v: str) -> bool:
            s = str(v).strip().lower()
            if s in ("1", "true"):
                return True
            if s in ("0", "false"):
                return False
            raise argparse.ArgumentTypeError(f"Invalid bool literal '{v}' (use true/false)")

        return _to_bool

    return str


def is_effectively_required(spec: Mapping[str, Any]) -> bool:
    if "default" in spec:
        return False
    return bool(spec.get("required", False))


# ---------------- argparse (two-stage) ----------------

def build_base_parser() -> argparse.ArgumentParser:
    """
    Stage 1 parser: parse only command + --transport + app-level args.
    Transport params are NOT declared here.
    """
    parser = argparse.ArgumentParser(prog="powerscope")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("transports")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--transport", required=True, help="Transport label (see: powerscope transports).")

    sub.add_parser("status", parents=[common])
    p_sensors = sub.add_parser("sensors", parents=[common])
    p_sensors.add_argument(
        "--read",
        type=int,
        nargs="+",
        help="Read one-shot values from given sensor runtime_id(s)"
    )

    ps = sub.add_parser("stream", parents=[common])
    ps.add_argument("--sensor", type=int, nargs="+", default=None)
    ps.add_argument("--period-ms", type=int, default=1000)
    ps.add_argument("--secs", type=float, default=None)
    ps.add_argument("--record", action="store_true")
    ps.add_argument(
        "--drain-ms",
        type=int,
        default=500,
        help="Post-stop drain time in ms to flush buffered readings (0 = disable).",
    )

    return parser


def build_full_parser_for(*, tindex: TransportIndex, transport_type_id: int) -> argparse.ArgumentParser:
    """
    Stage 2 parser: includes dynamic transport param flags based on metadata.
    """
    meta = tindex.meta_for_type_id(transport_type_id)
    params: Mapping[str, Mapping[str, Any]] = getattr(meta, "params", {}) or {}
    key_param = getattr(meta, "key_param", None)

    parser = argparse.ArgumentParser(prog="powerscope")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("transports")

    def add_transport_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--transport", required=True)

        # key param first
        if key_param and key_param in params:
            spec = params[key_param]
            p.add_argument(
                f"--{key_param}",
                required=is_effectively_required(spec),
                default=spec.get("default", None),
                type=cast_type_name(spec.get("type")),
                help=f"Transport key param for '{meta.label}'.",
            )

        # then the rest
        for name, spec in params.items():
            if name == key_param:
                continue
            p.add_argument(
                f"--{name}",
                required=is_effectively_required(spec),
                default=spec.get("default", None),
                type=cast_type_name(spec.get("type")),
                help=f"Transport param for '{meta.label}'.",
            )

    p_status = sub.add_parser("status")
    add_transport_flags(p_status)

    p_sensors = sub.add_parser("sensors")
    add_transport_flags(p_sensors)
    p_sensors.add_argument(
    "--read",
    type=int,
    nargs="+",
    help="Read one-shot values from given sensor runtime_id(s)"
    )

    p_stream = sub.add_parser("stream")
    add_transport_flags(p_stream)
    p_stream.add_argument("--sensor", type=int, nargs="*", default=None)
    p_stream.add_argument("--period-ms", type=int, default=1000)
    p_stream.add_argument("--secs", type=float, default=None)
    p_stream.add_argument("--record", action="store_true")
    p_stream.add_argument("--drain-ms", type=int, default=500)

    return parser


def parse_args(
    argv: Optional[list[str]] = None,
) -> Tuple[argparse.Namespace, Optional[TransportIndex], Optional[int], dict]:
    """
    Returns: (args, tindex, transport_type_id, overrides)

    - tindex is always present for 'transports'
    - transport_type_id is None for 'transports'
    - overrides contains only non-None transport param values
    """
    base_parser = build_base_parser()
    base, _unknown = base_parser.parse_known_args(argv)

    # Always build a transport index for commands that need it (and to avoid re-loading)
    tindex = TransportIndex.load(metadata_dir=METADATA_DIR, protocol_dir=PROTOCOL_DIR)

    if base.cmd == "transports":
        return base, tindex, None, {}

    type_id = tindex.resolve_type_id_by_label(base.transport)

    full_parser = build_full_parser_for(
        tindex=tindex,
        transport_type_id=type_id,
    )
    args = full_parser.parse_args(argv)

    meta = tindex.meta_for_type_id(type_id)
    params = getattr(meta, "params", {}) or {}

    overrides = {
        name: getattr(args, name)
        for name in params.keys()
        if getattr(args, name, None) is not None
    }

    return args, tindex, type_id, overrides

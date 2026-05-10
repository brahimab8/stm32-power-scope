# host/clients/dash/main.py
from __future__ import annotations

import argparse
from pathlib import Path

from dash import Dash

from .callbacks import register_callbacks
from .data import transport_options
from .layout_base import make_layout
from .layout_dashboard import build_dashboard_canvas


def create_app(default_daemon_url: str = "http://127.0.0.1:8765") -> Dash:
    assets_dir = Path(__file__).with_name("assets")
    app = Dash(__name__, assets_folder=str(assets_dir))
    app.title = "PowerScope Dash"

    options = transport_options()

    initial_live = build_dashboard_canvas(
        boards=[], sensor_readings={}, dashboard_state=None
    )

    app.layout = make_layout(
        transport_options=options,
        initial_param_inputs=[],
        initial_dashboard_panel=initial_live,
        initial_history_panel=None, 
    )

    register_callbacks(app, daemon_url=default_daemon_url, transport_options=options)
    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="powerscope-dash")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--daemon-url", default="http://127.0.0.1:8765")
    parser.add_argument("--debug", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = create_app(default_daemon_url=args.daemon_url)
    app.run(host=args.host, port=int(args.port), debug=bool(args.debug))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
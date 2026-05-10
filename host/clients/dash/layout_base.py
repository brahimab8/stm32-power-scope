# host/clients/dash/layout_base.py
from __future__ import annotations

from typing import Any

from dash import dcc, html

from .theme import (
    DEFAULT_THEME,
    FONT_FAMILY,
    get_button_base_style,
    get_theme,
)


# ---------------------------------------------------------------------------
# Dashboard state helpers
# ---------------------------------------------------------------------------

def default_dashboard_state() -> dict[str, Any]:
    return {
        "containers": [
            {"id": "main", "selection": []},
        ],
    }


def normalize_dashboard_state(dashboard_state: dict[str, Any] | None) -> dict[str, Any]:
    base = default_dashboard_state()
    if not isinstance(dashboard_state, dict):
        return base

    state = dict(dashboard_state)
    containers = list(state.get("containers", []) or [])
    if not containers:
        return base

    first = next((item for item in containers if isinstance(item, dict)), None)
    if not isinstance(first, dict):
        state["containers"] = base["containers"]
        return state

    state["containers"] = [
        {
            "id": "main",
            "selection": [
                dict(item)
                for item in list(first.get("selection", []) or [])
                if isinstance(item, dict)
            ],
        }
    ]
    return state


def dashboard_channel_key(board_id: str, sensor_id: int, channel_id: int) -> str:
    return f"{board_id}:{sensor_id}:{channel_id}"


def extract_reading_channels(reading_payload: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    values_by_id: dict[int, dict[str, Any]] = {}
    if not isinstance(reading_payload, dict):
        return values_by_id

    for group_name in ("measured", "computed"):
        group = reading_payload.get(group_name) or {}
        if not isinstance(group, dict):
            continue
        for cid, item in group.items():
            if not isinstance(item, dict):
                continue
            try:
                key = int(cid)
            except Exception:
                continue
            values_by_id[key] = item
    return values_by_id


# ---------------------------------------------------------------------------
# Top-level layout shell
# ---------------------------------------------------------------------------

def make_layout(
    transport_options: list[dict[str, str]],
    initial_param_inputs: list[html.Div],
    initial_dashboard_panel: html.Div | None = None,
    initial_history_panel: html.Div | None = None,
) -> html.Div:
    """
    Build the full app layout.

    ``initial_dashboard_panel`` and ``initial_history_panel`` are rendered
    server-side so the live-plot and history containers appear in the very
    first paint — no waiting for a callback cycle.
    """
    from .layout_dashboard import build_dashboard_layout  # local to avoid circular

    c = get_theme()
    button_base = get_button_base_style()

    return html.Div(
        id="app-root",
        style={
            "fontFamily": FONT_FAMILY,
            "backgroundColor": c["bg"],
            "color": c["text_primary"],
            "minHeight": "100vh",
        },
        children=[
            html.Div(
                id="app-container",
                style={
                    "fontFamily": FONT_FAMILY,
                    "padding": "16px",
                    "maxWidth": "1800px",
                    "margin": "0 auto",
                    "backgroundColor": c["bg"],
                    "color": c["text_primary"],
                    "minHeight": "100vh",
                },
                children=[
                    # ── Header ────────────────────────────────────────────
                    html.Div(
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "alignItems": "center",
                            "marginBottom": "16px",
                        },
                        children=[
                            html.H2(
                                "PowerScope Dashboard",
                                id="header-title",
                                style={"margin": "0", "color": c["text_primary"]},
                            ),
                        ],
                    ),

                    # ── Main content (left panel + right panel) ───────────
                    html.Div(
                        id="main-layout-container",
                        children=[
                            build_dashboard_layout(
                                transport_options=transport_options,
                                initial_param_inputs=initial_param_inputs,
                                initial_dashboard_panel=initial_dashboard_panel,
                                initial_history_panel=initial_history_panel,
                            ),
                        ],
                    ),
                ],
            ),

            # ── Stores ────────────────────────────────────────────────────
            dcc.Store(id="boards-store", data=[]),
            dcc.Store(id="refresh-token", data=0),
            dcc.Store(id="sensor-readings-store", data={}),
            dcc.Store(id="channel-unit-store", data={}),
            dcc.Store(id="uptime-store", data={}),
            dcc.Store(id="dashboard-layout-store", data=default_dashboard_state()),
            dcc.Store(id="history-sessions-store", data=[]),

            # ── Intervals ─────────────────────────────────────────────────
            dcc.Interval(id="boards-interval", interval=4000, n_intervals=0),
            dcc.Interval(id="stream-interval", interval=1000, n_intervals=0),
            dcc.Interval(id="uptime-interval", interval=15000, n_intervals=0),
        ],
    )
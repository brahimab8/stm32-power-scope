# host/clients/dash/layout_history.py
from __future__ import annotations

from typing import Any

from dash import dcc, html

from .theme import (
    get_button_base_style,
    get_button_primary_style,
    get_card_style,
    get_input_style,
    get_theme,
)
from .layout_dashboard import build_plot


def build_history_panel(
    sessions_by_board: list[dict[str, Any]],
    _theme: str | None = None,
) -> html.Div:
    c = get_theme()
    card_style = get_card_style()
    button_base = get_button_base_style()
    button_primary = get_button_primary_style()
    input_style = get_input_style()

    board_options = [
        {
            "label": (
                f"Board {b['board_uid_hex'][:16]}… "
                f"({b['session_count']} session{'s' if b['session_count'] != 1 else ''})"
            ),
            "value": b["board_uid_hex"],
        }
        for b in (sessions_by_board or [])
    ]

    return html.Div(
        style={**card_style, "marginTop": "16px"},
        children=[
            # ── Header ────────────────────────────────────────────────────
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "12px",
                },
                children=[
                    html.H3(
                        "Measurement History",
                        style={"margin": "0", "color": c["text_primary"]},
                    ),
                    html.Button(
                        "↻ Refresh sessions",
                        id="history-refresh-btn",
                        style={**button_base, "fontSize": "11px", "padding": "4px 10px"},
                    ),
                ],
            ),

            # ── Selector row ──────────────────────────────────────────────
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr 2fr 1fr 1fr auto",
                    "gap": "10px",
                    "alignItems": "end",
                    "marginBottom": "12px",
                },
                children=[
                    html.Div([
                        html.Label(
                            "Board",
                            style={
                                "fontSize": "11px",
                                "fontWeight": "600",
                                "color": c["text_secondary"],
                                "marginBottom": "4px",
                                "display": "block",
                            },
                        ),
                        dcc.Dropdown(
                            id="history-board-dropdown",
                            options=board_options,
                            placeholder="Select board…",
                            clearable=False,
                            searchable=False,
                            style={**input_style, "fontSize": "12px"},
                        ),
                    ]),
                    html.Div([
                        html.Label(
                            "Session",
                            style={
                                "fontSize": "11px",
                                "fontWeight": "600",
                                "color": c["text_secondary"],
                                "marginBottom": "4px",
                                "display": "block",
                            },
                        ),
                        dcc.Dropdown(
                            id="history-session-dropdown",
                            options=[],
                            placeholder="Select session…",
                            clearable=False,
                            searchable=False,
                            style={**input_style, "fontSize": "12px"},
                        ),
                    ]),
                    html.Div([
                        html.Label(
                            "Sensor",
                            style={
                                "fontSize": "11px",
                                "fontWeight": "600",
                                "color": c["text_secondary"],
                                "marginBottom": "4px",
                                "display": "block",
                            },
                        ),
                        dcc.Dropdown(
                            id="history-sensor-dropdown",
                            options=[],
                            placeholder="Select sensor…",
                            clearable=False,
                            searchable=False,
                            style={**input_style, "fontSize": "12px"},
                        ),
                    ]),
                    html.Div([
                        html.Label(
                            "Stream file",
                            style={
                                "fontSize": "11px",
                                "fontWeight": "600",
                                "color": c["text_secondary"],
                                "marginBottom": "4px",
                                "display": "block",
                            },
                        ),
                        dcc.Dropdown(
                            id="history-stream-dropdown",
                            options=[],
                            placeholder="All files…",
                            clearable=True,
                            searchable=False,
                            style={**input_style, "fontSize": "12px"},
                        ),
                    ]),
                    html.Button(
                        "Load",
                        id="history-load-btn",
                        style={**button_primary, "alignSelf": "end", "padding": "7px 18px"},
                    ),
                ],
            ),

            # ── Status line ───────────────────────────────────────────────
            html.Div(
                id="history-status",
                style={
                    "fontSize": "11px",
                    "color": c["text_secondary"],
                    "marginBottom": "8px",
                    "minHeight": "16px",
                },
            ),

            # ── Plot area — rendered server-side so it appears on first paint
            html.Div(
                id="history-plot-container",
                style={"width": "100%"},
                children=[build_plot([], initial_plot_message="Load a stream file.")],
            ),
        ],
    )
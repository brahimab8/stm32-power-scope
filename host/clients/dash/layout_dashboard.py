# host/clients/dash/layout_dashboard.py
from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
from dash import dcc, html

from .theme import (
    get_button_primary_style,
    get_card_style,
    get_input_style,
    get_button_base_style,
    get_theme,
)
from .units import convert_metric_unit_value, display_unit_text, normalize_unit_text
from .layout_base import (
    dashboard_channel_key,
    extract_reading_channels,
    normalize_dashboard_state,
)


# ---------------------------------------------------------------------------
# Live plot
# ---------------------------------------------------------------------------

def build_plot(
    records: list[dict[str, Any]],
    _theme: str | None = None,
    initial_plot_message: str = "Start a sensor stream.",
) -> dcc.Graph:
    c = get_theme()
    fig = go.Figure()

    if records:
        trace_count = 0
        for item in records:
            x_points: list[str] = []
            y_points: list[float] = []
            for point in list(item.get("history_points", []) or []):
                if not isinstance(point, dict):
                    continue
                ts_utc = str(point.get("ts_utc", "")).strip()
                if not ts_utc:
                    continue
                try:
                    numeric_value = float(point.get("value"))
                except Exception:
                    continue
                x_points.append(ts_utc)
                y_points.append(numeric_value)
            if not x_points:
                continue

            unit_text = str(item.get("unit", "")).strip()
            unit_text_display = display_unit_text(unit_text)
            channel_label = (
                f"{item['board_label']} [{item['sensor_id']}] {item['sensor_label']}"
                f" / {item['channel_label']} ({unit_text_display})"
                if unit_text_display
                else f"{item['board_label']} [{item['sensor_id']}] {item['sensor_label']}"
                f" / {item['channel_label']}"
            )
            unit_suffix = f" {unit_text_display}" if unit_text_display else ""
            fig.add_trace(
                go.Scatter(
                    x=x_points,
                    y=y_points,
                    mode="lines+markers",
                    name=channel_label,
                    marker={"size": 6},
                    line={"width": 2},
                    hovertemplate=f"%{{y:.6g}}{unit_suffix}<br>%{{x|%H:%M:%S.%L}}<extra></extra>",
                )
            )
            trace_count += 1

        fig.update_layout(
            height=380,
            margin={"l": 20, "r": 20, "t": 96, "b": 40},
            paper_bgcolor=c["card_bg"],
            plot_bgcolor=c["card_bg"],
            font={"color": c["text_primary"]},
            xaxis={"title": "Time (UTC)", "type": "date", "tickformat": "%H:%M:%S.%L"},
            yaxis={"title": "Value"},
            showlegend=True,
            legend={
                "orientation": "h",
                "y": 1.20,
                "x": 0,
                "xanchor": "left",
                "yanchor": "bottom",
                "font": {"size": 10},
            },
            uirevision="live-plot",
        )
        if trace_count == 0:
            fig.update_layout(
                annotations=[{
                    "text": "No numeric points yet.",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"size": 13, "color": c["text_secondary"]},
                }],
                xaxis={"visible": False},
                yaxis={"visible": False},
                showlegend=False,
            )
    else:
        fig.update_layout(
            height=380,
            margin={"l": 20, "r": 20, "t": 80, "b": 20},
            paper_bgcolor=c["card_bg"],
            plot_bgcolor=c["card_bg"],
            font={"color": c["text_primary"]},
            annotations=[{
                "text": initial_plot_message,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 14, "color": c["text_secondary"]},
            }],
            xaxis={"visible": False},
            yaxis={"visible": False},
            showlegend=False,
            uirevision="live-plot",
        )

    return dcc.Graph(
        figure=fig,
        config={
            "displayModeBar": True,
            "scrollZoom": True,
            "doubleClick": "reset",
            "responsive": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
        },
        style={"width": "100%"},
    )


# ---------------------------------------------------------------------------
# Dashboard canvas (live plot container)
# ---------------------------------------------------------------------------

def build_dashboard_canvas(
    boards: list[dict[str, Any]],
    sensor_readings: dict[str, Any],
    dashboard_state: dict[str, Any] | None,
    sensor_channel_catalog: dict[int, list[dict[str, Any]]] | None = None,
    unit_overrides: dict[str, str] | None = None,
    _theme: str | None = None,
) -> html.Div:
    c = get_theme()
    state = normalize_dashboard_state(dashboard_state)
    containers = list(state.get("containers", []) or [])
    board_list = list(boards or [])

    def build_container_view(_container: dict[str, Any]) -> html.Div:
        live_records: list[dict[str, Any]] = []
        for board in board_list:
            board_id = str(board.get("board_id", ""))
            status = dict(board.get("status") or {})
            sensors = list(status.get("sensors", []) or [])
            for sensor in sensors:
                runtime_id = int(sensor.get("runtime_id", -1))
                type_id = sensor.get("type_id")
                try:
                    sensor_type_id = int(type_id)
                except Exception:
                    continue
                channel_specs = list((sensor_channel_catalog or {}).get(sensor_type_id, []))
                reading_key = f"{board_id}:{runtime_id}"
                reading_entry = sensor_readings.get(reading_key)
                reading_payload = None
                if isinstance(reading_entry, dict):
                    maybe = reading_entry.get("reading")
                    if isinstance(maybe, dict):
                        reading_payload = maybe
                values_by_id = extract_reading_channels(reading_payload)

                for spec in channel_specs:
                    cid = int(spec.get("channel_id", -1))
                    channel_name = str(spec.get("name", f"ch_{cid}"))
                    channel_unit = str(spec.get("unit", "")).strip()
                    value_item = values_by_id.get(cid, {})
                    raw_unit = normalize_unit_text(
                        str((value_item or {}).get("unit") or channel_unit or "")
                    )
                    ch_key = dashboard_channel_key(board_id, runtime_id, cid)
                    selected_unit = normalize_unit_text(
                        str((unit_overrides or {}).get(ch_key, raw_unit) or raw_unit)
                    )

                    history_points: list[dict[str, Any]] = []
                    if isinstance(reading_entry, dict):
                        for history_item in list(reading_entry.get("history", []) or []):
                            if not isinstance(history_item, dict):
                                continue
                            ts_utc = str(history_item.get("ts_utc", "")).strip()
                            if not ts_utc:
                                continue
                            channel_values = history_item.get("channel_values") or {}
                            if not isinstance(channel_values, dict):
                                continue
                            raw_history_value = channel_values.get(
                                str(cid), channel_values.get(cid)
                            )
                            converted = (
                                convert_metric_unit_value(raw_history_value, raw_unit, selected_unit)
                                if raw_unit and selected_unit
                                else raw_history_value
                            )
                            history_points.append({"ts_utc": ts_utc, "value": converted})

                    if not history_points:
                        ts_latest = (
                            str((reading_entry or {}).get("ts_utc", "")).strip()
                            if isinstance(reading_entry, dict)
                            else ""
                        )
                        latest_value = (
                            value_item.get("value") if isinstance(value_item, dict) else None
                        )
                        latest_value = (
                            convert_metric_unit_value(latest_value, raw_unit, selected_unit)
                            if raw_unit and selected_unit
                            else latest_value
                        )
                        if ts_latest:
                            history_points.append({"ts_utc": ts_latest, "value": latest_value})

                    board_label = (
                        str(board.get("board_id", board_id))
                        if isinstance(board, dict)
                        else board_id
                    )
                    sensor_label = (
                        str(sensor.get("name", f"sensor_{runtime_id}"))
                        if isinstance(sensor, dict)
                        else f"sensor_{runtime_id}"
                    )
                    live_records.append({
                        "board_id": board_id,
                        "board_label": board_label,
                        "sensor_id": runtime_id,
                        "sensor_label": sensor_label,
                        "channel_id": cid,
                        "channel_label": channel_name,
                        "unit": selected_unit or channel_unit,
                        "value": (
                            convert_metric_unit_value(value_item.get("value"), raw_unit, selected_unit)
                            if isinstance(value_item, dict) and raw_unit and selected_unit
                            else (value_item.get("value") if isinstance(value_item, dict) else None)
                        ),
                        "history_points": history_points,
                    })

        return html.Div(
            style={
                "border": f"1px solid {c['card_border']}",
                "borderRadius": "12px",
                "padding": "12px",
                "backgroundColor": c["card_bg"],
            },
            children=[
                html.H3("Live Plot", style={"margin": "0 0 6px 0", "color": c["text_primary"]}),
                html.Div(
                    "Connect a board to see live data." if not live_records else "",
                    style={"fontSize": "11px", "color": c["text_secondary"], "marginBottom": "6px"},
                ),
                html.Div(
                    style={"width": "100%"},
                    children=[
                        html.Div(
                            build_plot(
                                live_records,
                                initial_plot_message="Connect a board to see live data.",
                            ),
                            style={"width": "100%"},
                        )
                    ],
                ),
            ],
        )

    panels = (
        [build_container_view(container) for container in containers]
        or [html.Div("No plot configured.", style={"fontSize": "12px", "color": c["text_light"]})]
    )
    return html.Div(
        style={"display": "flex", "flexDirection": "column", "gap": "12px"},
        children=panels,
    )


# ---------------------------------------------------------------------------
# Full dashboard layout shell (left + right columns)
# ---------------------------------------------------------------------------

def build_dashboard_layout(
    transport_options: list[dict[str, str]],
    initial_param_inputs: list[html.Div],
    _theme: str | None = None,
    initial_dashboard_panel: html.Div | None = None,
    initial_history_panel: html.Div | None = None,
) -> html.Div:
    from .layout_history import build_history_panel  # local to avoid circular

    c = get_theme()
    card_style = get_card_style()
    button_primary = get_button_primary_style()
    button_base = get_button_base_style()

    # Render both panels server-side on first paint so they appear simultaneously.
    live_panel = initial_dashboard_panel or build_dashboard_canvas(
        boards=[], sensor_readings={}, dashboard_state=None
    )
    history_panel = initial_history_panel or build_history_panel(sessions_by_board=[])

    return html.Div(
        children=[
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "minmax(280px, 28%) minmax(0, 72%)",
                    "gap": "16px",
                    "minHeight": "calc(100vh - 170px)",
                },
                children=[
                    # ── Left: boards + connect ─────────────────────────────
                    html.Div(
                        style={
                            **card_style,
                            "overflowY": "auto",
                            "padding": "10px",
                        },
                        children=[
                            html.H3(
                                "Boards",
                                style={"margin": "0 0 10px 0", "color": c["text_primary"]},
                            ),
                            html.Div(
                                id="sensor-status",
                                style={"fontSize": "12px", "marginBottom": "6px", "color": c["text_primary"]},
                            ),
                            html.Div(id="boards-panel"),
                            # Connect card
                            html.Details(
                                open=False,
                                style={
                                    "border": f"1px solid {c['border_color_alt']}",
                                    "borderRadius": "10px",
                                    "backgroundColor": "transparent",
                                    "marginTop": "4px",
                                },
                                children=[
                                    html.Summary(
                                        style={
                                            "padding": "10px 14px",
                                            "cursor": "pointer",
                                            "fontWeight": "bold",
                                            "fontSize": "13px",
                                            "color": c["text_secondary"],
                                            "display": "flex",
                                            "alignItems": "center",
                                            "gap": "6px",
                                            "listStyle": "none",
                                        },
                                        children=[html.Span("Connect a board")],
                                    ),
                                    html.Div(
                                        style={"padding": "0 12px 12px 12px"},
                                        children=[
                                            html.Label(
                                                "Transport",
                                                style={
                                                    "fontWeight": "600",
                                                    "fontSize": "12px",
                                                    "marginBottom": "6px",
                                                    "display": "block",
                                                    "color": c["text_primary"],
                                                },
                                            ),
                                            dcc.Dropdown(
                                                id="transport-dropdown",
                                                options=transport_options,
                                                value=None,
                                                placeholder="Select transport",
                                                clearable=False,
                                                searchable=False,
                                                style={"marginBottom": "8px"},
                                            ),
                                            html.Div(
                                                id="transport-params-container",
                                                children=initial_param_inputs,
                                                style={
                                                    "marginBottom": "8px",
                                                    "padding": "8px",
                                                    "backgroundColor": c["button_bg_alt"],
                                                    "borderRadius": "4px",
                                                    "display": "flex",
                                                    "flexDirection": "column",
                                                    "gap": "8px",
                                                },
                                            ),
                                            html.Button(
                                                "Connect Board",
                                                id="connect-board-btn",
                                                n_clicks=0,
                                                style={**button_primary, "width": "100%"},
                                            ),
                                            html.Div(
                                                id="connect-status",
                                                style={
                                                    "marginTop": "8px",
                                                    "fontSize": "12px",
                                                    "color": c["text_primary"],
                                                },
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),

                    # ── Right: live plot + history ─────────────────────────
                    html.Div(
                        style={
                            "minWidth": 0,
                            "display": "flex",
                            "flexDirection": "column",
                            "gap": "0",
                        },
                        children=[
                            html.Div(
                                id="dashboard-panel",
                                style={"width": "100%"},
                                children=[live_panel],
                            ),
                            html.Div(
                                id="history-panel-container",
                                children=[history_panel],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
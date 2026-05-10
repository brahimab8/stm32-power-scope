# host/clients/dash/layout_board_panel.py
from __future__ import annotations

from typing import Any

from dash import dcc, html

from host.clients.period_presets import SENSOR_PERIOD_OPTIONS_MS

from .data import resolve_transport_meta
from .theme import (
    get_button_base_style,
    get_input_style,
    get_theme,
)
from .units import (
    convert_metric_unit_value,
    display_unit_text,
    normalize_unit_text,
    unit_options_from_metadata,
)
from .layout_base import dashboard_channel_key


# ---------------------------------------------------------------------------
# Internal formatters
# ---------------------------------------------------------------------------

def _format_uptime_ms(uptime_ms: int | None) -> str:
    if uptime_ms is None:
        return "-"
    total_s = max(0, int(uptime_ms) // 1000)
    hours = total_s // 3600
    minutes = (total_s % 3600) // 60
    seconds = total_s % 60
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _format_sensor_value(value: Any) -> str:
    if value is None:
        return "-"
    try:
        out = f"{float(value):.3f}"
        return out.replace(".", ",")
    except Exception:
        return str(value)


# ---------------------------------------------------------------------------
# Transport param inputs
# ---------------------------------------------------------------------------

def build_transport_param_inputs(
    transport_meta: dict[str, Any],
    _theme: str | None = None,
) -> list[html.Div]:
    params_meta = transport_meta.get("params", {})
    controls: list[html.Div] = []

    input_style = get_input_style()
    c = get_theme()

    for param_name, param_info in params_meta.items():
        required = bool(param_info.get("required", False))
        if not required:
            continue

        param_type = str(param_info.get("type", "str"))
        default_val = param_info.get("default")
        label = f"{param_name}*"
        cid = {"type": "transport-param", "index": str(param_name)}
        choices = list(param_info.get("choices", []) or [])

        if param_type == "bool":
            input_comp = dcc.Dropdown(
                id=cid,
                options=[{"label": "true", "value": True}, {"label": "false", "value": False}],
                value=bool(default_val),
                clearable=False,
                searchable=False,
                style=input_style,
            )
        elif choices:
            input_comp = dcc.Dropdown(
                id=cid,
                options=[{"label": str(item), "value": item} for item in choices],
                value=default_val if default_val is not None else choices[0],
                clearable=False,
                searchable=False,
                style=input_style,
            )
        elif param_type in ("int", "float"):
            if param_type == "int":
                input_comp = dcc.Input(
                    id=cid,
                    type="text",
                    inputMode="numeric",
                    pattern="[0-9]*",
                    value="" if default_val is None else str(default_val),
                    style=input_style,
                )
            else:
                input_comp = dcc.Input(
                    id=cid,
                    type="number",
                    value=default_val if default_val is not None else 0.0,
                    step=0.01,
                    style=input_style,
                )
        else:
            input_comp = dcc.Input(
                id=cid,
                type="text",
                value="" if default_val is None else str(default_val),
                style=input_style,
            )

        controls.append(
            html.Div(
                html.Div(
                    style={"marginBottom": "0", "boxSizing": "border-box"},
                    children=[
                        html.Label(
                            label,
                            style={"fontSize": "12px", "fontWeight": "bold", "color": c["text_primary"]},
                        ),
                        input_comp,
                    ],
                )
            )
        )

    if not controls:
        return [
            html.Div(
                "No parameters for selected transport",
                style={"fontSize": "12px", "color": c["text_light"]},
            )
        ]

    return [
        html.Div(
            controls,
            style={
                "display": "grid",
                "gridTemplateColumns": "minmax(0, 1fr)",
                "gap": "8px",
                "boxSizing": "border-box",
                "width": "100%",
            },
        )
    ]


# ---------------------------------------------------------------------------
# Connected boards panel
# ---------------------------------------------------------------------------

def build_connected_boards_panel(
    boards: list[dict[str, Any]],
    sensor_readings: dict[str, Any],
    sensor_channel_catalog: dict[int, list[dict[str, Any]]] | None = None,
    unit_overrides: dict[str, str] | None = None,
    uptime_by_board: dict[str, Any] | None = None,
    _theme: str | None = None,
) -> html.Div:
    c = get_theme()
    button_base = get_button_base_style()

    cards: list[html.Div] = []

    for board in boards:
        board_id = board.get("board_id", "unknown")
        if isinstance(board_id, str):
            try:
                board_id = int(board_id)
            except Exception:
                pass

        board_uid_hex = str(board.get("board_uid_hex") or "").strip().lower() or "unknown"
        transport = dict(board.get("transport") or {})
        transport_label = str(transport.get("label", "unknown"))
        transport_meta = resolve_transport_meta(transport_label)
        params_meta = dict(transport_meta.get("params") or {})
        required_param_names = [
            str(name)
            for name, meta in params_meta.items()
            if isinstance(meta, dict) and bool(meta.get("required", False))
        ]
        overrides = transport.get("overrides") or {}
        transport_params_str = "  ".join(
            f"{name}={transport.get(name) or overrides.get(name, '')}"
            for name in required_param_names
            if transport.get(name) or overrides.get(name)
        )

        status = dict(board.get("status") or {})
        sensors = list(status.get("sensors", []) or [])

        uptime_value = (uptime_by_board or {}).get(str(board_id))
        uptime_ms = None
        board_error: str | None = None
        if isinstance(uptime_value, dict) and "error" in uptime_value:
            board_error = "Connection lost"
        elif isinstance(uptime_value, (int, float)):
            uptime_ms = int(uptime_value)

        # ── Board header ──────────────────────────────────────────────────
        header = html.Div(
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "6px",
            },
            children=[
                html.Div(
                    style={"display": "flex", "flexDirection": "column", "gap": "2px", "minWidth": 0},
                    children=[
                        html.Div(
                            f"Board #{board_id}",
                            style={"fontWeight": "bold", "fontSize": "13px", "color": c["text_primary"]},
                        ),
                        html.Div(
                            board_uid_hex,
                            title=board_uid_hex,
                            style={
                                "fontSize": "10px",
                                "color": c["text_tertiary"],
                                "fontFamily": "monospace",
                                "overflow": "hidden",
                                "textOverflow": "ellipsis",
                                "whiteSpace": "nowrap",
                            },
                        ),
                    ],
                ),
                html.Button(
                    "Disconnect",
                    id={"type": "disconnect-board-btn", "index": board_id},
                    style=button_base,
                ),
            ],
        )

        # ── Transport row ─────────────────────────────────────────────────
        transport_row = html.Div(
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "8px",
            },
            children=[
                html.Div(
                    style={
                        "display": "flex",
                        "gap": "6px",
                        "alignItems": "center",
                        "minWidth": 0,
                        "overflow": "hidden",
                    },
                    children=[
                        html.Span(
                            transport_label,
                            style={
                                "fontSize": "11px",
                                "fontWeight": "600",
                                "color": c["text_secondary"],
                                "backgroundColor": c["button_bg_alt"],
                                "padding": "1px 6px",
                                "borderRadius": "4px",
                            },
                        ),
                        html.Span(
                            transport_params_str,
                            style={
                                "fontSize": "11px",
                                "color": c["text_tertiary"],
                                "overflow": "hidden",
                                "textOverflow": "ellipsis",
                                "whiteSpace": "nowrap",
                            },
                        ),
                    ],
                ),
                html.Div(
                    f"⚠ {board_error}" if board_error else f"⏱ {_format_uptime_ms(uptime_ms)}",
                    style={
                        "fontSize": "11px",
                        "color": "#d9534f" if board_error else c["text_tertiary"],
                        "whiteSpace": "nowrap",
                        "marginLeft": "8px",
                    },
                ),
            ],
        )

        # ── Sensor rows ───────────────────────────────────────────────────
        sensor_rows: list[html.Div] = []
        for sensor in sensors:
            runtime_id = int(sensor.get("runtime_id", -1))
            name = str(sensor.get("name", f"sensor_{runtime_id}"))
            streaming = bool(sensor.get("streaming", False))
            period_ms = sensor.get("period_ms")
            period_value = int(period_ms) if isinstance(period_ms, int) else 1000
            if period_value not in SENSOR_PERIOD_OPTIONS_MS:
                period_value = 1000

            reading_key = f"{board_id}:{runtime_id}"
            reading_entry = sensor_readings.get(reading_key)
            reading_payload = None
            if isinstance(reading_entry, dict):
                maybe = reading_entry.get("reading")
                if isinstance(maybe, dict):
                    reading_payload = maybe

            type_id = sensor.get("type_id")
            channel_specs: list[dict[str, Any]] = []
            try:
                sensor_type_id = int(type_id)
                channel_specs = list((sensor_channel_catalog or {}).get(sensor_type_id, []))
            except Exception:
                pass

            values_by_id: dict[int, dict[str, Any]] = {}
            if isinstance(reading_payload, dict):
                for group_name in ("measured", "computed"):
                    group = reading_payload.get(group_name) or {}
                    for cid, item in group.items():
                        if isinstance(item, dict):
                            try:
                                values_by_id[int(cid)] = item
                            except Exception:
                                pass

            sensor_header = html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "6px",
                    "gap": "6px",
                },
                children=[
                    html.Div(
                        f"[{runtime_id}] {name}",
                        style={
                            "fontWeight": "600",
                            "fontSize": "12px",
                            "color": c["text_primary"],
                            "minWidth": 0,
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "whiteSpace": "nowrap",
                        },
                    ),
                    html.Div(
                        style={"display": "flex", "gap": "4px", "alignItems": "center", "flexShrink": 0},
                        children=[
                            html.Button(
                                "Read",
                                id={"type": "sensor-read-btn", "board_id": board_id, "sensor_id": runtime_id},
                                disabled=streaming,
                                style={
                                    **button_base,
                                    "opacity": 0.45 if streaming else 1.0,
                                    "cursor": "not-allowed" if streaming else "pointer",
                                },
                            ),
                            html.Button(
                                "Stop  Stream" if streaming else "Start Stream",
                                id={"type": "sensor-toggle-btn", "board_id": board_id, "sensor_id": runtime_id},
                                style={**button_base},
                            ),
                            dcc.Dropdown(
                                id={"type": "sensor-period-select", "board_id": board_id, "sensor_id": runtime_id},
                                options=[
                                    {"label": f"{item}ms", "value": int(item)}
                                    for item in SENSOR_PERIOD_OPTIONS_MS
                                ],
                                value=period_value,
                                clearable=False,
                                searchable=False,
                                style={"width": "80px", "minWidth": "80px", "fontSize": "10px"},
                            ),
                        ],
                    ),
                ],
            )

            # ── Channel rows ──────────────────────────────────────────────
            channel_rows: list[html.Div] = []
            if channel_specs:
                for spec in channel_specs:
                    cid = int(spec.get("channel_id", -1))
                    unit_text = str(spec.get("unit") or "").strip()
                    channel_name = str(spec.get("name", f"ch_{cid}"))
                    reading_item = values_by_id.get(cid, {})
                    raw_unit = normalize_unit_text(
                        str((reading_item or {}).get("unit") or unit_text or "")
                    )
                    channel_key = dashboard_channel_key(board_id, runtime_id, cid)
                    selected_unit = normalize_unit_text(
                        str((unit_overrides or {}).get(channel_key, raw_unit) or raw_unit)
                    )
                    if not selected_unit:
                        selected_unit = raw_unit
                    channel_name_with_unit = (
                        f"{channel_name} ({display_unit_text(selected_unit)})"
                        if selected_unit
                        else channel_name
                    )
                    raw_value = (
                        (reading_item or {}).get("value") if isinstance(reading_item, dict) else None
                    )
                    display_value = (
                        convert_metric_unit_value(raw_value, raw_unit, selected_unit)
                        if selected_unit and raw_unit
                        else raw_value
                    )
                    value_text = _format_sensor_value(display_value)
                    unit_options = [
                        str(i)
                        for i in list(spec.get("unit_options", []) or [])
                        if str(i).strip()
                    ]
                    if not unit_options:
                        unit_options = unit_options_from_metadata(raw_unit or unit_text)
                    if selected_unit and selected_unit not in unit_options:
                        unit_options.append(selected_unit)

                    channel_rows.append(
                        html.Div(
                            style={
                                "display": "grid",
                                "gridTemplateColumns": "minmax(0, 1fr) minmax(0, 90px) minmax(0, 80px)",
                                "alignItems": "center",
                                "gap": "6px",
                                "minWidth": 0,
                            },
                            children=[
                                html.Div(
                                    channel_name_with_unit,
                                    style={"fontSize": "11px", "color": c["text_secondary"]},
                                ),
                                html.Div(
                                    value_text,
                                    style={
                                        "textAlign": "right",
                                        "fontSize": "11px",
                                        "fontVariantNumeric": "tabular-nums",
                                        "color": c["text_primary"],
                                        "height": "28px",
                                        "display": "flex",
                                        "alignItems": "center",
                                        "justifyContent": "flex-end",
                                        "padding": "0 8px",
                                        "borderRadius": "6px",
                                        "border": f"1px solid {c['border_color']}",
                                        "backgroundColor": c["button_bg"],
                                        "minWidth": 0,
                                    },
                                ),
                                dcc.Dropdown(
                                    id={
                                        "type": "channel-unit-select",
                                        "board_id": board_id,
                                        "sensor_id": runtime_id,
                                        "channel_id": cid,
                                    },
                                    options=[
                                        {"label": display_unit_text(opt), "value": opt}
                                        for opt in unit_options
                                    ],
                                    value=selected_unit or raw_unit,
                                    clearable=False,
                                    searchable=False,
                                    style={
                                        "width": "100%",
                                        "minWidth": 0,
                                        "fontSize": "10px",
                                        "height": "28px",
                                    },
                                ),
                            ],
                        )
                    )
            else:
                channel_rows.append(
                    html.Div(
                        "No channels.",
                        style={"fontSize": "10px", "color": c["text_light"]},
                    )
                )

            sensor_rows.append(
                html.Div(
                    style={
                        "padding": "8px",
                        "border": f"1px solid {c['border_color_alt']}",
                        "borderRadius": "8px",
                        "marginBottom": "6px",
                        "backgroundColor": c["card_bg"],
                    },
                    children=[
                        sensor_header,
                        html.Div(
                            style={"display": "flex", "flexDirection": "column", "gap": "4px"},
                            children=channel_rows,
                        ),
                    ],
                )
            )

        # ── Assemble board card ───────────────────────────────────────────
        board_children = [
            header,
            transport_row,
            html.Hr(
                style={
                    "border": "none",
                    "borderTop": f"1px solid {c['border_color_alt']}",
                    "margin": "0 0 8px 0",
                }
            ),
        ]
        if sensor_rows:
            board_children.extend(sensor_rows)
        else:
            board_children.append(
                html.Div(
                    "No sensors discovered yet.",
                    style={"fontSize": "11px", "color": c["text_light"]},
                )
            )

        cards.append(
            html.Div(
                style={
                    "border": f"1px solid {c['card_border']}",
                    "borderRadius": "10px",
                    "padding": "10px",
                    "marginBottom": "10px",
                    "backgroundColor": c["card_bg"],
                },
                children=board_children,
            )
        )

    return html.Div(cards)
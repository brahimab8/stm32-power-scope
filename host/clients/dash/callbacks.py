# host/clients/dash/callbacks.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import dash
from dash import Dash, Input, Output, State, html, no_update

from .data import (
    coerce_by_type,
    load_boards,
    new_client,
    resolve_sensor_channels,
    resolve_transport_meta,
    load_session_sensor_history,
    history_items_to_plot_records,
)
from .layout_board_panel import build_connected_boards_panel, build_transport_param_inputs
from .layout_dashboard import build_dashboard_canvas, build_plot
from .theme import get_theme


_MAX_READING_HISTORY = 600


# ---------------------------------------------------------------------------
# Trigger helpers
# ---------------------------------------------------------------------------

def _trigger_id() -> Any:
    ctx = dash.callback_context
    try:
        return ctx.triggered_id
    except Exception:
        triggered = getattr(ctx, "triggered", None) or []
        if not triggered:
            return None
        prop_id = str((triggered[0] or {}).get("prop_id", ""))
        return prop_id.split(".", 1)[0] if prop_id else None


def _clicked_count_for_index(
    *,
    triggered: Any,
    ids: list[dict[str, Any]] | None,
    clicks: list[int | None] | None,
) -> int:
    if not isinstance(triggered, dict):
        return 0
    target_index = str(triggered.get("index", ""))
    for item_id, count in zip(ids or [], clicks or []):
        if str((item_id or {}).get("index", "")) == target_index:
            return int(count or 0)
    return 0


def _clicked_count_for_board_sensor(
    *,
    triggered: Any,
    ids: list[dict[str, Any]] | None,
    clicks: list[int | None] | None,
) -> int:
    if not isinstance(triggered, dict):
        return 0
    target_board = str(triggered.get("board_id", ""))
    target_sensor = str(triggered.get("sensor_id", ""))
    for item_id, count in zip(ids or [], clicks or []):
        if str((item_id or {}).get("board_id", "")) != target_board:
            continue
        if str((item_id or {}).get("sensor_id", "")) != target_sensor:
            continue
        return int(count or 0)
    return 0


def _value_for_board_sensor(
    *,
    ids: list[dict[str, Any]] | None,
    values: list[Any] | None,
    board_id: Any,
    sensor_id: int,
) -> Any:
    board_text = str(board_id)
    sensor_text = str(sensor_id)
    for item_id, value in zip(ids or [], values or []):
        if str((item_id or {}).get("board_id", "")) != board_text:
            continue
        if str((item_id or {}).get("sensor_id", "")) != sensor_text:
            continue
        return value
    return None


def _value_for_board_sensor_channel(
    *,
    ids: list[dict[str, Any]] | None,
    values: list[Any] | None,
    board_id: Any,
    sensor_id: int,
    channel_id: int,
) -> Any:
    board_text = str(board_id)
    sensor_text = str(sensor_id)
    channel_text = str(channel_id)
    for item_id, value in zip(ids or [], values or []):
        if str((item_id or {}).get("board_id", "")) != board_text:
            continue
        if str((item_id or {}).get("sensor_id", "")) != sensor_text:
            continue
        if str((item_id or {}).get("channel_id", "")) != channel_text:
            continue
        return value
    return None


# ---------------------------------------------------------------------------
# Reading / history helpers
# ---------------------------------------------------------------------------

def _reading_channel_values(reading: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(reading, dict):
        return {}
    out: dict[str, Any] = {}
    for group_name in ("measured", "computed"):
        group = reading.get(group_name) or {}
        if not isinstance(group, dict):
            continue
        for channel_id, item in group.items():
            if not isinstance(item, dict):
                continue
            out[str(channel_id)] = item.get("value")
    return out


def _append_sensor_history(
    readings: dict[str, Any],
    *,
    key: str,
    reading: dict[str, Any],
    ts_utc: str | None,
) -> None:
    entry = dict(readings.get(key, {}) or {})
    history = list(entry.get("history", []) or [])
    item_ts = str(ts_utc or datetime.now(timezone.utc).isoformat())
    history.append({"ts_utc": item_ts, "channel_values": _reading_channel_values(reading)})
    if len(history) > _MAX_READING_HISTORY:
        history = history[-_MAX_READING_HISTORY:]
    readings[key] = {
        "reading": reading,
        "ts_utc": item_ts,
        "history": history,
    }


def _sensor_streaming_state(
    boards: list[dict[str, Any]] | None,
    board_id: Any,
    sensor_id: int,
) -> bool:
    for board in list(boards or []):
        if str(board.get("board_id", "")) != str(board_id):
            continue
        for sensor in list(dict(board.get("status") or {}).get("sensors", []) or []):
            if int(sensor.get("runtime_id", -1)) == int(sensor_id):
                return bool(sensor.get("streaming", False))
    return False


def _sensor_period_state(
    boards: list[dict[str, Any]] | None,
    board_id: Any,
    sensor_id: int,
) -> int | None:
    for board in list(boards or []):
        if str(board.get("board_id", "")) != str(board_id):
            continue
        for sensor in list(dict(board.get("status") or {}).get("sensors", []) or []):
            if int(sensor.get("runtime_id", -1)) != int(sensor_id):
                continue
            period_ms = sensor.get("period_ms")
            return int(period_ms) if isinstance(period_ms, int) else None
    return None


def _channel_catalog_for_boards(boards: list[dict[str, Any]] | None) -> dict[int, list[dict[str, Any]]]:
    catalog: dict[int, list[dict[str, Any]]] = {}
    for board in list(boards or []):
        for sensor in list(dict(board.get("status") or {}).get("sensors", []) or []):
            try:
                tid = int(sensor.get("type_id"))
            except Exception:
                continue
            if tid not in catalog:
                catalog[tid] = resolve_sensor_channels(tid)
    return catalog


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------

def register_callbacks(app: Dash, daemon_url: str, transport_options: list[dict[str, str]]) -> None:

    # ------------------------------------------------------------------ #
    # Uptime polling                                                       #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("uptime-store", "data"),
        Input("uptime-interval", "n_intervals"),
        State("boards-store", "data"),
        prevent_initial_call=False,
    )
    def update_uptime_store(_n_intervals, boards):
        if not boards:
            return {}
        client = new_client(daemon_url)
        uptime_by_board = {}
        for board in boards:
            board_id = board.get("board_id")
            if board_id is None:
                continue
            try:
                board_id_int = int(board_id)
            except Exception:
                continue
            try:
                result = client.uptime(board_id=board_id_int)
                uptime_ms = result.get("uptime_ms")
                if isinstance(uptime_ms, (int, float)):
                    uptime_by_board[str(board_id_int)] = int(uptime_ms)
            except Exception as e:
                uptime_by_board[str(board_id_int)] = {"error": str(e)}
        return uptime_by_board

    # ------------------------------------------------------------------ #
    # Boards store                                                         #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("boards-store", "data"),
        Input("refresh-token", "data"),
        Input("boards-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_boards_store(_refresh_token, _n_intervals):
        try:
            return load_boards(daemon_url)
        except Exception:
            return []

    # ------------------------------------------------------------------ #
    # Transport param inputs                                               #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("transport-params-container", "children"),
        Input("transport-dropdown", "value"),
        prevent_initial_call=False,
    )
    def update_transport_params(transport_id: str | None):
        c = get_theme()
        if transport_id is None:
            return [
                html.Div(
                    "Select a transport first",
                    style={"fontSize": "12px", "color": c["text_light"]},
                )
            ]
        transport_meta = resolve_transport_meta(transport_id)
        return build_transport_param_inputs(transport_meta)

    # ------------------------------------------------------------------ #
    # Board connect / disconnect                                           #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("connect-status", "children"),
        Output("connect-status", "style"),
        Output("refresh-token", "data"),
        Input("connect-board-btn", "n_clicks"),
        Input({"type": "disconnect-board-btn", "index": dash.ALL}, "n_clicks"),
        State({"type": "disconnect-board-btn", "index": dash.ALL}, "id"),
        State("transport-dropdown", "value"),
        State({"type": "transport-param", "index": dash.ALL}, "value"),
        State({"type": "transport-param", "index": dash.ALL}, "id"),
        State("boards-store", "data"),
        State("refresh-token", "data"),
        prevent_initial_call=True,
    )
    def board_actions(
        _connect_clicks,
        _disconnect_clicks,
        disconnect_ids,
        transport_id,
        param_values,
        param_ids,
        boards,
        refresh_token,
    ):
        trigger = _trigger_id()
        client = new_client(daemon_url)
        error_style = {"marginTop": "8px", "fontSize": "12px", "color": "#d9534f"}
        success_style = {"marginTop": "8px", "fontSize": "12px", "color": "#2c7a2c"}

        try:
            if trigger == "connect-board-btn":
                if not _connect_clicks:
                    return no_update, no_update, refresh_token
                if transport_id is None:
                    return "Transport is required.", error_style, refresh_token

                transport_meta = resolve_transport_meta(transport_id)
                transport_label = str(transport_meta.get("label", ""))
                params_meta = transport_meta.get("params", {})
                if not transport_label:
                    return "Invalid transport selection.", error_style, refresh_token

                value_by_name = {
                    str((pid or {}).get("index", "")): value
                    for pid, value in zip(param_ids, param_values)
                }
                overrides: dict[str, Any] = {}
                for param_name, param_info in params_meta.items():
                    p_name = str(param_name)
                    p_type = str(param_info.get("type", "str"))
                    p_required = bool(param_info.get("required", False))
                    p_default = param_info.get("default")
                    raw = value_by_name.get(p_name, p_default)
                    if raw in (None, "") and p_required and p_default is None:
                        return f"Missing required param: {p_name}", error_style, refresh_token
                    if raw in (None, ""):
                        continue
                    overrides[p_name] = coerce_by_type(raw, p_type)

                client.connect_board(transport=transport_label, overrides=overrides)
                return "Connected board.", success_style, int(refresh_token) + 1

            if isinstance(trigger, dict) and trigger.get("type") == "disconnect-board-btn":
                click_count = _clicked_count_for_index(
                    triggered=trigger, ids=disconnect_ids, clicks=_disconnect_clicks
                )
                if click_count <= 0:
                    return no_update, no_update, refresh_token
                board_id = trigger.get("index")
                if board_id is None:
                    return "Invalid board id.", error_style, refresh_token
                try:
                    board_id_int = int(board_id)
                except Exception:
                    return f"Invalid board id: {board_id}", error_style, refresh_token
                client.disconnect_board(board_id=board_id_int)
                return f"Disconnected board '{board_id_int}'.", success_style, int(refresh_token) + 1

            return no_update, no_update, refresh_token

        except Exception as e:
            return f"Board action failed: {e}", error_style, refresh_token

    # ------------------------------------------------------------------ #
    # Boards panel render                                                  #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("boards-panel", "children"),
        Input("boards-store", "data"),
        Input("sensor-readings-store", "data"),
        Input("channel-unit-store", "data"),
        Input("uptime-store", "data"),
        prevent_initial_call=False,
    )
    def render_boards(boards, sensor_readings, channel_unit_store, uptime_store):
        return build_connected_boards_panel(
            boards=list(boards or []),
            sensor_readings=dict(sensor_readings or {}),
            sensor_channel_catalog=_channel_catalog_for_boards(boards),
            unit_overrides=dict(channel_unit_store or {}),
            uptime_by_board=uptime_store,
        )

    # ------------------------------------------------------------------ #
    # Dashboard panel render                                               #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("dashboard-panel", "children"),
        Input("boards-store", "data"),
        Input("sensor-readings-store", "data"),
        Input("dashboard-layout-store", "data"),
        Input("channel-unit-store", "data"),
        prevent_initial_call=False,
    )
    def render_dashboard_panel(boards, sensor_readings, dashboard_state, channel_unit_store):
        return build_dashboard_canvas(
            boards=list(boards or []),
            sensor_readings=dict(sensor_readings or {}),
            dashboard_state=dashboard_state,
            sensor_channel_catalog=_channel_catalog_for_boards(boards),
            unit_overrides=dict(channel_unit_store or {}),
        )

    # ------------------------------------------------------------------ #
    # Channel unit overrides                                               #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("channel-unit-store", "data"),
        Input({"type": "channel-unit-select", "board_id": dash.ALL, "sensor_id": dash.ALL, "channel_id": dash.ALL}, "value"),
        State({"type": "channel-unit-select", "board_id": dash.ALL, "sensor_id": dash.ALL, "channel_id": dash.ALL}, "id"),
        State("channel-unit-store", "data"),
        prevent_initial_call=True,
    )
    def update_channel_unit_overrides(unit_values, unit_ids, channel_unit_store):
        trigger = _trigger_id()
        if not isinstance(trigger, dict) or trigger.get("type") != "channel-unit-select":
            return no_update

        board_id = str(trigger.get("board_id", "")).strip()
        try:
            sensor_id = int(trigger.get("sensor_id", -1))
            channel_id = int(trigger.get("channel_id", -1))
        except Exception:
            return no_update
        if not board_id or sensor_id < 0 or channel_id < 0:
            return no_update

        new_unit = _value_for_board_sensor_channel(
            ids=unit_ids,
            values=unit_values,
            board_id=board_id,
            sensor_id=sensor_id,
            channel_id=channel_id,
        )
        if new_unit in (None, ""):
            return no_update

        key = f"{board_id}:{sensor_id}:{channel_id}"
        next_store = dict(channel_unit_store or {})
        if str(next_store.get(key, "")) == str(new_unit):
            return no_update
        next_store[key] = str(new_unit)
        return next_store

    # ------------------------------------------------------------------ #
    # Stream polling                                                       #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("sensor-readings-store", "data", allow_duplicate=True),
        Input("stream-interval", "n_intervals"),
        State("boards-store", "data"),
        State("sensor-readings-store", "data"),
        prevent_initial_call=True,
    )
    def poll_stream_readings(_n_intervals, boards, sensor_readings):
        boards = list(boards or [])
        if not boards:
            return no_update

        has_streaming = any(
            bool(sensor.get("streaming", False))
            for board in boards
            for sensor in list(dict(board.get("status") or {}).get("sensors", []) or [])
        )
        if not has_streaming:
            return no_update

        client = new_client(daemon_url)
        readings = dict(sensor_readings or {})
        changed = False

        for board in boards:
            board_id = str(board.get("board_id", "")).strip()
            if not board_id:
                continue
            sensors = list(dict(board.get("status") or {}).get("sensors", []) or [])
            if not any(bool(s.get("streaming", False)) for s in sensors):
                continue
            try:
                out = client.drain_readings(board_id=board_id, limit=120)
            except Exception:
                continue
            for item in list(out.get("items", []) or []):
                try:
                    runtime_id = int(item.get("runtime_id", -1))
                except Exception:
                    continue
                if runtime_id < 0:
                    continue
                reading = item.get("reading")
                if not isinstance(reading, dict):
                    continue
                key = f"{board_id}:{runtime_id}"
                _append_sensor_history(readings, key=key, reading=reading, ts_utc=item.get("ts_utc"))
                changed = True

        return readings if changed else no_update

    # ------------------------------------------------------------------ #
    # Pre-load history on board connect                                    #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("sensor-readings-store", "data", allow_duplicate=True),
        Input("boards-store", "data"),
        State("sensor-readings-store", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def load_history_on_board_change(boards, sensor_readings):
        boards = list(boards or [])
        if not boards:
            return no_update

        client = new_client(daemon_url)
        readings = dict(sensor_readings or {})
        changed = False

        for board in boards:
            board_id = str(board.get("board_id", "")).strip()
            if not board_id:
                continue
            try:
                board_id_int = int(board_id)
            except Exception:
                continue
            for sensor in list(dict(board.get("status") or {}).get("sensors", []) or []):
                try:
                    runtime_id = int(sensor.get("runtime_id", -1))
                except Exception:
                    continue
                if runtime_id < 0:
                    continue
                key = f"{board_id}:{runtime_id}"
                if key in readings and readings[key].get("history"):
                    continue
                try:
                    out = client.sensor_history(
                        board_id=board_id_int,
                        sensor_runtime_id=runtime_id,
                        limit=_MAX_READING_HISTORY,
                    )
                except Exception:
                    continue
                for item in list(out.get("items", []) or []):
                    reading = item.get("reading")
                    if not isinstance(reading, dict):
                        continue
                    _append_sensor_history(
                        readings,
                        key=key,
                        reading=reading,
                        ts_utc=item.get("ts_utc"),
                    )
                    changed = True

        return readings if changed else no_update

    # ------------------------------------------------------------------ #
    # Sensor actions                                                       #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("sensor-status", "children"),
        Output("sensor-status", "style"),
        Output("refresh-token", "data", allow_duplicate=True),
        Output("sensor-readings-store", "data"),
        Input({"type": "sensor-read-btn", "board_id": dash.ALL, "sensor_id": dash.ALL}, "n_clicks"),
        Input({"type": "sensor-toggle-btn", "board_id": dash.ALL, "sensor_id": dash.ALL}, "n_clicks"),
        Input({"type": "sensor-period-select", "board_id": dash.ALL, "sensor_id": dash.ALL}, "value"),
        State({"type": "sensor-read-btn", "board_id": dash.ALL, "sensor_id": dash.ALL}, "id"),
        State({"type": "sensor-toggle-btn", "board_id": dash.ALL, "sensor_id": dash.ALL}, "id"),
        State({"type": "sensor-period-select", "board_id": dash.ALL, "sensor_id": dash.ALL}, "id"),
        State({"type": "sensor-period-select", "board_id": dash.ALL, "sensor_id": dash.ALL}, "value"),
        State("boards-store", "data"),
        State("refresh-token", "data"),
        State("sensor-readings-store", "data"),
        prevent_initial_call=True,
    )
    def sensor_actions(
        read_clicks,
        toggle_clicks,
        _period_input_values,
        read_ids,
        toggle_ids,
        period_select_ids,
        period_select_values,
        boards,
        refresh_token,
        sensor_readings,
    ):
        trigger = _trigger_id()
        readings = dict(sensor_readings or {})
        client = new_client(daemon_url)
        success_style = {"fontSize": "12px", "marginBottom": "8px", "color": "#2c7a2c"}
        error_style = {"fontSize": "12px", "marginBottom": "8px", "color": "#d9534f"}

        try:
            if isinstance(trigger, dict) and trigger.get("type") == "sensor-read-btn":
                click_count = _clicked_count_for_board_sensor(
                    triggered=trigger, ids=read_ids, clicks=read_clicks
                )
                if click_count <= 0:
                    return no_update, no_update, refresh_token, readings
                try:
                    board_id_int = int(trigger.get("board_id"))
                    sensor_id = int(trigger.get("sensor_id", -1))
                except Exception:
                    return "Invalid sensor target.", error_style, refresh_token, readings
                if sensor_id < 0:
                    return "Invalid sensor target.", error_style, refresh_token, readings
                out = client.read_sensor(board_id=board_id_int, sensor_runtime_id=sensor_id)
                reading = out.get("reading")
                if isinstance(reading, dict):
                    _append_sensor_history(
                        readings,
                        key=f"{board_id_int}:{sensor_id}",
                        reading=reading,
                        ts_utc=datetime.now(timezone.utc).isoformat(),
                    )
                return (
                    f"Read sensor {sensor_id} on '{board_id_int}'.",
                    success_style,
                    refresh_token,
                    readings,
                )

            if isinstance(trigger, dict) and trigger.get("type") == "sensor-toggle-btn":
                click_count = _clicked_count_for_board_sensor(
                    triggered=trigger, ids=toggle_ids, clicks=toggle_clicks
                )
                if click_count <= 0:
                    return no_update, no_update, refresh_token, readings
                try:
                    board_id_int = int(trigger.get("board_id"))
                    sensor_id = int(trigger.get("sensor_id", -1))
                except Exception:
                    return "Invalid sensor target.", error_style, refresh_token, readings
                if sensor_id < 0:
                    return "Invalid sensor target.", error_style, refresh_token, readings

                is_streaming = _sensor_streaming_state(boards, board_id_int, sensor_id)
                if is_streaming:
                    client.stop_stream(board_id=board_id_int, sensor_runtime_id=sensor_id)
                    msg = f"Stopped stream for sensor {sensor_id} on '{board_id_int}'."
                else:
                    client.start_stream(board_id=board_id_int, sensor_runtime_id=sensor_id)
                    msg = f"Started stream for sensor {sensor_id} on '{board_id_int}'."
                return msg, success_style, int(refresh_token) + 1, readings

            if isinstance(trigger, dict) and trigger.get("type") == "sensor-period-select":
                try:
                    board_id_int = int(trigger.get("board_id"))
                    sensor_id = int(trigger.get("sensor_id", -1))
                except Exception:
                    return "Invalid sensor target.", error_style, refresh_token, readings
                if sensor_id < 0:
                    return "Invalid sensor target.", error_style, refresh_token, readings

                raw_period = _value_for_board_sensor(
                    ids=period_select_ids,
                    values=period_select_values,
                    board_id=board_id_int,
                    sensor_id=sensor_id,
                )
                period_ms = int(raw_period)
                if period_ms <= 0:
                    return "Period must be > 0 ms.", error_style, refresh_token, readings

                current_period = _sensor_period_state(boards, board_id_int, sensor_id)
                if current_period is not None and int(current_period) == period_ms:
                    return no_update, no_update, refresh_token, readings

                try:
                    client.set_period(
                        board_id=board_id_int,
                        sensor_runtime_id=sensor_id,
                        period_ms=period_ms,
                    )
                except Exception as e:
                    return (
                        f"Set period failed for sensor {sensor_id} on '{board_id_int}': {e}",
                        error_style,
                        int(refresh_token) + 1,
                        readings,
                    )
                return (
                    f"Set period for sensor {sensor_id} on '{board_id_int}' to {period_ms} ms.",
                    success_style,
                    int(refresh_token) + 1,
                    readings,
                )

            return no_update, no_update, refresh_token, readings

        except Exception as e:
            return f"Sensor action failed: {e}", error_style, refresh_token, readings

    # ------------------------------------------------------------------ #
    # History: initial load + refresh                                      #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("history-sessions-store", "data"),
        Output("history-board-dropdown", "options"),
        Output("history-board-dropdown", "value"),
        Input("history-refresh-btn", "n_clicks"),
        prevent_initial_call=False,
    )
    def load_history_sessions(_n_clicks):
        try:
            sessions = new_client(daemon_url).list_sessions().get("boards", [])
        except Exception:
            sessions = []
        options = [
            {
                "label": (
                    f"Board {b['board_uid_hex'][:16]}… "
                    f"({b['session_count']} session{'s' if b['session_count'] != 1 else ''})"
                ),
                "value": b["board_uid_hex"],
            }
            for b in sessions
        ]
        first_value = options[0]["value"] if options else None
        return sessions, options, first_value

    # ------------------------------------------------------------------ #
    # History: board → session options                                     #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("history-session-dropdown", "options"),
        Output("history-session-dropdown", "value"),
        Input("history-board-dropdown", "value"),
        State("history-sessions-store", "data"),
        prevent_initial_call=True,
    )
    def populate_history_sessions(board_uid, sessions_store):
        if not board_uid or not sessions_store:
            return [], None
        board = next((b for b in sessions_store if b["board_uid_hex"] == board_uid), None)
        if not board:
            return [], None
        options = [
            {
                "label": (
                    f"{s['created_at_utc'][:19].replace('T', '  ')}   |   "
                    f"{s['transport_label']}   |   "
                    f"{len(s['sensors'])} sensor{'s' if len(s['sensors']) != 1 else ''}"
                ),
                "value": s["session_id"],
            }
            for s in board["sessions"]
        ]
        first_value = options[0]["value"] if options else None
        return options, first_value

    # ------------------------------------------------------------------ #
    # History: session → sensor options                                    #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("history-sensor-dropdown", "options"),
        Output("history-sensor-dropdown", "value"),
        Input("history-session-dropdown", "value"),
        State("history-sessions-store", "data"),
        prevent_initial_call=True,
    )
    def populate_history_sensors(session_id, sessions_store):
        if not session_id or not sessions_store:
            return [], None
        for board in sessions_store:
            for s in board["sessions"]:
                if s["session_id"] != session_id:
                    continue
                options = [
                    {
                        "label": f"[{sen['sensor_runtime_id']}] {sen['sensor_name']}  ({sen['channel_count']} ch)",
                        "value": str(sen["sensor_runtime_id"]),
                    }
                    for sen in s["sensors"]
                    if sen["has_data"]
                ]
                return options, (options[0]["value"] if options else None)
        return [], None

    # ------------------------------------------------------------------ #
    # History: sensor → stream file options                                #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("history-stream-dropdown", "options"),
        Output("history-stream-dropdown", "value"),
        Input("history-sensor-dropdown", "value"),
        State("history-session-dropdown", "value"),
        State("history-sessions-store", "data"),
        prevent_initial_call=True,
    )
    def populate_history_streams(sensor_rid, session_id, sessions_store):
        if not sensor_rid or not session_id or not sessions_store:
            return [], None
        for board in sessions_store:
            for s in board["sessions"]:
                if s["session_id"] != session_id:
                    continue
                for sen in s["sensors"]:
                    if str(sen["sensor_runtime_id"]) != str(sensor_rid):
                        continue
                    options = [
                        {
                            "label": f"{f['ts_label']}  ({f['size_bytes'] // 1024 or '<1'} KB)",
                            "value": f["rel_path"],
                        }
                        for f in sen.get("stream_files", [])
                    ]
                    last = options[-1]["value"] if options else None
                    return options, last
        return [], None

    # ------------------------------------------------------------------ #
    # History: load button → fetch data and render plot                    #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("history-plot-container", "children"),
        Output("history-status", "children"),
        Input("history-load-btn", "n_clicks"),
        State("history-session-dropdown", "value"),
        State("history-sensor-dropdown", "value"),
        State("history-stream-dropdown", "value"),
        State("history-sessions-store", "data"),
        prevent_initial_call=True,
    )
    def load_history_plot(_n_clicks, session_id, sensor_rid, stream_file, sessions_store):
        c = get_theme()
        error_style = {"fontSize": "11px", "color": "#d9534f"}

        if not session_id or not sensor_rid:
            return no_update, html.Span("Select a session and sensor first.", style=error_style)

        board_uid, sensor_name, transport_label = "", "", ""
        created_at_utc = ""
        transport_params_str = ""
        for board in (sessions_store or []):
            for s in board["sessions"]:
                if s["session_id"] != session_id:
                    continue
                board_uid = board["board_uid_hex"]
                transport_label = s.get("transport_label", "")
                created_at_utc = s.get("created_at_utc", "")
                # Try to extract transport params
                transport_params = s.get("transport_params", {})
                if transport_params:
                    # show the first param if it exists
                    k, v = next(iter(transport_params.items()))
                    transport_params_str = f"({k}: {v})"
                    # uncomment to show all params instead of just the first one
                    # param_strs = [f"{k}: {v}" for k, v in transport_params.items()]
                    # transport_params_str = f"({', '.join(param_strs)})"
                for sen in s["sensors"]:
                    if str(sen["sensor_runtime_id"]) == str(sensor_rid):
                        sensor_name = sen["sensor_name"]

        try:
            items = load_session_sensor_history(
                daemon_url,
                session_id=session_id,
                sensor_runtime_id=int(sensor_rid),
                stream_file=stream_file,
            )
        except Exception as e:
            return no_update, html.Span(f"Failed to load: {e}", style=error_style)

        records = history_items_to_plot_records(
            items,
            sensor_name=sensor_name,
            sensor_runtime_id=int(sensor_rid),
            board_uid=board_uid,
        )

        point_count = sum(len(r["history_points"]) for r in records)
        # Format timestamp
        started_str = ""
        if created_at_utc:
            try:
                dt = datetime.fromisoformat(created_at_utc.replace("Z", "+00:00"))
                started_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception:
                started_str = created_at_utc
        # Find stream file timestamp label (first file or selected file)
        stream_file_ts_label = ""
        for board in (sessions_store or []):
            for s in board["sessions"]:
                if s["session_id"] != session_id:
                    continue
                for sen in s["sensors"]:
                    if str(sen["sensor_runtime_id"]) == str(sensor_rid):
                        stream_files = sen.get("stream_files", [])
                        if stream_file:
                            for f in stream_files:
                                if isinstance(f, dict) and f.get("rel_path") == stream_file:
                                    stream_file_ts_label = f.get("ts_label", "")
                                    break
                        elif stream_files:
                            f = stream_files[0]
                            if isinstance(f, dict):
                                stream_file_ts_label = f.get("ts_label", "")
        status_str = (
            f"Loaded {point_count} points across {len(records)} channel{'s' if len(records) != 1 else ''} — "
            f"Board: {board_uid[:12]}… — "
            f"Session created at: {started_str} — "
            f"{sensor_name} [{sensor_rid}] — "
            f"First stream timestamp: {stream_file_ts_label} — "
            f"Transport: {transport_label} {transport_params_str} — "
        )
        status = html.Span(
            status_str,
            style={"fontSize": "11px", "color": c["text_secondary"]},
        )
        return build_plot(records), status
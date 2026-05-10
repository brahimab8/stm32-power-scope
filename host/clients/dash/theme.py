# host/clients/dash/theme.py
from __future__ import annotations

FONT_FAMILY = "Inter, Segoe UI, Arial, sans-serif"

DEFAULT_THEME = "dark"

_DARK: dict[str, str] = {
    "bg": "#0f172a",
    "bg_secondary": "#1e293b",
    "card_bg": "#1e293b",
    "card_border": "#334155",
    "card_alt_bg": "#1a2332",
    "card_alt_border": "#2d3e52",
    "text_primary": "#e2e8f0",
    "text_secondary": "#cbd5e1",
    "text_tertiary": "#94a3b8",
    "text_light": "#64748b",
    "border_color": "#334155",
    "border_color_alt": "#475569",
    "border_color_dashed": "#475569",
    "button_bg": "#334155",
    "button_bg_alt": "#1e293b",
    "input_border": "#334155",
    "accent": "#3b82f6",
    "accent_light": "#60a5fa",
}


def get_theme(_theme: str | None = None) -> dict[str, str]:
    """Always returns the dark theme. Parameter kept for call-site compatibility."""
    return _DARK


def get_card_style(_theme: str | None = None) -> dict:
    c = _DARK
    return {
        "border": f"1px solid {c['card_border']}",
        "borderRadius": "12px",
        "padding": "12px",
        "backgroundColor": c["card_bg"],
    }


def get_button_base_style(_theme: str | None = None) -> dict:
    c = _DARK
    return {
        "fontSize": "12px",
        "fontWeight": "600",
        "padding": "6px 12px",
        "borderRadius": "8px",
        "cursor": "pointer",
        "border": f"1px solid {c['border_color']}",
        "backgroundColor": c["button_bg"],
        "color": c["text_primary"],
    }


def get_button_primary_style(_theme: str | None = None) -> dict:
    c = _DARK
    return {
        **get_button_base_style(),
        "backgroundColor": c["accent"],
        "border": f"1px solid {c['accent']}",
        "color": "#ffffff",
    }


def get_input_style(_theme: str | None = None) -> dict:
    c = _DARK
    return {
        "width": "100%",
        "fontSize": "13px",
        "padding": "7px 10px",
        "borderRadius": "8px",
        "border": f"1px solid {c['input_border']}",
        "backgroundColor": c["card_bg"],
        "color": c["text_primary"],
        "boxSizing": "border-box",
    }
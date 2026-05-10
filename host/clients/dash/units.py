# host/clients/dash/units.py
from __future__ import annotations

from typing import Any

_UNIT_PREFIX_EXP: dict[str, int] = {
    "p": -12,
    "n": -9,
    "u": -6,
    "m": -3,
    "": 0,
    "k": 3,
    "M": 6,
}
_EXP_TO_PREFIX = {exp: prefix for prefix, exp in _UNIT_PREFIX_EXP.items()}


def normalize_unit_text(unit: str) -> str:
    return str(unit or "").strip().replace("µ", "u")


def display_unit_text(unit: str) -> str:
    """Format units for UI display without changing internal normalized unit values."""
    text = normalize_unit_text(unit)
    if text.startswith("u") and len(text) > 1 and text[1:].isalpha():
        return f"µ{text[1:]}"
    return text


def split_metric_unit(unit: str) -> tuple[str, str] | None:
    text = normalize_unit_text(unit)
    if not text:
        return None
    if len(text) == 1 and text.isalpha():
        return "", text
    first = text[0]
    tail = text[1:]
    if first in _UNIT_PREFIX_EXP and tail.isalpha():
        return first, tail
    if text.isalpha():
        return "", text
    return None


def unit_options_from_metadata(default_unit: str) -> list[str]:
    split = split_metric_unit(default_unit)
    if split is None:
        unit_text = normalize_unit_text(default_unit)
        return [unit_text] if unit_text else []

    _prefix, base = split
    if base not in {"V", "A", "W"}:
        return [f"{_prefix}{base}" if _prefix else base]

    # Keep a compact, sensible list of SI prefixes.
    exps = [-6, -3, 0, 3]
    return [f"{_EXP_TO_PREFIX.get(exp, '')}{base}" for exp in exps]


def convert_metric_unit_value(value: Any, from_unit: str, to_unit: str) -> Any:
    if value is None:
        return None
    try:
        numeric = float(value)
    except Exception:
        return value

    from_split = split_metric_unit(from_unit)
    to_split = split_metric_unit(to_unit)
    if from_split is None or to_split is None:
        return numeric

    from_prefix, from_base = from_split
    to_prefix, to_base = to_split
    if from_base != to_base:
        return numeric

    from_exp = _UNIT_PREFIX_EXP.get(from_prefix)
    to_exp = _UNIT_PREFIX_EXP.get(to_prefix)
    if from_exp is None or to_exp is None:
        return numeric
    return numeric * (10.0 ** (from_exp - to_exp))

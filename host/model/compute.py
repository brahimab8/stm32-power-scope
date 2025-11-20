# host/model/compute.py
from __future__ import annotations

from typing import Callable, Iterable, List


def _product(vals: Iterable[float]) -> float:
    r = 1.0
    for v in vals:
        r *= float(v)
    return r


OPS: dict[str, Callable[[List[float]], float]] = {
    "multiply": lambda v: _product(v),
    "add": lambda v: float(sum(v)),
    "mean": lambda v: float(sum(v) / len(v)),
    "min": lambda v: float(min(v)),
    "max": lambda v: float(max(v)),
}


def op_subtract(vals: List[float]) -> float:
    if len(vals) != 2:
        raise ValueError("subtract requires exactly 2 inputs")
    return float(vals[0] - vals[1])


def op_divide(vals: List[float]) -> float:
    if len(vals) != 2:
        raise ValueError("divide requires exactly 2 inputs")
    denom = float(vals[1])
    return float(vals[0] / denom) if denom != 0.0 else float("inf")


OPS["subtract"] = op_subtract
OPS["divide"] = op_divide


def eval_op(operation: str, vals: List[float]) -> float:
    op = operation.lower()
    fn = OPS.get(op)
    if not fn:
        raise NotImplementedError(f"Unknown compute operation '{operation}'")
    if not vals:
        raise ValueError("compute requires at least one input")
    return fn(vals)

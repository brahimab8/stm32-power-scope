from __future__ import annotations

import math
import pytest

from host.model.compute import eval_op


def test_eval_op_unknown_raises():
    with pytest.raises(NotImplementedError):
        eval_op("nope", [1.0])


def test_eval_op_requires_at_least_one_input():
    with pytest.raises(ValueError):
        eval_op("add", [])


def test_add_multiply_mean_min_max():
    assert eval_op("add", [1.0, 2.0, 3.0]) == 6.0
    assert eval_op("multiply", [2.0, 3.0, 4.0]) == 24.0
    assert eval_op("mean", [2.0, 4.0]) == 3.0
    assert eval_op("min", [3.0, -1.0, 5.0]) == -1.0
    assert eval_op("max", [3.0, -1.0, 5.0]) == 5.0


def test_subtract_requires_two_inputs():
    with pytest.raises(ValueError):
        eval_op("subtract", [1.0])
    with pytest.raises(ValueError):
        eval_op("subtract", [1.0, 2.0, 3.0])

    assert eval_op("subtract", [5.0, 2.0]) == 3.0


def test_divide_requires_two_inputs():
    with pytest.raises(ValueError):
        eval_op("divide", [1.0])
    with pytest.raises(ValueError):
        eval_op("divide", [1.0, 2.0, 3.0])

    assert eval_op("divide", [6.0, 2.0]) == 3.0


def test_divide_by_zero_returns_inf():
    out = eval_op("divide", [1.0, 0.0])
    assert math.isinf(out) and out > 0

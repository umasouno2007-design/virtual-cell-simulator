"""不改写运行中实验状态的细胞内条件沙盒。"""

from copy import deepcopy
from math import isfinite
from typing import Any

from cell import CellCulture
from intracellular import IntracellularState
from numeric_utils import is_boolean_scalar


FORECAST_INPUTS = {
    "oxygen_percent": {"label": "起始局部氧代理", "unit": "模型刻度 %", "low": 0.5, "high": 21.0, "default": 5.0},
    "glucose_mm": {"label": "葡萄糖", "unit": "mM", "low": 0.0, "high": 50.0, "default": 5.0},
    "drug_um": {"label": "药物浓度", "unit": "µM", "low": 0.0, "high": 1000.0, "default": 10.0},
}


def forecast_intracellular_state(
    cell: CellCulture,
    state: IntracellularState,
    *,
    attribute: str,
    value: float,
    horizon_h: float,
) -> dict[str, Any]:
    """复制当前状态并推进候选条件；原对象始终不被修改。"""

    if not isinstance(cell, CellCulture):
        raise ValueError("条件推演需要有效的培养状态对象。")
    if not isinstance(state, IntracellularState):
        raise ValueError("条件推演需要有效的代表性细胞状态。")
    # Validate model parameters even for a zero-hour request: otherwise the no-op
    # branch below could bypass the checks normally performed by a model step.
    try:
        cell._validate_finite_parameters()
    except (AttributeError, TypeError, ValueError):
        raise ValueError("培养模型参数无效；请检查参数后再推演。") from None
    if not isinstance(attribute, str) or attribute not in FORECAST_INPUTS:
        raise KeyError(f"未知条件：{attribute}")
    if is_boolean_scalar(cell.time_h) or is_boolean_scalar(state.time_h):
        raise ValueError("培养时钟与代表性细胞状态时钟必须是有限小时数。")
    try:
        cell_time_h = float(cell.time_h)
        state_time_h = float(state.time_h)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("培养时钟与代表性细胞状态时钟必须是有限小时数。") from None
    if not isfinite(cell_time_h) or not isfinite(state_time_h) or cell_time_h < 0 or state_time_h < 0:
        raise ValueError("培养时钟与代表性细胞状态时钟必须是有限非负小时数。")
    if abs(cell_time_h - state_time_h) > 1e-6:
        raise ValueError("培养时钟与代表性细胞状态时钟不一致；请先重置或同步当前场景。")
    # Also validate the source state for zero-hour requests, which otherwise
    # would bypass the checks normally performed by an intracellular step.
    if not state.finite():
        raise ValueError("代表性细胞状态包含越界或非有限值；请重置或修复状态后再推演。")
    if is_boolean_scalar(value) or is_boolean_scalar(horizon_h):
        raise ValueError("候选条件和推演时长必须是有限数值。")
    try:
        candidate_value = float(value)
        requested_h = float(horizon_h)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("候选条件和推演时长必须是有限数值。") from None
    specification = FORECAST_INPUTS[attribute]
    if not isfinite(candidate_value) or not specification["low"] <= candidate_value <= specification["high"]:
        raise ValueError(f"候选{specification['label']}超出当前沙盒输入范围。")
    if not isfinite(requested_h) or not 0.0 <= requested_h <= 48.0:
        raise ValueError("推演时长必须是 0–48 h 内的有限数值；不会静默截短。")
    candidate_cell = deepcopy(cell)
    candidate_state = deepcopy(state)
    setattr(candidate_cell, attribute, candidate_value)
    remaining = requested_h
    while remaining > 1e-9 and candidate_cell.alive:
        dt_h = min(0.25, remaining)
        candidate_cell.step(dt_h)
        candidate_state.step(candidate_cell, dt_h)
        remaining -= dt_h
    return {
        "candidate_cell": candidate_cell.snapshot(),
        "candidate_state": candidate_state.snapshot(),
        "completed_h": requested_h - remaining,
        "input": {"attribute": attribute, "value": candidate_value},
    }

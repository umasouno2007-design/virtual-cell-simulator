"""不改写运行中实验状态的细胞内条件沙盒。"""

from copy import deepcopy
from math import isfinite
from typing import Any

from cell import CellCulture
from intracellular import IntracellularState


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

    if attribute not in FORECAST_INPUTS:
        raise KeyError(f"未知条件：{attribute}")
    if isinstance(value, bool) or isinstance(horizon_h, bool):
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

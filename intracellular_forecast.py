"""不改写运行中实验状态的细胞内条件沙盒。"""

from copy import deepcopy
from typing import Any

from cell import CellCulture
from intracellular import IntracellularState


FORECAST_INPUTS = {
    "oxygen_percent": {"label": "溶氧", "unit": "%", "low": 0.5, "high": 21.0, "default": 5.0},
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
    candidate_cell = deepcopy(cell)
    candidate_state = deepcopy(state)
    setattr(candidate_cell, attribute, float(value))
    remaining = max(0.0, min(float(horizon_h), 48.0))
    while remaining > 1e-9 and candidate_cell.alive:
        dt_h = min(0.25, remaining)
        candidate_cell.step(dt_h)
        candidate_state.step(candidate_cell, dt_h)
        remaining -= dt_h
    return {
        "candidate_cell": candidate_cell.snapshot(),
        "candidate_state": candidate_state.snapshot(),
        "completed_h": float(horizon_h) - remaining,
        "input": {"attribute": attribute, "value": float(value)},
    }

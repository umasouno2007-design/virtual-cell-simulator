"""可审阅的两参数网格搜索校准。"""

from dataclasses import dataclass, replace
from math import isfinite

import pandas as pd

from cell import CellCulture, ModelParameters
from experiment_data import comparison_frame


FIT_FIELDS = ("viable_cells", "glucose_mM", "lactate_mM")
_SNAPSHOT_FIELDS = {
    "viable_cells": "viable_cells", "dead_cells": "dead_cells", "time_h": "time_h",
    "glucose_mM": "glucose_mm", "glutamine_mM": "glutamine_mm", "lactate_mM": "lactate_mm",
    "oxygen_percent": "oxygen_percent", "pH": "ph", "temperature_C": "temperature_c",
    "CO2_percent": "co2_percent", "osmolality_mOsm_kg": "osmolality_mosm_kg",
    "drug_uM": "drug_um", "energy_index": "energy_index",
}


@dataclass
class CalibrationResult:
    growth_scale: float
    uptake_scale: float
    normalized_rmse: float
    fitted_history: list[dict]


def _make_cell(template: CellCulture, initial: dict, growth_scale: float, uptake_scale: float) -> CellCulture:
    parameters: ModelParameters = replace(template.parameters)
    parameters.growth_scale = growth_scale
    parameters.uptake_scale = uptake_scale
    cell = CellCulture(template.profile_key, template.culture_volume_ml, template.surface_area_cm2, parameters=parameters)
    for source, target in _SNAPSHOT_FIELDS.items():
        if source in initial:
            setattr(cell, target, initial[source])
    return cell


def replay_from_initial(template: CellCulture, initial: dict, target_times, growth_scale: float, uptake_scale: float) -> tuple[CellCulture, list[dict]]:
    """从历史首点重演到指定时间；最大内部步长为 1 小时。"""

    cell = _make_cell(template, initial, growth_scale, uptake_scale)
    history = [cell.snapshot()]
    for target in sorted({float(value) for value in target_times if float(value) >= cell.time_h}):
        while cell.alive and cell.time_h < target:
            cell.step(min(1.0, target - cell.time_h))
        if target > initial.get("time_h", 0.0):
            history.append(cell.snapshot())
    return cell, history


def _score(comparison: pd.DataFrame) -> float:
    terms = []
    for field in FIT_FIELDS:
        observed = f"{field}_observed"
        residual = f"{field}_residual"
        if observed not in comparison or residual not in comparison:
            continue
        values = comparison[[observed, residual]].dropna()
        if len(values) < 2:
            continue
        scale = max(float(values[observed].abs().max()), float(values[observed].max() - values[observed].min()), 1.0)
        terms.extend((values[residual] / scale).pow(2).tolist())
    return float("inf") if not terms else (sum(terms) / len(terms)) ** 0.5


def fit_growth_and_uptake(template: CellCulture, model_history: list[dict], measurements: pd.DataFrame) -> CalibrationResult:
    """在明确范围内穷举两个缩放系数，不拟合无数据支撑的其他参数。"""

    if len(measurements) < 2:
        raise ValueError("粗校准至少需要两个实测时间点。")
    eligible = [field for field in FIT_FIELDS if field in measurements and measurements[field].notna().sum() >= 2]
    if not eligible:
        raise ValueError("请至少提供活细胞数、葡萄糖或乳酸中的一个指标，且不少于两个时间点。")
    if not model_history:
        raise ValueError("没有可作为初始条件的模拟历史。")
    initial = model_history[0]
    growth_candidates = [round(value / 10, 1) for value in range(1, 21)]
    uptake_candidates = [round(value / 10, 1) for value in range(1, 31)]
    best: tuple[float, float, float] | None = None
    for growth in growth_candidates:
        for uptake in uptake_candidates:
            _, sampled = replay_from_initial(template, initial, measurements["time_h"], growth, uptake)
            score = _score(comparison_frame(pd.DataFrame(sampled), measurements))
            if isfinite(score) and (best is None or score < best[0]):
                best = (score, growth, uptake)
    if best is None:
        raise ValueError("实测时间点超出可重演范围，无法完成粗校准。")
    _, replayed = replay_from_initial(template, initial, [item["time_h"] for item in model_history], best[1], best[2])
    return CalibrationResult(best[1], best[2], best[0], replayed)

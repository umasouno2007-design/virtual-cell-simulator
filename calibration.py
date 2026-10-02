"""可审阅的两参数网格搜索校准。"""

from dataclasses import dataclass, replace
from math import isfinite

import pandas as pd

from cell import CellCulture, ModelParameters
from experiment_data import comparison_frame, residual_summary


FIT_FIELDS = ("viable_cells", "glucose_mM", "lactate_mM")
_CULTURE_INTERVENTIONS = {
    "环境调整", "全量换液", "设置药物", "补充葡萄糖", "补充溶氧", "应用粗校准",
    "计划执行：补充葡萄糖", "计划执行：补充溶氧",
    "计划执行：部分换液", "计划执行：设置药物",
}
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
    grid_scores: list[dict] | None = None
    weights: dict[str, float] | None = None
    training_time_h: list[float] | None = None
    holdout_time_h: list[float] | None = None
    training_metrics: list[dict] | None = None
    holdout_metrics: list[dict] | None = None


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


def _score(comparison: pd.DataFrame, weights: dict[str, float] | None = None) -> float:
    """计算按观测量纲归一化后的加权 RMSE；权重是可解释偏好而非统计权重。"""

    weighted_squared_error = 0.0
    total_weight = 0.0
    for field in FIT_FIELDS:
        observed = f"{field}_observed"
        residual = f"{field}_residual"
        if observed not in comparison or residual not in comparison:
            continue
        values = comparison[[observed, residual]].dropna()
        if len(values) < 2:
            continue
        scale = max(float(values[observed].abs().max()), float(values[observed].max() - values[observed].min()), 1.0)
        weight = float((weights or {}).get(field, 1.0))
        if not isfinite(weight) or weight < 0:
            raise ValueError("校准指标权重必须是有限的非负数。")
        if weight == 0:
            continue
        normalized_squared = (values[residual] / scale).pow(2)
        weighted_squared_error += float((normalized_squared * weight).sum())
        total_weight += weight * len(normalized_squared)
    return float("inf") if total_weight <= 0 else (weighted_squared_error / total_weight) ** 0.5


def fit_growth_and_uptake(
    template: CellCulture, model_history: list[dict], measurements: pd.DataFrame,
    weights: dict[str, float] | None = None,
    events: list[dict] | None = None,
) -> CalibrationResult:
    """在明确范围内穷举两个缩放系数；中途培养干预需先另建无干预场景。"""

    if len(measurements) < 2:
        raise ValueError("粗校准至少需要两个实测时间点。")
    eligible = [field for field in FIT_FIELDS if field in measurements and measurements[field].notna().sum() >= 2]
    if not eligible:
        raise ValueError("请至少提供活细胞数、葡萄糖或乳酸中的一个指标，且不少于两个时间点。")
    try:
        if any(isinstance(value, bool) for value in (weights or {}).values()):
            raise TypeError("布尔权重不是数值输入。")
        resolved_weights = {field: float((weights or {}).get(field, 1.0)) for field in FIT_FIELDS}
    except (TypeError, ValueError):
        raise ValueError("校准指标权重必须为数值。") from None
    if any(not isfinite(value) or value < 0 for value in resolved_weights.values()):
        raise ValueError("校准指标权重必须是有限的非负数。")
    if not any(resolved_weights[field] > 0 for field in eligible):
        raise ValueError("至少一个具备观测值的校准指标权重必须大于 0。")
    if not model_history:
        raise ValueError("没有可作为初始条件的模拟历史。")
    if "time_h" not in measurements.columns:
        raise ValueError("实测数据缺少 time_h 列，无法与模拟时间轴对齐。")
    initial = model_history[0]
    initial_time = float(initial.get("time_h", 0.0))
    if not isfinite(initial_time) or initial_time < 0:
        raise ValueError("模拟历史起点必须是有限非负小时数。")
    # 多个 t=0 快照可能代表设置初始条件；以同一时刻的最后快照作为重演起点。
    initial = next(
        (item for item in reversed(model_history) if abs(float(item.get("time_h", -1)) - initial_time) < 1e-9),
        initial,
    )
    for event in events or []:
        name = str(event.get("event", ""))
        if name not in _CULTURE_INTERVENTIONS:
            continue
        try:
            event_time = float(event.get("time_h", -1))
        except (TypeError, ValueError):
            raise ValueError("培养干预记录的模拟时间无效；无法确认校准重演条件。") from None
        if not isfinite(event_time):
            raise ValueError("培养干预记录的模拟时间无效；无法确认校准重演条件。")
        if event_time > initial_time + 1e-9:
            raise ValueError(
                f"模拟历史包含中途培养干预（{name}，t={event_time:g} h）；"
                "当前两参数网格不重放干预，请从干预后的场景重新开始并匹配实测时间原点。"
            )
    measurement_times = pd.to_numeric(measurements["time_h"], errors="coerce")
    if measurement_times.isna().any() or not measurement_times.map(isfinite).all():
        raise ValueError("粗校准时间列包含缺失或非有限值，无法与模拟时间轴对齐。")
    if (measurement_times < 0).any():
        raise ValueError("粗校准时间不能为负值；请使用从实验起点开始的小时数。")
    if (measurement_times < initial_time).any():
        raise ValueError(
            f"有实测时间早于模拟历史起点（{initial_time:g} h）；"
            "请统一实验时间原点或从匹配的初始场景重新模拟。"
        )
    for field in FIT_FIELDS:
        if field not in measurements:
            continue
        values = pd.to_numeric(measurements[field], errors="coerce")
        if (values.notna() & ~values.map(isfinite)).any():
            raise ValueError(f"{field} 包含无穷值；请先修正数据质量问题。")
        if (values.dropna() < 0).any():
            raise ValueError(f"{field} 包含负值；请先核对单位或数据质量。")
    if "viability_percent" in measurements:
        viability = pd.to_numeric(measurements["viability_percent"], errors="coerce").dropna()
        if (viability > 100.0).any():
            raise ValueError("存活率不能超过 100%；请核对输入是否为百分比。")
    growth_candidates = [round(value / 10, 1) for value in range(1, 21)]
    uptake_candidates = [round(value / 10, 1) for value in range(1, 31)]
    best: tuple[float, float, float] | None = None
    grid_scores: list[dict] = []
    for growth in growth_candidates:
        for uptake in uptake_candidates:
            _, sampled = replay_from_initial(template, initial, measurements["time_h"], growth, uptake)
            score = _score(comparison_frame(pd.DataFrame(sampled), measurements), weights)
            grid_scores.append({"growth_scale": growth, "uptake_scale": uptake, "normalized_rmse": score})
            if isfinite(score) and (best is None or score < best[0]):
                best = (score, growth, uptake)
    if best is None:
        raise ValueError("实测时间点超出可重演范围，无法完成粗校准。")
    _, replayed = replay_from_initial(template, initial, [item["time_h"] for item in model_history], best[1], best[2])
    return CalibrationResult(best[1], best[2], best[0], replayed, grid_scores, weights or {})


def fit_with_temporal_holdout(
    template: CellCulture, model_history: list[dict], measurements: pd.DataFrame,
    weights: dict[str, float] | None = None, events: list[dict] | None = None,
) -> CalibrationResult:
    """最后至少两个时间点作描述性留出；少于五点时只报告拟合误差。"""

    if "time_h" not in measurements:
        raise ValueError("实测数据缺少 time_h 列，无法划分训练与留出时间点。")
    times = pd.to_numeric(measurements["time_h"], errors="coerce")
    if times.isna().any() or not times.map(isfinite).all() or (times < 0).any():
        raise ValueError("时间列必须是有限非负小时数，才能划分训练与留出点。")
    if times.duplicated().any():
        raise ValueError("实测时间点重复；请先核对并标准化 CSV。")
    ordered = measurements.assign(time_h=times).sort_values("time_h").reset_index(drop=True)
    for field in FIT_FIELDS:
        if field not in ordered:
            continue
        values = pd.to_numeric(ordered[field], errors="coerce")
        if (values.notna() & ~values.map(isfinite)).any() or (values.dropna() < 0).any():
            raise ValueError(f"{field} 含无效观测；请先处理整个数据集，再划分留出点。")
    holdout_count = max(2, round(len(ordered) * 0.2)) if len(ordered) >= 5 else 0
    training = ordered.iloc[:-holdout_count] if holdout_count else ordered
    holdout = ordered.iloc[-holdout_count:] if holdout_count else ordered.iloc[0:0]
    result = fit_growth_and_uptake(template, model_history, training, weights, events)
    initial_time = float(model_history[0].get("time_h", 0.0))
    initial = next(
        (item for item in reversed(model_history) if abs(float(item.get("time_h", -1)) - initial_time) < 1e-9),
        model_history[0],
    )
    _, sampled = replay_from_initial(
        template, initial, ordered["time_h"], result.growth_scale, result.uptake_scale,
    )
    replay = pd.DataFrame(sampled)
    result.training_time_h = [float(value) for value in training["time_h"]]
    result.holdout_time_h = [float(value) for value in holdout["time_h"]]
    result.training_metrics = residual_summary(comparison_frame(replay, training)).to_dict("records")
    result.holdout_metrics = (
        residual_summary(comparison_frame(replay, holdout)).to_dict("records")
        if holdout_count else []
    )
    return result

"""可审阅的两参数网格搜索校准。"""

from dataclasses import dataclass, replace
from math import isclose, isfinite

import pandas as pd

from cell import CellCulture, ModelParameters
from data_quality import quality_report
from experiment_data import FIELD_LABELS, comparison_frame, residual_summary
from version import MODEL_VERSION
from numeric_utils import is_boolean_scalar


FIT_FIELDS = ("viable_cells", "glucose_mM", "lactate_mM")
# 与当前培养场景可配置的最长运行时段一致；这不是生物学有效期。
MAX_CALIBRATION_HORIZON_H = 168.0
_CULTURE_INTERVENTIONS = {
    "环境调整", "全量换液", "设置药物", "补充葡萄糖", "补充溶氧", "应用粗校准",
    "计划执行：补充葡萄糖", "计划执行：补充溶氧",
    "计划执行：部分换液", "计划执行：设置药物",
}
_SNAPSHOT_FIELDS = {
    "viable_cells": "viable_cells", "dead_cells": "dead_cells", "time_h": "time_h",
    "glucose_mM": "glucose_mm", "glutamine_mM": "glutamine_mm", "lactate_mM": "lactate_mm",
    "oxygen_percent": "oxygen_percent", "pH": "ph", "temperature_C": "temperature_c",
    "oxygen_setpoint_percent": "oxygen_setpoint_percent",
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
    warnings: list[str] | None = None


def _make_cell(template: CellCulture, initial: dict, growth_scale: float, uptake_scale: float) -> CellCulture:
    parameters: ModelParameters = replace(template.parameters)
    parameters.growth_scale = growth_scale
    parameters.uptake_scale = uptake_scale
    cell = CellCulture(template.profile_key, template.culture_volume_ml, template.surface_area_cm2, parameters=parameters)
    # 旧培养历史快照只记录局部氧代理，不包含培养环境氧设定值。
    # 无中途干预的校准沿用当前实验场景的设定值，而非构造器的默认 18.6%。
    cell.oxygen_setpoint_percent = template.oxygen_setpoint_percent
    for source, target in _SNAPSHOT_FIELDS.items():
        if source in initial:
            setattr(cell, target, initial[source])
    return cell


def replay_from_initial(template: CellCulture, initial: dict, target_times, growth_scale: float, uptake_scale: float) -> tuple[CellCulture, list[dict]]:
    """从历史首点重演至有限目标时刻；每段内部步长不超过 1 h。"""

    if not isinstance(template, CellCulture):
        raise ValueError("校准重演模板必须是有效的培养状态对象。")
    if not isinstance(initial, dict) or initial.get("cell_type") != template.profile_key:
        raise ValueError("校准重演起点的细胞系与当前模板不一致；请核对实验来源。")
    if initial.get("model_version") != MODEL_VERSION:
        raise ValueError("校准重演起点的模型版本不一致；不能混合不同版本结果。")
    cell = _make_cell(template, initial, growth_scale, uptake_scale)
    history = [cell.snapshot()]
    if isinstance(target_times, (str, bytes)):
        raise ValueError("校准重演时间必须是有限小时数。")
    try:
        raw_targets = list(target_times)
        if any(is_boolean_scalar(value) for value in raw_targets):
            raise TypeError
        targets = [float(value) for value in raw_targets]
    except (TypeError, ValueError, OverflowError):
        raise ValueError("校准重演时间必须是有限小时数。") from None
    if any(not isfinite(target) or target < cell.time_h for target in targets):
        raise ValueError("校准重演时间必须是有限数值，且不能早于起始时刻。")
    if targets and max(targets) - cell.time_h > MAX_CALIBRATION_HORIZON_H:
        raise ValueError(f"校准重演最长支持 {MAX_CALIBRATION_HORIZON_H:g} h；请缩短拟合时段或分段分析。")
    for target in sorted(set(targets)):
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
        try:
            weight = float((weights or {}).get(field, 1.0))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("校准指标权重必须是有限的非负数。") from None
        if not isfinite(weight) or weight < 0:
            raise ValueError("校准指标权重必须是有限的非负数。")
        if weight == 0:
            continue
        if comparison[observed].notna().sum() < 2:
            continue
        # 观测点若落在重演轨迹之外，不能靠丢弃这些残差得到虚假的低误差。
        if (comparison[observed].notna() & comparison[residual].isna()).any():
            return float("inf")
        values = comparison[[observed, residual]].dropna()
        if len(values) < 2:
            continue
        scale = max(float(values[observed].abs().max()), float(values[observed].max() - values[observed].min()), 1.0)
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

    if not isinstance(template, CellCulture):
        raise ValueError("校准模板必须是有效的培养状态对象。")
    if not isinstance(measurements, pd.DataFrame):
        raise ValueError("校准观测必须是已标准化的 Pandas 表格。")
    if events is not None and (
        not isinstance(events, list) or any(not isinstance(event, dict) for event in events)
    ):
        raise ValueError("校准干预记录必须是事件对象列表。")
    if len(measurements) < 2:
        raise ValueError("粗校准至少需要两个实测时间点。")
    eligible = [
        field for field in FIT_FIELDS
        if field in measurements and pd.to_numeric(measurements[field], errors="coerce").notna().sum() >= 2
    ]
    if not eligible:
        raise ValueError("请至少提供活细胞数、葡萄糖或乳酸中的一个指标，且不少于两个时间点。")
    if weights is not None and not isinstance(weights, dict):
        raise ValueError("校准指标权重必须是以指标名称为键的映射。")
    unknown_weights = set(weights or {}) - set(FIT_FIELDS)
    if unknown_weights:
        unknown = "、".join(sorted(str(name) for name in unknown_weights))
        raise ValueError(f"校准权重包含不支持的指标：{unknown}。可用指标：{'、'.join(FIT_FIELDS)}。")
    try:
        if any(is_boolean_scalar(value) for value in (weights or {}).values()):
            raise TypeError("布尔权重不是数值输入。")
        resolved_weights = {field: float((weights or {}).get(field, 1.0)) for field in FIT_FIELDS}
    except (TypeError, ValueError, OverflowError):
        raise ValueError("校准指标权重必须为数值。") from None
    if any(not isfinite(value) or value < 0 for value in resolved_weights.values()):
        raise ValueError("校准指标权重必须是有限的非负数。")
    if not any(resolved_weights[field] > 0 for field in eligible):
        raise ValueError("至少一个具备观测值的校准指标权重必须大于 0。")
    if not model_history:
        raise ValueError("没有可作为初始条件的模拟历史。")
    if "time_h" not in measurements.columns:
        raise ValueError("实测数据缺少 time_h 列，无法与模拟时间轴对齐。")
    previous_model_time = -1.0
    for row in model_history:
        if not isinstance(row, dict) or row.get("cell_type") != template.profile_key or row.get("model_version") != MODEL_VERSION:
            raise ValueError("模拟历史含不同细胞系或模型版本；不能混用为校准起点。")
        try:
            model_time = float(row["time_h"])
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValueError("模拟历史时间必须是有限非负小时数。") from None
        if not isfinite(model_time) or model_time < previous_model_time:
            raise ValueError("模拟历史时间必须是有限非负且单调不减的小时数。")
        for field in FIT_FIELDS:
            value = row.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
                raise ValueError(f"模拟历史字段 {field} 必须是有限非负数值。")
        previous_model_time = model_time
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
        except (TypeError, ValueError, OverflowError):
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
    if measurement_times.duplicated().any():
        raise ValueError("粗校准时间点重复；请先核对原始记录并显式生成标准化副本，避免同一时刻被重复加权。")
    if (measurement_times < initial_time).any():
        raise ValueError(
            f"有实测时间早于模拟历史起点（{initial_time:g} h）；"
            "请统一实验时间原点或从匹配的初始场景重新模拟。"
        )
    if float(measurement_times.max()) - initial_time > MAX_CALIBRATION_HORIZON_H:
        raise ValueError(f"粗校准最长支持从模拟起点起 {MAX_CALIBRATION_HORIZON_H:g} h 的实测时段；请缩短拟合时段或分段分析。")
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
    # 直接调用网格搜索也须经过与界面相同的质量门槛。否则未参与拟合的
    # 氧/pH 等列或原始 CSV 的解析问题可能被训练入口忽略。
    report = quality_report(measurements)
    if report["blocked"]:
        raise ValueError(f"实测数据质量阻止粗校准：{report['blocked'][0][0]}。{report['blocked'][0][1]}")
    initial_warnings = []
    start_rows = measurements.loc[measurement_times == initial_time]
    if not start_rows.empty:
        for field in FIT_FIELDS:
            if field not in measurements or field not in initial:
                continue
            observed = pd.to_numeric(start_rows[field], errors="coerce").iloc[0]
            if pd.notna(observed) and not isclose(float(observed), float(initial[field]), rel_tol=1e-6, abs_tol=1e-9):
                initial_warnings.append(
                    f"{FIELD_LABELS[field]}的起点观测与模拟初值不同；两个缩放参数不能修正起点差异，"
                    "请核对接种量、培养基和时间原点。"
                )
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
    return CalibrationResult(best[1], best[2], best[0], replayed, grid_scores, weights or {}, warnings=initial_warnings)


def fit_with_temporal_holdout(
    template: CellCulture, model_history: list[dict], measurements: pd.DataFrame,
    weights: dict[str, float] | None = None, events: list[dict] | None = None,
) -> CalibrationResult:
    """最后至少两个时间点作描述性留出；少于五点时只报告拟合误差。"""

    if not isinstance(template, CellCulture):
        raise ValueError("校准模板必须是有效的培养状态对象。")
    if not isinstance(measurements, pd.DataFrame):
        raise ValueError("校准观测必须是已标准化的 Pandas 表格。")
    if "time_h" not in measurements:
        raise ValueError("实测数据缺少 time_h 列，无法划分训练与留出时间点。")
    times = pd.to_numeric(measurements["time_h"], errors="coerce")
    if times.isna().any() or not times.map(isfinite).all() or (times < 0).any():
        raise ValueError("时间列必须是有限非负小时数，才能划分训练与留出点。")
    if times.duplicated().any():
        raise ValueError("实测时间点重复；请先核对并标准化 CSV。")
    ordered = measurements.assign(time_h=times).sort_values("time_h").reset_index(drop=True)
    ordered.attrs = measurements.attrs.copy()
    if model_history:
        try:
            initial_time = float(model_history[0].get("time_h", 0.0))
        except (TypeError, ValueError):
            initial_time = float("nan")
        if isfinite(initial_time) and not ordered.empty and float(ordered["time_h"].max()) - initial_time > MAX_CALIBRATION_HORIZON_H:
            raise ValueError(f"粗校准最长支持从模拟起点起 {MAX_CALIBRATION_HORIZON_H:g} h 的实测时段；请缩短拟合时段或分段分析。")
    report = quality_report(ordered)
    if report["blocked"]:
        raise ValueError(f"实测数据质量阻止粗校准：{report['blocked'][0][0]}。{report['blocked'][0][1]}")
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

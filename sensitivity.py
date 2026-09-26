"""经验培养模型的单因素敏感性分析。

范围是情景探索范围，不是置信区间，也不代表参数的真实生物学分布。模块只
复用现有模型，不改变其方程或在分析过程中改写用户正在运行的培养状态。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite

import pandas as pd

from cell import CellCulture, ModelParameters


METRICS = ("viable_cells", "viability_percent", "glucose_mM", "lactate_mM", "pH")


@dataclass(frozen=True)
class SensitivityParameter:
    """单因素情景定义；values 是无量纲缩放值，不是统计置信区间。"""

    key: str
    label: str
    values: tuple[float, float, float]
    source: str
    limitation: str


SENSITIVITY_PARAMETERS = {
    "doubling_time": SensitivityParameter(
        "doubling_time", "群体倍增时间", (0.8, 1.0, 1.2),
        "A549 等细胞系的中心倍增时间来自细胞库；±20% 为 C 级教学情景范围。",
        "细胞库记录不是同批次实验的置信区间；必须用本体系生长曲线校准。",
    ),
    "growth_scale": SensitivityParameter(
        "growth_scale", "生长速率缩放", (0.5, 1.0, 1.5),
        "B 级待校准先验；取现有 UI 校准范围内的宽松情景点。",
        "只表达未校准生长项的依赖性，不给出真实参数分布。",
    ),
    "uptake_scale": SensitivityParameter(
        "uptake_scale", "代谢摄取缩放", (0.5, 1.0, 1.5),
        "B 级待校准先验；取现有 UI 校准范围内的宽松情景点。",
        "细胞系、培养基和密度均会改变摄取率；需要实测葡萄糖/乳酸数据。",
    ),
}

PENDING_MEASUREMENT_PARAMETERS = (
    "基础死亡率、氧传递系数、pH 缓冲容量、乳酸生成率与承载密度：当前没有可公开通用的、"
    "适用于本模型三种细胞系和培养体系的范围，因此未进入默认敏感性扫描，需由实验测定。"
)


def _clone(cell: CellCulture) -> CellCulture:
    """深拷贝模型状态；单位保持为 cells、mM、%、h，且不修改输入对象。"""

    clone = CellCulture(
        cell.profile_key, cell.culture_volume_ml, cell.surface_area_cm2,
        viable_cells=cell.viable_cells, parameters=replace(cell.parameters),
    )
    for name in (
        "dead_cells", "time_h", "glucose_mm", "glutamine_mm", "lactate_mm",
        "oxygen_percent", "oxygen_setpoint_percent", "ph", "temperature_c",
        "co2_percent", "osmolality_mosm_kg", "drug_um", "energy_index",
    ):
        setattr(clone, name, getattr(cell, name))
    return clone


def _apply_scenario(cell: CellCulture, key: str, factor: float) -> None:
    if key == "doubling_time":
        cell.profile = replace(cell.profile, doubling_time_h=cell.profile.doubling_time_h * factor)
    elif key == "growth_scale":
        cell.parameters.growth_scale *= factor
    elif key == "uptake_scale":
        cell.parameters.uptake_scale *= factor
    else:
        raise ValueError(f"未知敏感性参数：{key}")


def simulate_one_factor(cell: CellCulture, parameter_key: str, horizon_h: float = 72.0) -> pd.DataFrame:
    """在固定起点下逐项改变一个参数并输出每小时历史。

    ``horizon_h`` 单位为 h，必须为有限的正数且不超过 168 h；输出含场景、时间和
    ``METRICS`` 所列真实单位指标。异常输入抛出 ``ValueError``。
    """

    if parameter_key not in SENSITIVITY_PARAMETERS:
        raise ValueError(f"未知敏感性参数：{parameter_key}")
    if not isfinite(horizon_h) or not 0 < horizon_h <= 168:
        raise ValueError("分析时长必须是 0–168 h 内的有限正数。")
    definition = SENSITIVITY_PARAMETERS[parameter_key]
    rows: list[dict] = []
    for factor, scenario in zip(definition.values, ("低情景", "基准", "高情景")):
        trial = _clone(cell)
        _apply_scenario(trial, parameter_key, factor)
        rows.append({"parameter": parameter_key, "parameter_label": definition.label, "scenario": scenario, "factor": factor, **trial.snapshot()})
        remaining = float(horizon_h)
        while trial.alive and remaining > 1e-9:
            dt = min(1.0, remaining)
            trial.step(dt)
            remaining -= dt
            rows.append({"parameter": parameter_key, "parameter_label": definition.label, "scenario": scenario, "factor": factor, **trial.snapshot()})
    return pd.DataFrame(rows)


def run_sensitivity(cell: CellCulture, horizon_h: float = 72.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """运行全部默认单因素场景，返回逐时历史和终点摘要；不估计置信区间。"""

    histories = [simulate_one_factor(cell, key, horizon_h) for key in SENSITIVITY_PARAMETERS]
    history = pd.concat(histories, ignore_index=True)
    final_time = history.groupby(["parameter", "scenario"])["time_h"].transform("max")
    summary = history[history["time_h"] == final_time].copy()
    return history, summary[["parameter", "parameter_label", "scenario", "factor", "time_h", *METRICS]]

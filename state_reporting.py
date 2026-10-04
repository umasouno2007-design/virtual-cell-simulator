"""单细胞轨迹的描述性变化摘要；不参与状态模拟。"""

from __future__ import annotations

from math import isfinite
from typing import Any


_INDEX_LABELS = {
    "ATP_percent": "ATP",
    "mitochondrial_potential_percent": "线粒体功能",
    "glycolysis_percent": "糖酵解",
    "ROS_percent": "ROS",
    "DNA_damage_percent": "DNA 损伤",
    "ER_stress_percent": "ER 应激",
    "autophagy_percent": "自噬适应/回收",
    "protein_synthesis_percent": "蛋白合成",
    "growth_signal_percent": "增殖信号",
    "apoptosis_signal_percent": "促凋亡压力",
}


def intracellular_change_summary(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """比较最后两条状态记录，返回相对指数差和每小时变化率。

    仅作轨迹描述，不是实验速率或统计估计。若两条记录处于相同时点
    （例如施加教学干预），保留差值但将速率标为不可计算。
    """

    if not history:
        return []
    latest = history[-1]
    previous = history[-2] if len(history) > 1 else None
    delta_time = None
    if previous is not None:
        try:
            delta_time = float(latest["time_h"]) - float(previous["time_h"])
        except (KeyError, TypeError, ValueError, OverflowError):
            delta_time = None
        if delta_time is not None and (not isfinite(delta_time) or delta_time < 0):
            delta_time = None

    rows: list[dict[str, Any]] = []
    for key, label in _INDEX_LABELS.items():
        try:
            current = float(latest[key])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if not isfinite(current):
            continue
        delta = None
        rate = None
        note = "无前一条记录"
        if previous is not None:
            try:
                prior_value = float(previous[key])
                if not isfinite(prior_value):
                    raise ValueError
                delta = current - prior_value
                if delta_time is not None and delta_time > 0:
                    rate = delta / delta_time
                    note = f"相邻记录间隔 {delta_time:g} h；描述性模型差值"
                elif delta_time == 0:
                    note = "同一模拟时点的干预/状态更新；不计算每小时速率"
                else:
                    note = "时间信息无效；不计算每小时速率"
            except (KeyError, TypeError, ValueError, OverflowError):
                note = "缺少有效的前一条指标值"
        rows.append({
            "指标": label,
            "当前值（相对指数，0–100）": current,
            "较上一条记录变化（指数点）": delta,
            "变化速率（指数点/h）": rate,
            "说明": note,
        })
    return rows

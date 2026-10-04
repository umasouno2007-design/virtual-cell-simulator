"""细胞周期互动导航的演示性时间估算。"""

from typing import Any
from math import isfinite

from numeric_utils import is_boolean_scalar


def _finite_number(value: float, name: str) -> float:
    if is_boolean_scalar(value):
        raise ValueError(f"{name} 必须是有限数值，不能是布尔值。")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} 必须是有限数值。") from None
    if not isfinite(number):
        raise ValueError(f"{name} 必须是有限数值。")
    return number


def next_cycle_checkpoint(
    progress_percent: float, growth_signal_percent: float, doubling_time_h: float
) -> dict[str, Any]:
    """返回下一相位边界及基于当前模型增长信号的估计推进时间。

    边界继承 ``IntracellularState`` 的演示性阶段划分；增长信号不是实测
    周期速度，因此结果仅用于交互导航。
    """

    progress = _finite_number(progress_percent, "细胞周期进度")
    growth_signal = _finite_number(growth_signal_percent, "增殖信号")
    doubling_time = _finite_number(doubling_time_h, "倍增时间")
    if not 0.0 <= progress <= 100.0:
        raise ValueError("细胞周期进度必须位于 0–100%。")
    if not 0.0 <= growth_signal <= 100.0:
        raise ValueError("增殖信号相对指数必须位于 0–100%。")
    if not 1.0 <= doubling_time <= 500.0:
        raise ValueError("倍增时间必须位于 1–500 h。")
    progress %= 100.0
    if progress < 45.0:
        target, phase = 45.0, "S"
    elif progress < 75.0:
        target, phase = 75.0, "G2"
    elif progress < 92.0:
        target, phase = 92.0, "M"
    else:
        target, phase = 100.0, "G1"
    signal_fraction = max(0.01, growth_signal / 100.0)
    hours = (target - progress) / 100.0 * doubling_time / signal_fraction
    return {
        "current_progress": progress,
        "target_progress": target % 100.0,
        "next_phase": phase,
        "estimated_hours": hours,
    }

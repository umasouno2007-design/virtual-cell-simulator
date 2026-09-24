"""细胞周期互动导航的演示性时间估算。"""

from typing import Any


def next_cycle_checkpoint(
    progress_percent: float, growth_signal_percent: float, doubling_time_h: float
) -> dict[str, Any]:
    """返回下一相位边界及基于当前模型增长信号的估计推进时间。

    边界继承 ``IntracellularState`` 的演示性阶段划分；增长信号不是实测
    周期速度，因此结果仅用于交互导航。
    """

    progress = float(progress_percent) % 100.0
    if progress < 45.0:
        target, phase = 45.0, "S"
    elif progress < 75.0:
        target, phase = 75.0, "G2"
    elif progress < 92.0:
        target, phase = 92.0, "M"
    else:
        target, phase = 100.0, "G1"
    signal_fraction = max(0.01, float(growth_signal_percent) / 100.0)
    hours = (target - progress) / 100.0 * float(doubling_time_h) / signal_fraction
    return {
        "current_progress": progress,
        "target_progress": target % 100.0,
        "next_phase": phase,
        "estimated_hours": hours,
    }

"""模拟控制、实验场景与状态判定。"""

from math import isfinite
from typing import Dict, List

from cell import CellCulture, ModelParameters
from numeric_utils import is_boolean_scalar


History = List[Dict[str, float | str]]
MAX_BATCH_STEPS = 10_000


PRESETS = {
    "标准培养": {
        "changes": {},
        "description": "采用所选细胞系的推荐温度、CO₂、接种密度和基础培养基。",
    },
    "低氧培养（1% O₂）": {
        "changes": {"oxygen_percent": 1.0, "oxygen_setpoint_percent": 1.0},
        "description": "模拟低氧培养箱；需用实测溶氧校准传质参数。",
    },
    "酸性微环境": {
        "changes": {"ph": 6.8},
        "description": "从 pH 6.8 开始，观察酸化对生长和糖酵解的影响。",
    },
    "高密度接种": {
        "changes": {"seeding_fraction": 0.80},
        "description": "初始汇合度约 80%，用于观察接触抑制和营养消耗。",
    },
    "药物暴露": {
        "changes": {"drug_um": 10.0},
        "description": "默认 10 µM；必须输入该药物在所选细胞系中的 IC50。",
    },
}


def new_simulation(
    profile_key: str = "hela",
    preset_name: str = "标准培养",
    culture_volume_ml: float = 10.0,
    surface_area_cm2: float = 25.0,
) -> tuple[CellCulture, History]:
    """创建指定细胞系和实验场景，并保存初始数据点。"""

    cell = CellCulture(
        profile_key=profile_key,
        culture_volume_ml=culture_volume_ml,
        surface_area_cm2=surface_area_cm2,
        parameters=ModelParameters(),
    )
    if not isinstance(preset_name, str) or preset_name not in PRESETS:
        supported = "、".join(PRESETS)
        raise ValueError(f"不支持的实验预设；可用预设：{supported}。")
    changes = PRESETS[preset_name]["changes"]
    for name, value in changes.items():
        if name == "seeding_fraction":
            cell.viable_cells = cell.carrying_capacity * value
        else:
            setattr(cell, name, value)
    return cell, [cell.snapshot()]


def run_steps(
    cell: CellCulture, history: History, steps: int = 1, dt_h: float = 1.0
) -> int:
    """原子地推进非负整数步，并为每步记录带单位的数据。

    参数校验或任一步推进/记录失败时，恢复调用前的培养状态和历史长度；
    单次调用最多推进 10,000 步作为软件资源保护，不代表科学时长上限。
    培养量、时间及步长单位与 ``CellCulture`` 相同。
    """

    if not isinstance(cell, CellCulture):
        raise ValueError("批量模拟需要有效的 CellCulture 对象。")
    if not isinstance(history, list):
        raise ValueError("模拟历史必须是可追加的列表。")
    if type(steps) is not int or not 0 <= steps <= MAX_BATCH_STEPS:
        raise ValueError(f"模拟步数必须是 0–{MAX_BATCH_STEPS:,} 范围内的整数。")
    if is_boolean_scalar(dt_h):
        raise ValueError("每步时长必须是 0–6 h 内的有限正数。")
    try:
        step_hours = float(dt_h)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("每步时长必须是 0–6 h 内的有限正数。") from None
    if not isfinite(step_hours) or not 0 < step_hours <= 6.0:
        raise ValueError("每步时长必须是 0–6 h 内的有限正数。")

    before_state = cell.__dict__.copy()
    history_length = len(history)
    completed = 0
    try:
        for _ in range(steps):
            if not cell.alive:
                break
            cell.step(step_hours)
            history.append(cell.snapshot())
            completed += 1
    except Exception:
        cell.__dict__.clear()
        cell.__dict__.update(before_state)
        del history[history_length:]
        raise
    return completed


def cell_status(cell: CellCulture) -> tuple[str, str]:
    """依据可测培养指标返回当前状态与提示级别。"""

    if not cell.alive or cell.viability_percent <= 10:
        return "培养物失活", "error"
    if cell.viability_percent < 70:
        return "大量细胞死亡", "error"
    if cell.ph < 6.7 or cell.ph > 7.8:
        return "严重 pH 偏离", "error"
    if cell.oxygen_percent < 1.0:
        return "极低氧", "error"
    if cell.glucose_mm < 0.2:
        return "葡萄糖接近耗尽", "error"
    if cell.lactate_mm > 25:
        return "乳酸高负荷", "warning"
    if cell.oxygen_percent < 5.0:
        return "低氧", "warning"
    if not 7.0 <= cell.ph <= 7.6:
        return "pH 偏离推荐范围", "warning"
    if cell.confluence_percent > 90:
        return "接近满汇合，建议传代", "warning"
    if cell.energy_index < 45:
        return "代谢能量状态受抑", "warning"
    return "培养状态稳定", "success"

"""模拟控制、实验场景与状态判定。"""

from typing import Dict, List

from cell import CellCulture, ModelParameters


History = List[Dict[str, float | str]]


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
    changes = PRESETS.get(preset_name, PRESETS["标准培养"])["changes"]
    for name, value in changes.items():
        if name == "seeding_fraction":
            cell.viable_cells = cell.carrying_capacity * value
        else:
            setattr(cell, name, value)
    return cell, [cell.snapshot()]


def run_steps(
    cell: CellCulture, history: History, steps: int = 1, dt_h: float = 1.0
) -> int:
    """推进指定步数；每步记录一次带单位的数据。"""

    completed = 0
    for _ in range(max(0, int(steps))):
        if not cell.alive:
            break
        cell.step(dt_h)
        history.append(cell.snapshot())
        completed += 1
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

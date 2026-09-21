"""模拟控制、历史记录与状态文字。"""

from typing import Dict, List

from cell import Cell, MetabolismParameters


History = List[Dict[str, float]]


# 教学实验预设：只改变初始环境和少量模型参数。
PRESETS = {
    "正常培养环境": {
        "cell": {"glucose": 60.0, "oxygen": 70.0, "atp": 50.0, "mitochondria": 5},
        "parameters": {},
        "description": "资源适中，适合观察完整的有氧到缺氧过程。",
    },
    "急性缺氧": {
        "cell": {"glucose": 70.0, "oxygen": 12.0, "atp": 45.0, "mitochondria": 5},
        "parameters": {},
        "description": "氧气很少，可快速观察无氧代谢和乳酸堆积。",
    },
    "高能量需求": {
        "cell": {"glucose": 75.0, "oxygen": 80.0, "atp": 45.0, "mitochondria": 6},
        "parameters": {"maintenance_base": 8.0},
        "description": "ATP 维护消耗更高，资源会更快耗尽。",
    },
    "线粒体丰富": {
        "cell": {"glucose": 65.0, "oxygen": 85.0, "atp": 50.0, "mitochondria": 9},
        "parameters": {"maintenance_base": 5.5},
        "description": "有氧代谢容量较高，同时承担更多线粒体维护成本。",
    },
    "酸性环境": {
        "cell": {"glucose": 65.0, "oxygen": 70.0, "atp": 50.0, "mitochondria": 5, "ph": 6.7},
        "parameters": {},
        "description": "pH 偏低，用于观察酸性环境对代谢和健康度的影响。",
    },
    "毒素暴露": {
        "cell": {"glucose": 65.0, "oxygen": 75.0, "atp": 50.0, "mitochondria": 5, "toxin": 55.0},
        "parameters": {},
        "description": "毒素水平较高，会抑制 ATP 生成并造成细胞损伤。",
    },
    "高渗脱水": {
        "cell": {"glucose": 65.0, "oxygen": 75.0, "atp": 50.0, "mitochondria": 5, "osmolarity": 370.0},
        "parameters": {},
        "description": "外界渗透压较高，细胞会逐步失水。",
    },
}


def new_simulation(preset_name: str = "正常培养环境") -> tuple[Cell, History]:
    """按实验预设创建细胞，并记录初始数据点。"""
    preset = PRESETS.get(preset_name, PRESETS["正常培养环境"])
    parameters = MetabolismParameters(**preset["parameters"])
    cell = Cell(**preset["cell"], parameters=parameters)
    return cell, [cell.snapshot()]


def run_steps(cell: Cell, history: History, steps: int = 1) -> int:
    """最多推进 steps 步；若细胞死亡则立即停止，并返回实际步数。"""
    completed = 0
    for _ in range(max(0, steps)):
        if not cell.alive:
            break
        cell.step()
        history.append(cell.snapshot())
        completed += 1
    return completed


def cell_status(cell: Cell) -> tuple[str, str]:
    """按最严重问题优先，返回状态文字与 Streamlit 提示级别。"""
    if not cell.alive:
        return "细胞死亡", "error"
    if cell.health <= 20:
        return "细胞濒死", "error"
    if cell.atp <= 8:
        return "ATP 耗竭", "error"
    if cell.oxygen <= 8:
        return "严重缺氧", "error"
    if cell.ph <= 6.6 or cell.ph >= 8.2:
        return "严重 pH 异常", "error"
    if cell.toxin >= 70:
        return "严重毒性损伤", "error"
    if cell.water_balance <= 20:
        return "细胞严重脱水", "error"
    if cell.water_balance >= 80:
        return "细胞严重肿胀", "error"
    if cell.lactate >= 65:
        return "乳酸堆积", "warning"
    if cell.atp < 30:
        return "能量不足", "warning"
    if cell.oxygen < cell.parameters.hypoxia_threshold:
        return "轻度缺氧", "warning"
    if not 7.1 <= cell.ph <= 7.7:
        return "pH 异常", "warning"
    if cell.toxin >= 20:
        return "毒素暴露", "warning"
    if cell.water_balance < 35:
        return "细胞脱水", "warning"
    if cell.water_balance > 65:
        return "细胞肿胀", "warning"
    return "状态正常", "success"

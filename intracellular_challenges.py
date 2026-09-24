"""细胞内状态互动挑战的可解释判定规则。

挑战用于引导用户观察模型内既有状态的时间顺序；阈值均为演示性规则，
并非细胞系通用质量标准或实验放行标准。
"""

from typing import Any


CHALLENGES: dict[str, dict[str, Any]] = {
    "oxidative_recovery": {
        "title": "氧化应激恢复",
        "description": "施加一次 ROS/DNA 损伤脉冲后，观察抗氧化响应与后续培养能否恢复稳态。",
        "starter": "oxidative_stress",
        "requirements": [
            ("ros_percent", "ROS", "at_most", 25.0),
            ("dna_damage_percent", "DNA 损伤", "at_most", 15.0),
            ("apoptosis_signal_percent", "凋亡信号", "at_most", 18.0),
        ],
    },
    "proteostasis_recovery": {
        "title": "蛋白稳态恢复",
        "description": "提高内质网压力后，追踪蛋白合成、自噬代理指标与能量状态。",
        "starter": "er_stress",
        "requirements": [
            ("er_stress_percent", "内质网应激", "at_most", 22.0),
            ("protein_synthesis_percent", "蛋白合成", "at_least", 62.0),
            ("atp_percent", "ATP", "at_least", 60.0),
        ],
    },
    "energy_checkpoint": {
        "title": "能量检查点",
        "description": "在低能量起点下，观察线粒体膜电位、ATP 与细胞周期推进的耦合趋势。",
        "starter": "energy_stress",
        "requirements": [
            ("mitochondrial_potential_percent", "线粒体膜电位", "at_least", 70.0),
            ("atp_percent", "ATP", "at_least", 65.0),
            ("cycle_progress_percent", "细胞周期进度", "at_least", 20.0),
        ],
    },
}


def evaluate_challenge(challenge_key: str, snapshot: dict[str, float | str]) -> dict[str, Any]:
    """按演示阈值返回可渲染的任务进度，不改变模拟状态。"""

    challenge = CHALLENGES[challenge_key]
    checks = []
    for metric, label, direction, threshold in challenge["requirements"]:
        value = float(snapshot[metric])
        passed = value <= threshold if direction == "at_most" else value >= threshold
        operator = "≤" if direction == "at_most" else "≥"
        checks.append({
            "label": label,
            "metric": metric,
            "value": value,
            "threshold": threshold,
            "operator": operator,
            "passed": passed,
        })
    passed_count = sum(check["passed"] for check in checks)
    return {
        "title": challenge["title"],
        "description": challenge["description"],
        "checks": checks,
        "progress": passed_count / len(checks),
        "completed": passed_count == len(checks),
    }

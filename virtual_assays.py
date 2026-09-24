"""由模型相对指数生成的演示性虚拟检测读出。

这些数值不是仪器校准值、标准曲线或真实实验结果，只用于让用户比较同一
模拟内不同干预时点的相对趋势。检测名称与读出方向参考常见实验用途，线性
映射、单位和噪声模型均为 C 级演示规则。
"""

from random import Random
from typing import Any


ASSAYS: dict[str, dict[str, str]] = {
    "atp_luminescence": {
        "label": "ATP 发光读出", "metric": "ATP_percent", "unit": "相对发光单位 (RLU)",
        "note": "仅保留 ATP 代理指标的相对趋势，不代表 ATP 浓度或试剂盒标准曲线。",
    },
    "mitochondrial_probe": {
        "label": "线粒体膜电位探针", "metric": "mitochondrial_potential_percent", "unit": "红/绿相对比值",
        "note": "仅演示膜电位变化方向，不对应任一荧光探针或补偿流程。",
    },
    "ros_fluorescence": {
        "label": "ROS 荧光读出", "metric": "ROS_percent", "unit": "相对荧光单位 (RFU)",
        "note": "不包含探针特异性、光漂白、细胞数归一化或背景扣除。",
    },
    "er_stress_reporter": {
        "label": "内质网应激报告", "metric": "ER_stress_percent", "unit": "相对报告信号 (RLU)",
        "note": "不等价于 UPR 单通路或具体报告基因实验。",
    },
    "autophagy_indicator": {
        "label": "自噬指示信号", "metric": "autophagy_percent", "unit": "相对荧光单位 (RFU)",
        "note": "不是自噬通量；真实实验需结合 LC3/p62 与溶酶体抑制条件。",
    },
    "apoptosis_probe": {
        "label": "凋亡探针阳性率", "metric": "apoptosis_signal_percent", "unit": "% 阳性（演示）",
        "note": "不等价于 Annexin V/PI、caspase 或形态学判读。",
    },
}


def assay_base_value(assay_key: str, snapshot: dict[str, float | str]) -> float:
    """将内部相对指数映射为仅用于展示的合成读出基线。"""

    metric = ASSAYS[assay_key]["metric"]
    index = float(snapshot[metric])
    if assay_key == "atp_luminescence":
        return 1_000.0 * index
    if assay_key == "mitochondrial_probe":
        return 0.15 + 0.032 * index
    if assay_key in {"ros_fluorescence", "er_stress_reporter", "autophagy_indicator"}:
        return 10.0 * index
    return index


def simulate_virtual_assay(
    assay_key: str,
    snapshot: dict[str, float | str],
    *,
    replicates: int = 3,
    noise_percent: float = 5.0,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """返回可导出的合成重复孔；相同输入和 seed 保持可复现。"""

    if assay_key not in ASSAYS:
        raise KeyError(f"未知虚拟检测：{assay_key}")
    replicates = max(1, min(12, int(replicates)))
    noise_percent = max(0.0, min(30.0, float(noise_percent)))
    assay = ASSAYS[assay_key]
    base = assay_base_value(assay_key, snapshot)
    rng = Random(seed)
    return [
        {
            "assay": assay["label"],
            "replicate": index + 1,
            "value": round(max(0.0, base * (1.0 + rng.gauss(0.0, noise_percent / 100.0))), 4),
            "unit": assay["unit"],
            "source_metric": assay["metric"],
            "source_index_percent": round(float(snapshot[assay["metric"]]), 4),
            "is_synthetic_demo": True,
        }
        for index in range(replicates)
    ]

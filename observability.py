"""将细胞内部相对指数连接到可验证的实验读出。"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Observable:
    model_metric: str
    suggested_readout: str
    interpretation_boundary: str
    evidence_keys: Tuple[str, ...]


OBSERVABLES: Tuple[Observable, ...] = (
    Observable("ATP 水平", "ATP 发光法或经验证的 ATP 荧光探针", "模型百分比不是 ATP 浓度、ATP/ADP 比或能量通量。", ("redox_mito",)),
    Observable("线粒体膜电位", "TMRE/TMRM；或经适当对照验证的 JC-1", "模型百分比不是 mV；染料负载、细胞数与膜完整性会影响读数。", ("redox_mito",)),
    Observable("ROS", "通用 ROS 探针与线粒体 ROS 探针分开设计，并设阳/阴性对照", "不能由单一染料区分全部 ROS 物种、来源或氧化损伤。", ("redox_mito",)),
    Observable("DNA 损伤", "γH2AX 免疫荧光/免疫印迹；按问题选择彗星实验", "模型指数不是双链断裂数、彗星尾矩或修复动力学。", ("dna_damage",)),
    Observable("内质网应激", "联合检测 BiP/GRP78、CHOP、XBP1 剪接或 PERK-eIF2α 通路标志物", "单个标志物不能完整代表 UPR 三条分支或应激持续时间。", ("upr",)),
    Observable("自噬", "LC3 与 p62 联合，并在有/无溶酶体抑制条件下评估通量", "LC3 点或单次蛋白水平不等于自噬通量。", ("autophagy",)),
    Observable("凋亡信号", "Annexin V/PI 与 caspase-3/7 或裂解型 caspase/PARP 联合", "模型信号不是凋亡细胞百分比；需与坏死和细胞周期停滞区分。", ("dna_damage", "upr", "redox_mito")),
    Observable("细胞周期", "EdU 掺入结合 DNA 含量染色（PI/DAPI）或流式细胞术", "模型阶段占比是演示规则，不是实际 G1/S/G2/M 分布。", ("dna_damage",)),
)


def observability_rows() -> list[dict[str, str]]:
    return [
        {
            "模型指标": item.model_metric,
            "建议实验读出": item.suggested_readout,
            "解释边界": item.interpretation_boundary,
            "依据": "；".join(item.evidence_keys),
        }
        for item in OBSERVABLES
    ]

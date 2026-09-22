"""模型证据目录。

这里记录的是“某种关系为何被保留”，不是对当前数值参数的验证。
证据等级必须与 README 和界面使用同一含义：

* A — 直接支持：来源直接给出培养条件、细胞系属性或模型采用的关系/形式；
* B — 文献推断·待校准：方向有文献依据，但系数、阈值或适用范围未在本项目体系中拟合；
* C — 演示规则：为了交互和趋势展示设置，没有定量预测含义。
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class EvidenceReference:
    key: str
    title: str
    url: str
    source_type: str


@dataclass(frozen=True)
class EvidenceEntry:
    mechanism: str
    relationship: str
    applicability: str
    level: str
    sources: Tuple[str, ...]
    limitation: str


REFERENCES: Dict[str, EvidenceReference] = {
    "atcc_hela": EvidenceReference("atcc_hela", "ATCC HeLa CCL-2", "https://www.atcc.org/products/ccl-2", "细胞库"),
    "atcc_hek293": EvidenceReference("atcc_hek293", "ATCC 293 [HEK-293] CRL-1573", "https://www.atcc.org/products/crl-1573", "细胞库"),
    "atcc_a549": EvidenceReference("atcc_a549", "ATCC A549 CCL-185", "https://www.atcc.org/products/ccl-185", "细胞库"),
    "cellosaurus_hela": EvidenceReference("cellosaurus_hela", "Cellosaurus HeLa CVCL_0030", "https://www.cellosaurus.org/CVCL_0030", "细胞库"),
    "cellosaurus_hek293": EvidenceReference("cellosaurus_hek293", "Cellosaurus HEK293 CVCL_0045", "https://www.cellosaurus.org/CVCL_0045", "细胞库"),
    "cellosaurus_a549": EvidenceReference("cellosaurus_a549", "Cellosaurus A-549 CVCL_0023", "https://www.cellosaurus.org/CVCL_0023", "细胞库"),
    "hek_bioprocess": EvidenceReference("hek_bioprocess", "Preliminary studies of cell culture strategies for HEK293 cells", "https://pmc.ncbi.nlm.nih.gov/articles/PMC3980760/", "同行评议论文"),
    "glucose_metabolism": EvidenceReference("glucose_metabolism", "Glucose metabolism in mammalian cell culture", "https://pubmed.ncbi.nlm.nih.gov/20691487/", "同行评议综述"),
    "metabolic_flux": EvidenceReference("metabolic_flux", "Metabolic flux and the regulation of mammalian cell growth", "https://pubmed.ncbi.nlm.nih.gov/21982705/", "同行评议综述"),
    "ph_control": EvidenceReference("ph_control", "Evidence-based guidelines for controlling pH in mammalian live-cell culture systems", "https://pubmed.ncbi.nlm.nih.gov/31044169/", "同行评议论文"),
    "acidification": EvidenceReference("acidification", "Warburg-associated acidification represses lactic fermentation", "https://pmc.ncbi.nlm.nih.gov/articles/PMC10584866/", "同行评议论文"),
    "oxygen_culture": EvidenceReference("oxygen_culture", "Supraphysiological Oxygen Levels in Mammalian Cell Culture", "https://pubmed.ncbi.nlm.nih.gov/36231085/", "同行评议综述"),
    "osmolality": EvidenceReference("osmolality", "Effect of osmolarity on CHO-cell metabolism and morphology", "https://pubmed.ncbi.nlm.nih.gov/19002978/", "同行评议论文"),
    "contact_inhibition": EvidenceReference("contact_inhibition", "Contact inhibition controls survival and proliferation via YAP/TAZ-autophagy", "https://pubmed.ncbi.nlm.nih.gov/30054475/", "同行评议论文"),
    "ic50": EvidenceReference("ic50", "Guidelines for accurate EC50/IC50 estimation", "https://pubmed.ncbi.nlm.nih.gov/22328315/", "同行评议方法论文"),
    "redox_mito": EvidenceReference("redox_mito", "Redox regulation of mitochondrial function", "https://pubmed.ncbi.nlm.nih.gov/22146081/", "同行评议综述"),
    "upr": EvidenceReference("upr", "The unfolded protein response: from stress pathway to homeostatic regulation", "https://pubmed.ncbi.nlm.nih.gov/22116877/", "同行评议综述"),
    "dna_damage": EvidenceReference("dna_damage", "The DNA-damage response in human biology and disease", "https://pubmed.ncbi.nlm.nih.gov/19847258/", "同行评议综述"),
    "autophagy": EvidenceReference("autophagy", "Guidelines for monitoring autophagy (4th edition)", "https://pubmed.ncbi.nlm.nih.gov/33634751/", "同行评议指南"),
}


EVIDENCE_ENTRIES: Tuple[EvidenceEntry, ...] = (
    EvidenceEntry("细胞系身份与培养条件", "培养基、血清、37°C、5% CO₂及贴壁属性按细胞库记录配置。", "指定的 HeLa、HEK-293、A549；具体批次仍以产品说明为准。", "A 直接支持", ("atcc_hela", "atcc_hek293", "atcc_a549", "cellosaurus_hela", "cellosaurus_hek293", "cellosaurus_a549"), "培养基品牌、血清批次、传代数会改变表型。"),
    EvidenceEntry("增殖动力学", "μmax = ln(2)/倍增时间；环境修正后按指数增殖。", "对数生长期的群体平均近似。", "B 文献推断·待校准", ("atcc_a549", "cellosaurus_hela", "hek_bioprocess"), "HeLa/A549 基线有来源；HEK-293 倍增时间及所有环境修正系数需同体系拟合。"),
    EvidenceEntry("死亡动力学", "基础死亡率叠加营养、环境和药物应激。", "仅用于定性比较。", "C 演示规则", (), "加和形式、阈值与系数均未以实验数据校准。"),
    EvidenceEntry("葡萄糖/谷氨酰胺消耗", "摄取量按平均活细胞数×比摄取率×时间积分；营养限制方向符合培养代谢。", "二维哺乳动物细胞培养的简化物料衡算。", "B 文献推断·待校准", ("glucose_metabolism", "metabolic_flux", "hek_bioprocess"), "各细胞系比摄取率和 Monod 半饱和常数是先验，不是通用测量值。"),
    EvidenceEntry("乳酸生成与 pH", "乳酸按葡萄糖消耗的表观产率生成；乳酸酸负荷降低 pH。", "有氧糖酵解占主导的培养情景。", "B 文献推断·待校准", ("glucose_metabolism", "ph_control", "acidification"), "固定产率和缓冲容量忽略其他酸碱物种及代谢重编程。"),
    EvidenceEntry("氧消耗与传递", "细胞消耗氧；培养环境以一阶传质项向设定值恢复。", "充分混合的单室近似。", "B 文献推断·待校准", ("oxygen_culture", "hek_bioprocess"), "氧百分比是代理量；OUR、kLa、液深和探头响应均需实测。"),
    EvidenceEntry("pH 与 CO₂", "以乳酸酸负荷和 CO₂ 偏移改变 pH；接近生理 pH 时生长较优。", "碳酸氢盐缓冲培养基的定性趋势。", "B 文献推断·待校准", ("ph_control",), "未显式求解 Henderson–Hasselbalch 平衡；0.006 系数为演示参数。"),
    EvidenceEntry("温度", "偏离 37°C 时降低生长修正项。", "当前三种人源贴壁细胞的演示范围。", "B 文献推断·待校准", ("atcc_hela", "atcc_hek293", "atcc_a549"), "37°C 推荐条件有直接来源；高斯响应宽度没有细胞系特异数据。"),
    EvidenceEntry("渗透压", "偏离 300 mOsm/kg 时降低生长修正项。", "从 CHO 结果外推到人源贴壁细胞。", "B 文献推断·待校准", ("osmolality",), "跨细胞系外推；最适值与高斯宽度待测。"),
    EvidenceEntry("药物浓度", "Hill/IC50 抑制项表示浓度—效应；IC50 为上下平台中点。", "只有用户输入同细胞系、同终点、同暴露时间参数时才可解释。", "A 直接支持", ("ic50",), "默认 IC50、Hill 系数及药物一阶衰减均为待校准先验。"),
    EvidenceEntry("汇合度/接触抑制", "随 N/K 增加线性降低增殖能力。", "贴壁单层培养的简化近似；肿瘤细胞可能部分失去接触抑制。", "B 文献推断·待校准", ("contact_inhibition",), "YAP/TAZ 方向有支持，线性 1−N/K 形式和 K 值未直接验证。"),
    EvidenceEntry("ATP与线粒体膜电位", "氧、温度、药物影响膜电位；膜电位与糖酵解共同影响 ATP 指数。", "代表性单细胞功能指数。", "B 文献推断·待校准", ("redox_mito",), "百分比不是 ATP 浓度或膜电位 mV；权重和时间常数为演示参数。"),
    EvidenceEntry("ROS、DNA 损伤与凋亡", "氧化/药物应激提高 ROS；高 ROS 关联损伤、线粒体失稳和死亡信号。", "趋势探索，不表示特定 ROS 物种或损伤灶。", "B 文献推断·待校准", ("redox_mito", "dna_damage"), "阈值、加权和修复速率为演示参数；不能据此判定真实凋亡。"),
    EvidenceEntry("内质网应激", "营养/药物/氧化应激提高 ER 应激；持续未缓解 UPR 可转向凋亡。", "代表性 UPR 功能指数。", "B 文献推断·待校准", ("upr",), "未分别建模 IRE1、PERK、ATF6；权重与阈值未校准。"),
    EvidenceEntry("自噬", "能量不足和 ER 应激提高自噬指数。", "只表示调节方向。", "B 文献推断·待校准", ("autophagy", "upr"), "单一指数不等于自噬通量；必须用多指标与通量实验验证。"),
    EvidenceEntry("细胞周期", "G1→S→G2→M 顺序推进，严重凋亡/能量不足时停止。", "交互展示。", "C 演示规则", (), "45/30/17/8% 的阶段占比及推进速度没有针对三种细胞系校准。"),
    EvidenceEntry("界面干预与状态徽标", "氧化刺激、抗氧化响应、颜色阈值和动画提供即时可视反馈。", "教学与交互。", "C 演示规则", (), "不代表药剂剂量、反应时间或临床/实验分级。"),
)


def evidence_rows() -> list[dict[str, str]]:
    """生成适合 Streamlit/测试展示的表格记录。"""

    rows = []
    for entry in EVIDENCE_ENTRIES:
        source_titles = "；".join(REFERENCES[key].title for key in entry.sources) or "无直接来源"
        rows.append({
            "模拟机制": entry.mechanism,
            "数学/逻辑关系": entry.relationship,
            "适用范围": entry.applicability,
            "证据等级": entry.level,
            "来源": source_titles,
            "当前限制": entry.limitation,
        })
    return rows

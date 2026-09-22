"""文献驱动的细胞系配置。

培养条件来自公开细胞库；动力学参数中，凡是缺少同一培养体系下直接测量值的
项目都标记为 ``starter_prior``，只能作为拟合初值，不能当作实验测量结果。
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Reference:
    """一个可追溯的数据来源。"""

    title: str
    url: str
    note: str


@dataclass(frozen=True)
class CellProfile:
    """细胞系的培养条件和动力学先验。"""

    key: str
    display_name: str
    organism: str
    tissue: str
    disease: str
    morphology: str
    growth_mode: str
    medium: str
    serum_percent: float
    temperature_c: float
    co2_percent: float
    initial_glucose_mm: float
    initial_glutamine_mm: float
    doubling_time_h: float
    seeding_density_cell_cm2: float
    max_density_cell_cm2: float
    glucose_uptake_pmol_cell_h: float
    glutamine_uptake_pmol_cell_h: float
    lactate_yield_mol_per_mol_glucose: float
    oxygen_uptake_pmol_cell_h: float
    reference_status: str
    references: Tuple[Reference, ...]


ATCC_HELA = Reference(
    "ATCC HeLa CCL-2",
    "https://www.atcc.org/products/ccl-2",
    "EMEM + 10% FBS，37°C，5% CO₂；贴壁生长；建议 1:2–1:6 传代。",
)
ATCC_HEK293 = Reference(
    "ATCC 293 [HEK-293] CRL-1573",
    "https://www.atcc.org/products/crl-1573",
    "EMEM + 10% FBS，37°C，5% CO₂；建议接种 1–4×10⁴ cells/cm²。",
)
ATCC_A549 = Reference(
    "ATCC A549 CCL-185",
    "https://www.atcc.org/products/ccl-185",
    "F-12K + 10% FBS，37°C，5% CO₂；群体倍增时间约 22 h。",
)
CELLOSAURUS_HELA = Reference(
    "Cellosaurus HeLa CVCL_0030",
    "https://www.cellosaurus.org/CVCL_0030",
    "细胞系标识 RRID:CVCL_0030；记录倍增时间 1.3 天（不同来源/条件可不同）。",
)
CELLOSAURUS_HEK293 = Reference(
    "Cellosaurus HEK293 CVCL_0045",
    "https://www.cellosaurus.org/CVCL_0045",
    "细胞系标识 RRID:CVCL_0045；用于身份追溯，不作为本模型动力学参数来源。",
)
CELLOSAURUS_A549 = Reference(
    "Cellosaurus A-549 CVCL_0023",
    "https://www.cellosaurus.org/CVCL_0023",
    "细胞系标识 RRID:CVCL_0023；用于身份追溯。",
)
ACIDIFICATION_PAPER = Reference(
    "Warburg-associated acidification represses lactic fermentation",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC10584866/",
    "HEK 和 HeLa 体系中，酸化显著降低葡萄糖消耗与乳酸生成。",
)
HEK_BIOPROCESS_PAPER = Reference(
    "Preliminary studies of cell culture strategies for HEK293 cells",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC3980760/",
    "报告 HEK293 培养中的细胞生长、葡萄糖、乳酸与溶氧控制。",
)


CELL_PROFILES: Dict[str, CellProfile] = {
    "hela": CellProfile(
        key="hela", display_name="HeLa（宫颈癌）", organism="Homo sapiens",
        tissue="宫颈", disease="腺癌", morphology="上皮样，贴壁", growth_mode="adherent",
        medium="EMEM + 10% FBS", serum_percent=10.0, temperature_c=37.0,
        co2_percent=5.0, initial_glucose_mm=5.5, initial_glutamine_mm=2.0,
        doubling_time_h=31.2, seeding_density_cell_cm2=1.5e4,
        max_density_cell_cm2=1.0e5, glucose_uptake_pmol_cell_h=0.22,
        glutamine_uptake_pmol_cell_h=0.035,
        lactate_yield_mol_per_mol_glucose=1.75, oxygen_uptake_pmol_cell_h=0.08,
        reference_status="培养条件及 31.2 h 倍增时间有来源；代谢速率为待校准先验",
        references=(ATCC_HELA, CELLOSAURUS_HELA, ACIDIFICATION_PAPER),
    ),
    "hek293": CellProfile(
        key="hek293", display_name="HEK-293（人胚肾来源细胞系）", organism="Homo sapiens",
        tissue="胚胎肾来源", disease="转化细胞系", morphology="上皮样，贴壁",
        growth_mode="adherent", medium="EMEM + 10% FBS", serum_percent=10.0,
        temperature_c=37.0, co2_percent=5.0, initial_glucose_mm=5.5,
        initial_glutamine_mm=2.0, doubling_time_h=30.0,
        seeding_density_cell_cm2=2.0e4, max_density_cell_cm2=7.0e4,
        glucose_uptake_pmol_cell_h=0.18, lactate_yield_mol_per_mol_glucose=1.65,
        glutamine_uptake_pmol_cell_h=0.040,
        oxygen_uptake_pmol_cell_h=0.10,
        reference_status="培养条件/密度有来源；倍增及代谢速率为待校准先验",
        references=(ATCC_HEK293, CELLOSAURUS_HEK293, HEK_BIOPROCESS_PAPER, ACIDIFICATION_PAPER),
    ),
    "a549": CellProfile(
        key="a549", display_name="A549（肺腺癌）", organism="Homo sapiens",
        tissue="肺", disease="肺癌", morphology="上皮样，贴壁", growth_mode="adherent",
        medium="F-12K + 10% FBS", serum_percent=10.0, temperature_c=37.0,
        co2_percent=5.0, initial_glucose_mm=10.0, initial_glutamine_mm=2.0,
        doubling_time_h=22.0, seeding_density_cell_cm2=1.0e4,
        max_density_cell_cm2=7.0e4, glucose_uptake_pmol_cell_h=0.20,
        glutamine_uptake_pmol_cell_h=0.032,
        lactate_yield_mol_per_mol_glucose=1.70, oxygen_uptake_pmol_cell_h=0.09,
        reference_status="培养条件、密度和倍增时间有来源；代谢速率为待校准先验",
        references=(ATCC_A549, CELLOSAURUS_A549),
    ),
}


def get_profile(key: str) -> CellProfile:
    """按键名返回细胞配置，未知键名回退到 HeLa。"""

    return CELL_PROFILES.get(key, CELL_PROFILES["hela"])

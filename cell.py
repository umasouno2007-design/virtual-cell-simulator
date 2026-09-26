"""单位明确、可校准的细胞培养动力学模型。"""

from dataclasses import dataclass
from math import exp, isfinite, log
from typing import Dict

from profiles import CellProfile, get_profile


def _finite_nonnegative(value: float, fallback: float = 0.0) -> float:
    """将外部数值限制为有限非负数，防止状态快照出现 NaN/无穷大。"""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if isfinite(number) and number >= 0.0 else fallback


@dataclass
class ModelParameters:
    """可由实验数据拟合的模型参数。

    所有默认值均是启动模拟用先验，而不是三种细胞系的已验证常数。证据边界与
    来源见 ``evidence.py``；尤其是半饱和常数、死亡项、kLa、缓冲能力和药物
    衰减必须由同一培养体系的数据重新估计。
    """

    growth_scale: float = 1.0
    uptake_scale: float = 1.0
    death_rate_per_h: float = 0.001
    glucose_half_saturation_mm: float = 0.5
    glutamine_half_saturation_mm: float = 0.12
    oxygen_half_saturation_percent: float = 3.0
    lactate_inhibition_mm: float = 20.0
    drug_ic50_um: float = 10.0
    drug_hill: float = 1.2
    oxygen_transfer_per_h: float = 0.35
    buffer_capacity_mm_per_ph: float = 25.0


class CellCulture:
    """模拟一个贴壁细胞培养孔/瓶中的细胞群体和培养液。"""

    def __init__(
        self,
        profile_key: str = "hela",
        culture_volume_ml: float = 10.0,
        surface_area_cm2: float = 25.0,
        viable_cells: float | None = None,
        parameters: ModelParameters | None = None,
    ) -> None:
        self.profile: CellProfile = get_profile(profile_key)
        self.profile_key = self.profile.key
        self.culture_volume_ml = max(0.1, _finite_nonnegative(culture_volume_ml, 0.1))
        self.surface_area_cm2 = max(0.1, _finite_nonnegative(surface_area_cm2, 0.1))
        default_viable = (
            self.profile.seeding_density_cell_cm2 * self.surface_area_cm2
        )
        self.viable_cells = default_viable if viable_cells is None else _finite_nonnegative(viable_cells)
        self.dead_cells = 0.0
        self.time_h = 0.0
        self.glucose_mm = self.profile.initial_glucose_mm
        self.glutamine_mm = self.profile.initial_glutamine_mm
        self.lactate_mm = 0.0
        self.oxygen_percent = 18.6
        self.oxygen_setpoint_percent = 18.6
        self.ph = 7.4
        self.temperature_c = self.profile.temperature_c
        self.co2_percent = self.profile.co2_percent
        self.osmolality_mosm_kg = 300.0
        self.drug_um = 0.0
        self.energy_index = 100.0
        self.parameters = parameters or ModelParameters()
        self.last_growth_rate_per_h = 0.0
        self.last_death_rate_per_h = 0.0

    @property
    def total_cells(self) -> float:
        return self.viable_cells + self.dead_cells

    @property
    def viability_percent(self) -> float:
        if self.total_cells <= 0:
            return 0.0
        return min(100.0, max(0.0, 100.0 * self.viable_cells / self.total_cells))

    @property
    def carrying_capacity(self) -> float:
        return self.profile.max_density_cell_cm2 * self.surface_area_cm2

    @property
    def confluence_percent(self) -> float:
        return min(100.0, 100.0 * self.viable_cells / self.carrying_capacity)

    @property
    def alive(self) -> bool:
        return self.viable_cells >= 1.0 and self.viability_percent > 1.0

    def growth_modifiers(self) -> Dict[str, float]:
        """返回环境修正系数。

        营养/氧使用 Monod 型经验项、药物使用 Hill 型项；pH、温度、渗透压和
        乳酸的曲线形状及乘法组合属于待校准先验。接触抑制的方向有 YAP/TAZ
        文献支持，但线性 ``1-N/K`` 是简化，并非直接测得的机制方程。
        """

        p = self.parameters
        glucose_mm = _finite_nonnegative(self.glucose_mm)
        glutamine_mm = _finite_nonnegative(self.glutamine_mm)
        oxygen_percent = _finite_nonnegative(self.oxygen_percent)
        glucose_half = max(1e-9, _finite_nonnegative(p.glucose_half_saturation_mm, 1e-9))
        glutamine_half = max(1e-9, _finite_nonnegative(p.glutamine_half_saturation_mm, 1e-9))
        oxygen_half = max(1e-9, _finite_nonnegative(p.oxygen_half_saturation_percent, 1e-9))
        lactate_inhibition = max(1e-9, _finite_nonnegative(p.lactate_inhibition_mm, 1e-9))
        glucose = glucose_mm / (glucose_half + glucose_mm)
        glutamine = glutamine_mm / (glutamine_half + glutamine_mm)
        oxygen = oxygen_percent / (oxygen_half + oxygen_percent)
        ph = exp(-((self.ph - 7.35) / 0.38) ** 2)
        temperature = exp(-((self.temperature_c - 37.0) / 2.0) ** 2)
        osmolality = exp(-((self.osmolality_mosm_kg - 300.0) / 55.0) ** 2)
        lactate = 1.0 / (
            1.0 + (_finite_nonnegative(self.lactate_mm) / lactate_inhibition) ** 2
        )
        drug = 1.0 / (
            1.0 + (self.drug_um / max(0.001, p.drug_ic50_um)) ** p.drug_hill
        )
        contact = max(0.0, 1.0 - self.viable_cells / self.carrying_capacity)
        return {
            "glucose": glucose,
            "glutamine": glutamine,
            "oxygen": oxygen,
            "ph": ph,
            "temperature": temperature,
            "osmolality": osmolality,
            "lactate": lactate,
            "drug": drug,
            "contact": contact,
        }

    def step(self, dt_h: float = 1.0) -> None:
        """用经验动力学方程推进培养状态。实验预测前必须重新拟合参数。"""

        dt_h = _finite_nonnegative(dt_h)
        if not self.alive or dt_h <= 0:
            return
        dt_h = min(dt_h, 6.0)
        # 状态可来自 CSV/恢复文件；推进前统一裁剪，避免单个无效值污染后续历史。
        for name in ("viable_cells", "dead_cells", "glucose_mm", "glutamine_mm", "lactate_mm", "oxygen_percent", "drug_um"):
            setattr(self, name, _finite_nonnegative(getattr(self, name)))
        self.oxygen_percent = min(21.0, self.oxygen_percent)
        self.ph = min(8.0, max(6.2, _finite_nonnegative(self.ph, 7.4)))
        p = self.parameters
        modifiers = self.growth_modifiers()
        mu_max = log(2.0) / self.profile.doubling_time_h
        mu = mu_max * p.growth_scale
        for value in modifiers.values():
            mu *= value

        stress = 1.0 - min(
            modifiers["ph"], modifiers["temperature"], modifiers["osmolality"],
            modifiers["oxygen"], modifiers["drug"],
        )
        # 下列死亡阈值及加和系数属于 C 级演示规则，仅保证压力升高时方向合理。
        death_rate = p.death_rate_per_h + 0.045 * max(0.0, stress - 0.25)
        if self.glucose_mm < 0.1:
            death_rate += 0.02
        if self.glutamine_mm < 0.03:
            death_rate += 0.012
        if self.lactate_mm > 30.0:
            death_rate += 0.01 * min(2.0, (self.lactate_mm - 30.0) / 10.0)

        start_viable = self.viable_cells
        new_cells = start_viable * max(0.0, exp(mu * dt_h) - 1.0)
        deaths = min(start_viable + new_cells, start_viable * death_rate * dt_h)
        self.viable_cells = max(0.0, start_viable + new_cells - deaths)
        self.dead_cells += deaths

        average_viable = (start_viable + self.viable_cells) / 2.0
        glucose_umol = (
            average_viable * self.profile.glucose_uptake_pmol_cell_h
            * p.uptake_scale * dt_h / 1e6
        )
        glucose_umol = min(glucose_umol, self.glucose_mm * self.culture_volume_ml)
        glucose_drop_mm = glucose_umol / self.culture_volume_ml
        lactate_rise_mm = glucose_drop_mm * self.profile.lactate_yield_mol_per_mol_glucose
        self.glucose_mm = max(0.0, self.glucose_mm - glucose_drop_mm)
        self.lactate_mm += lactate_rise_mm

        glutamine_umol = (
            average_viable * self.profile.glutamine_uptake_pmol_cell_h
            * p.uptake_scale * dt_h / 1e6
        )
        glutamine_umol = min(
            glutamine_umol, self.glutamine_mm * self.culture_volume_ml
        )
        self.glutamine_mm = max(
            0.0, self.glutamine_mm - glutamine_umol / self.culture_volume_ml
        )

        # 单室氧平衡；分母比例与一阶传质系数不是实测 kLa/OUR，实验使用前需拟合。
        oxygen_demand = (
            average_viable * self.profile.oxygen_uptake_pmol_cell_h
            * p.uptake_scale * dt_h / max(1.0, self.culture_volume_ml * 2.5e5)
        )
        oxygen_recovery = (
            self.oxygen_setpoint_percent - self.oxygen_percent
        ) * p.oxygen_transfer_per_h * dt_h
        self.oxygen_percent = max(
            0.0, min(21.0, self.oxygen_percent + oxygen_recovery - oxygen_demand)
        )

        # pH 是缓冲容量近似，不是完整的碳酸氢盐 Henderson–Hasselbalch 平衡。
        acid_load = lactate_rise_mm / max(1.0, p.buffer_capacity_mm_per_ph)
        co2_shift = (self.co2_percent - self.profile.co2_percent) * 0.006 * dt_h
        self.ph = max(6.2, min(8.0, self.ph - acid_load - co2_shift))

        energy = 100.0
        for key in ("glucose", "glutamine", "oxygen", "ph", "temperature", "drug"):
            energy *= modifiers[key]
        self.energy_index = max(0.0, min(100.0, energy))
        # 0.003 h⁻¹ 是演示性衰减；具体药物须使用稳定性/清除实验数据替换。
        self.drug_um = max(0.0, self.drug_um * exp(-0.003 * dt_h))
        self.time_h += dt_h
        self.last_growth_rate_per_h = mu
        self.last_death_rate_per_h = death_rate

    def exchange_medium(self, fraction: float = 1.0) -> None:
        """更换指定比例培养基，1.0 表示全量换液。"""

        fraction = max(0.0, min(1.0, fraction))
        self.glucose_mm += (self.profile.initial_glucose_mm - self.glucose_mm) * fraction
        self.glutamine_mm += (self.profile.initial_glutamine_mm - self.glutamine_mm) * fraction
        self.lactate_mm *= 1.0 - fraction
        self.drug_um *= 1.0 - fraction
        self.ph += (7.4 - self.ph) * fraction
        self.osmolality_mosm_kg += (300.0 - self.osmolality_mosm_kg) * fraction

    def add_drug(self, concentration_um: float) -> None:
        """设置药物浓度；药物效应取决于用户提供的 IC50/Hill 参数。"""

        self.drug_um = max(0.0, float(concentration_um))

    def add_glucose(self, concentration_increase_mm: float) -> None:
        """按培养液终浓度增量补充葡萄糖。"""

        self.glucose_mm = min(
            100.0,
            self.glucose_mm + max(0.0, float(concentration_increase_mm)),
        )

    def snapshot(self) -> Dict[str, float | str]:
        """返回带真实单位列名的历史记录。"""

        return {
            "time_h": self.time_h, "cell_type": self.profile_key,
            "viable_cells": self.viable_cells, "dead_cells": self.dead_cells,
            "viability_percent": self.viability_percent,
            "confluence_percent": self.confluence_percent,
            "glucose_mM": self.glucose_mm, "glutamine_mM": self.glutamine_mm,
            "lactate_mM": self.lactate_mm, "oxygen_percent": self.oxygen_percent,
            "pH": self.ph, "temperature_C": self.temperature_c,
            "CO2_percent": self.co2_percent,
            "osmolality_mOsm_kg": self.osmolality_mosm_kg,
            "drug_uM": self.drug_um, "energy_index": self.energy_index,
            "growth_rate_per_h": self.last_growth_rate_per_h,
            "death_rate_per_h": self.last_death_rate_per_h,
        }


Cell = CellCulture
MetabolismParameters = ModelParameters

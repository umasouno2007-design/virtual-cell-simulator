"""单位明确、可校准的细胞培养动力学模型。"""

from dataclasses import dataclass
from math import exp, log
from typing import Dict

from profiles import CellProfile, get_profile


@dataclass
class ModelParameters:
    """可由实验数据拟合的模型参数。"""

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
        self.culture_volume_ml = max(0.1, culture_volume_ml)
        self.surface_area_cm2 = max(0.1, surface_area_cm2)
        self.viable_cells = viable_cells or (
            self.profile.seeding_density_cell_cm2 * self.surface_area_cm2
        )
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
        return 100.0 * self.viable_cells / self.total_cells

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
        """返回各环境因子对最大生长率的无量纲修正系数。"""

        p = self.parameters
        glucose = self.glucose_mm / (p.glucose_half_saturation_mm + self.glucose_mm)
        glutamine = self.glutamine_mm / (
            p.glutamine_half_saturation_mm + self.glutamine_mm
        )
        oxygen = self.oxygen_percent / (
            p.oxygen_half_saturation_percent + self.oxygen_percent
        )
        ph = exp(-((self.ph - 7.35) / 0.38) ** 2)
        temperature = exp(-((self.temperature_c - 37.0) / 2.0) ** 2)
        osmolality = exp(-((self.osmolality_mosm_kg - 300.0) / 55.0) ** 2)
        lactate = 1.0 / (
            1.0 + (self.lactate_mm / p.lactate_inhibition_mm) ** 2
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

        if not self.alive or dt_h <= 0:
            return
        dt_h = min(float(dt_h), 6.0)
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

        acid_load = lactate_rise_mm / max(1.0, p.buffer_capacity_mm_per_ph)
        co2_shift = (self.co2_percent - self.profile.co2_percent) * 0.006 * dt_h
        self.ph = max(6.2, min(8.0, self.ph - acid_load - co2_shift))

        energy = 100.0
        for key in ("glucose", "glutamine", "oxygen", "ph", "temperature", "drug"):
            energy *= modifiers[key]
        self.energy_index = max(0.0, min(100.0, energy))
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

"""可解释的哺乳动物细胞内部状态模型。

这是连接培养环境与细胞器功能的最小模型，不试图替代全基因组代谢网络。
所有百分比均为相对功能指数，适合做趋势探索，不能直接当作实验测量值。
"""

from dataclasses import dataclass
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from cell import CellCulture


def _bounded(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class IntracellularState:
    """单个代表性细胞的功能状态。"""

    time_h: float = 0.0
    atp_percent: float = 88.0
    mitochondrial_potential_percent: float = 90.0
    glycolysis_percent: float = 45.0
    ros_percent: float = 10.0
    cytosolic_calcium_nm: float = 100.0
    dna_damage_percent: float = 2.0
    er_stress_percent: float = 5.0
    autophagy_percent: float = 10.0
    protein_synthesis_percent: float = 78.0
    growth_signal_percent: float = 72.0
    apoptosis_signal_percent: float = 2.0
    cycle_progress_percent: float = 8.0
    cycle_phase: str = "G1"

    def step(self, culture: "CellCulture", dt_h: float = 1.0) -> None:
        """根据培养环境推进细胞器与细胞命运状态。"""

        if dt_h <= 0:
            return
        dt_h = min(float(dt_h), 6.0)
        oxygen = _bounded(culture.oxygen_percent / 18.6, 0.0, 1.0)
        glucose = _bounded(culture.glucose_mm / culture.profile.initial_glucose_mm, 0.0, 1.0)
        ph_fitness = _bounded(1.0 - abs(culture.ph - 7.35) / 0.9, 0.0, 1.0)
        thermal_fitness = _bounded(1.0 - abs(culture.temperature_c - 37.0) / 6.0, 0.0, 1.0)
        drug_stress = culture.drug_um / (culture.drug_um + culture.parameters.drug_ic50_um)

        mitochondrial_target = 22.0 + 72.0 * oxygen * thermal_fitness * (1.0 - 0.45 * drug_stress)
        glycolysis_target = 18.0 + 68.0 * glucose * (1.0 + 0.28 * (1.0 - oxygen))
        self.mitochondrial_potential_percent += (mitochondrial_target - self.mitochondrial_potential_percent) * min(1.0, 0.22 * dt_h)
        self.glycolysis_percent += (glycolysis_target - self.glycolysis_percent) * min(1.0, 0.28 * dt_h)

        atp_target = (
            0.58 * self.mitochondrial_potential_percent
            + 0.34 * self.glycolysis_percent
            + 8.0 * ph_fitness
        )
        self.atp_percent += (atp_target - self.atp_percent) * min(1.0, 0.32 * dt_h)

        ros_target = 6.0 + 42.0 * (1.0 - oxygen) + 30.0 * drug_stress
        ros_target += max(0.0, 55.0 - self.mitochondrial_potential_percent) * 0.35
        self.ros_percent += (ros_target - self.ros_percent) * min(1.0, 0.26 * dt_h)

        damage_gain = max(0.0, self.ros_percent - 28.0) * 0.012 + drug_stress * 0.38
        damage_repair = max(0.0, self.atp_percent - 35.0) * 0.004
        self.dna_damage_percent += (damage_gain - damage_repair) * dt_h

        er_target = 5.0 + 36.0 * (1.0 - glucose) + 28.0 * drug_stress
        er_target += max(0.0, self.ros_percent - 35.0) * 0.25
        self.er_stress_percent += (er_target - self.er_stress_percent) * min(1.0, 0.18 * dt_h)
        autophagy_target = 8.0 + 0.42 * self.er_stress_percent + 0.35 * max(0.0, 55.0 - self.atp_percent)
        self.autophagy_percent += (autophagy_target - self.autophagy_percent) * min(1.0, 0.22 * dt_h)

        self.protein_synthesis_percent = _bounded(
            0.58 * self.atp_percent + 34.0 * glucose - 0.28 * self.er_stress_percent
        )
        self.growth_signal_percent = _bounded(
            45.0 * glucose + 32.0 * ph_fitness + 23.0 * (1.0 - culture.confluence_percent / 100.0)
        )
        apoptosis_target = _bounded(
            0.48 * self.dna_damage_percent
            + 0.34 * self.ros_percent
            + 0.30 * self.er_stress_percent
            + 0.42 * max(0.0, 35.0 - self.atp_percent)
            - 10.0
        )
        self.apoptosis_signal_percent += (apoptosis_target - self.apoptosis_signal_percent) * min(1.0, 0.16 * dt_h)

        calcium_target = 100.0 + 2.2 * self.er_stress_percent + 1.1 * self.apoptosis_signal_percent
        self.cytosolic_calcium_nm += (calcium_target - self.cytosolic_calcium_nm) * min(1.0, 0.25 * dt_h)

        if self.apoptosis_signal_percent < 70.0 and self.atp_percent > 25.0:
            speed = self.growth_signal_percent / 100.0
            self.cycle_progress_percent = (self.cycle_progress_percent + 100.0 * dt_h * speed / culture.profile.doubling_time_h) % 100.0
        self.cycle_phase = self._phase_from_progress(self.cycle_progress_percent)

        for name in (
            "atp_percent", "mitochondrial_potential_percent", "glycolysis_percent",
            "ros_percent", "dna_damage_percent", "er_stress_percent",
            "autophagy_percent", "protein_synthesis_percent", "growth_signal_percent",
            "apoptosis_signal_percent",
        ):
            setattr(self, name, _bounded(getattr(self, name)))
        self.cytosolic_calcium_nm = _bounded(self.cytosolic_calcium_nm, 50.0, 1200.0)
        self.time_h += dt_h

    @staticmethod
    def _phase_from_progress(progress: float) -> str:
        if progress < 45.0:
            return "G1"
        if progress < 75.0:
            return "S"
        if progress < 92.0:
            return "G2"
        return "M"

    def apply_oxidative_stress(self, intensity: float = 20.0) -> None:
        """施加一次可控氧化刺激，便于观察下游响应。"""

        self.ros_percent = _bounded(self.ros_percent + intensity)
        self.dna_damage_percent = _bounded(self.dna_damage_percent + intensity * 0.12)

    def apply_antioxidant_response(self, intensity: float = 15.0) -> None:
        """模拟增强抗氧化清除能力；既有 DNA 损伤仍需随时间修复。"""

        self.ros_percent = _bounded(self.ros_percent - intensity)

    def snapshot(self) -> Dict[str, float | str]:
        return {
            "time_h": self.time_h,
            "ATP_percent": self.atp_percent,
            "mitochondrial_potential_percent": self.mitochondrial_potential_percent,
            "glycolysis_percent": self.glycolysis_percent,
            "ROS_percent": self.ros_percent,
            "calcium_nM": self.cytosolic_calcium_nm,
            "DNA_damage_percent": self.dna_damage_percent,
            "ER_stress_percent": self.er_stress_percent,
            "autophagy_percent": self.autophagy_percent,
            "protein_synthesis_percent": self.protein_synthesis_percent,
            "growth_signal_percent": self.growth_signal_percent,
            "apoptosis_signal_percent": self.apoptosis_signal_percent,
            "cycle_progress_percent": self.cycle_progress_percent,
            "cycle_phase": self.cycle_phase,
        }


def intracellular_status(state: IntracellularState) -> tuple[str, str]:
    """返回代表性细胞的综合状态与 Streamlit 提示级别。"""

    if state.apoptosis_signal_percent >= 70.0:
        return "凋亡程序高度激活", "error"
    if state.atp_percent < 30.0 or state.dna_damage_percent >= 60.0:
        return "细胞稳态严重受损", "error"
    if state.ros_percent >= 45.0 or state.er_stress_percent >= 45.0:
        return "细胞应激升高", "warning"
    if state.atp_percent < 55.0:
        return "能量供应不足", "warning"
    return "细胞内部稳态", "success"

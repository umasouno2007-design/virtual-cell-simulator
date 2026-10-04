"""可解释的哺乳动物细胞内部状态模型。

这是连接培养环境与细胞器功能的最小模型，不试图替代全基因组代谢网络。
所有百分比均为相对功能指数，适合做趋势探索，不能直接当作实验测量值。
ATP/膜电位/ROS、UPR、DNA 损伤、自噬和促凋亡压力之间的调节方向有文献支持，
但本文件中的权重、阈值、时间常数和周期分段全部属于演示规则，尚未校准。
完整证据边界与来源见 ``evidence.py``。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Dict, TYPE_CHECKING

from microenvironment import MicroenvironmentState
from numeric_utils import checked_time_advance

if TYPE_CHECKING:
    from cell import CellCulture

MAX_INTERNAL_STEP_H = 0.25


def _bounded(value: float, low: float = 0.0, high: float = 100.0) -> float:
    numeric = float(value)
    return max(low, min(high, numeric)) if isfinite(numeric) else low


def _teaching_intensity(value: float) -> float:
    """Validate a relative teaching pulse, not an experimental dose."""

    if isinstance(value, bool):
        raise ValueError("教学干预强度必须是有限非负数。")
    try:
        intensity = float(value)
    except (TypeError, ValueError):
        raise ValueError("教学干预强度必须是有限非负数。") from None
    if not isfinite(intensity) or intensity < 0:
        raise ValueError("教学干预强度必须是有限非负数。")
    return intensity


@dataclass
class IntracellularState:
    """单个代表性细胞的相对功能状态，不是实验测量或细胞比例。"""

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

    def finite(self) -> bool:
        """Return whether current relative indices are finite and in model bounds."""

        percent_fields = (
            "atp_percent", "mitochondrial_potential_percent", "glycolysis_percent",
            "ros_percent", "dna_damage_percent", "er_stress_percent", "autophagy_percent",
            "protein_synthesis_percent", "growth_signal_percent", "apoptosis_signal_percent",
            "cycle_progress_percent",
        )
        values = [self.time_h, self.cytosolic_calcium_nm]
        values.extend(getattr(self, name) for name in percent_fields)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
            return False
        try:
            finite_values = all(isfinite(float(value)) for value in values)
        except OverflowError:
            return False
        if not finite_values:
            return False
        if self.time_h < 0.0 or not 50.0 <= self.cytosolic_calcium_nm <= 1200.0:
            return False
        if any(not 0.0 <= float(getattr(self, name)) <= 100.0 for name in percent_fields):
            return False
        return (
            self.cycle_phase in {"G1", "S", "G2", "M"}
            and self.cycle_phase == self._phase_from_progress(self.cycle_progress_percent)
        )

    def step(self, environment: MicroenvironmentState | "CellCulture", dt_h: float = 1.0) -> None:
        """根据培养环境推进细胞器与命运的相对指数。

        ``environment.local_oxygen_availability`` 是“局部氧可用性代理”，并不等同于
        培养箱头空间氧、培养液溶氧或组织生理氧。这里不是 ODE 生化网络，也不
        输出 ATP 浓度、膜电位 mV、自噬通量、DNA 损伤灶数或凋亡细胞比例。
        所有线性组合只用于产生可解释的趋势与交互反馈。乳酸值随环境快照保存，
        但当前没有被单细胞状态方程直接使用；其酸碱影响需通过独立 pH 输入表达。
        合法推进按不超过 0.25 h 的内部子步执行，与条件沙盒使用的数值步长一致，
        以减少同一时长因调用方式不同而产生的离散差异；这不是实验采样频率建议。
        """

        if isinstance(dt_h, bool):
            raise ValueError("单细胞单步时长必须是 0–6 h 内的有限数值。")
        try:
            dt_h = float(dt_h)
        except (TypeError, ValueError):
            raise ValueError("单细胞单步时长必须是 0–6 h 内的有限数值。") from None
        if not isfinite(dt_h) or dt_h < 0.0:
            raise ValueError("单细胞单步时长必须是 0–6 h 内的有限数值。")
        if dt_h > 6.0:
            raise ValueError("单细胞单步时长不能超过 6 h；请分步推进。")
        if dt_h == 0.0:
            return
        if not self.finite():
            raise ValueError("单细胞状态包含越界或非有限值；请重置或载入有效状态。")
        next_time_h = checked_time_advance(self.time_h, dt_h)
        if dt_h > MAX_INTERNAL_STEP_H:
            remaining_h = dt_h
            while remaining_h > 1e-12:
                substep_h = min(MAX_INTERNAL_STEP_H, remaining_h)
                self.step(environment, substep_h)
                remaining_h -= substep_h
            return
        # 兼容旧调用：现有培养工作流继续传入 CellCulture；新单细胞/微群体只传入环境。
        microenvironment = (
            environment.normalized_copy() if isinstance(environment, MicroenvironmentState)
            else MicroenvironmentState.from_culture(environment)
        )
        local_oxygen_availability = microenvironment.local_oxygen_availability
        glucose = _bounded(
            microenvironment.glucose_mm / microenvironment.glucose_reference_mm,
            0.0, 1.0,
        )
        ph_fitness = _bounded(1.0 - abs(microenvironment.ph - 7.35) / 0.9, 0.0, 1.0)
        thermal_fitness = _bounded(1.0 - abs(microenvironment.temperature_c - 37.0) / 6.0, 0.0, 1.0)
        drug_stress = microenvironment.drug_um / (microenvironment.drug_um + microenvironment.drug_ic50_um)

        mitochondrial_target = 22.0 + 72.0 * local_oxygen_availability * thermal_fitness * (1.0 - 0.45 * drug_stress)
        # 低氧下的糖酵解补偿是方向性教学规则，不能解读为任意细胞系的定量通量。
        glycolysis_target = 18.0 + 68.0 * glucose * (1.0 + 0.28 * (1.0 - local_oxygen_availability))
        self.mitochondrial_potential_percent += (mitochondrial_target - self.mitochondrial_potential_percent) * min(1.0, 0.22 * dt_h)
        self.glycolysis_percent += (glycolysis_target - self.glycolysis_percent) * min(1.0, 0.28 * dt_h)

        atp_target = (
            0.58 * self.mitochondrial_potential_percent
            + 0.34 * self.glycolysis_percent
            + 8.0 * ph_fitness
        )
        self.atp_percent += (atp_target - self.atp_percent) * min(1.0, 0.32 * dt_h)

        # 不将“氧越低→ROS 必然越高”写成直接单调规则：低氧、复氧、细胞系、
        # 暴露时间和抗氧化能力均可改变 ROS 方向。这里只保留药物与既有线粒体
        # 功能失衡的教学性压力项，ROS 本身仍是相对红氧状态指数。
        ros_target = 6.0 + 30.0 * drug_stress
        ros_target += max(0.0, 55.0 - self.mitochondrial_potential_percent) * 0.35
        self.ros_percent += (ros_target - self.ros_percent) * min(1.0, 0.26 * dt_h)

        damage_gain = max(0.0, self.ros_percent - 28.0) * 0.012 + drug_stress * 0.38
        damage_repair = max(0.0, self.atp_percent - 35.0) * 0.004
        self.dna_damage_percent += (damage_gain - damage_repair) * dt_h

        er_target = 5.0 + 36.0 * (1.0 - glucose) + 28.0 * drug_stress
        er_target += max(0.0, self.ros_percent - 35.0) * 0.25
        self.er_stress_percent += (er_target - self.er_stress_percent) * min(1.0, 0.18 * dt_h)
        # 自噬指数表示适应/回收压力，并不区分保护性自噬、受损自噬或自噬依赖死亡。
        autophagy_target = 8.0 + 0.42 * self.er_stress_percent + 0.35 * max(0.0, 55.0 - self.atp_percent)
        self.autophagy_percent += (autophagy_target - self.autophagy_percent) * min(1.0, 0.22 * dt_h)

        self.protein_synthesis_percent = _bounded(
            0.58 * self.atp_percent + 34.0 * glucose - 0.28 * self.er_stress_percent
        )
        self.growth_signal_percent = _bounded(
            45.0 * glucose + 32.0 * ph_fitness + 23.0 * (1.0 - microenvironment.local_confluence_percent / 100.0)
        )
        # 促凋亡压力相对指数，不是凋亡阳性细胞比例、caspase 活性或死亡结局。
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
            self.cycle_progress_percent = (self.cycle_progress_percent + 100.0 * dt_h * speed / microenvironment.doubling_time_h) % 100.0
        self.cycle_phase = self._phase_from_progress(self.cycle_progress_percent)

        for name in (
            "atp_percent", "mitochondrial_potential_percent", "glycolysis_percent",
            "ros_percent", "dna_damage_percent", "er_stress_percent",
            "autophagy_percent", "protein_synthesis_percent", "growth_signal_percent",
            "apoptosis_signal_percent",
        ):
            setattr(self, name, _bounded(getattr(self, name)))
        self.cytosolic_calcium_nm = _bounded(self.cytosolic_calcium_nm, 50.0, 1200.0)
        self.time_h = next_time_h

    @staticmethod
    def _phase_from_progress(progress: float) -> str:
        # 阶段顺序符合细胞周期定义；45/30/17/8% 的时长占比是 C 级演示规则。
        if progress < 45.0:
            return "G1"
        if progress < 75.0:
            return "S"
        if progress < 92.0:
            return "G2"
        return "M"

    def apply_oxidative_stress(self, intensity: float = 20.0) -> None:
        """施加一次教学性氧化压力脉冲，便于观察相对状态的下游趋势。"""

        intensity = _teaching_intensity(intensity)
        self.ros_percent = _bounded(self.ros_percent + intensity)
        self.dna_damage_percent = _bounded(self.dna_damage_percent + intensity * 0.12)

    def apply_antioxidant_response(self, intensity: float = 15.0) -> None:
        """模拟增强抗氧化清除能力；既有 DNA 损伤代理仍需随时间恢复。"""

        intensity = _teaching_intensity(intensity)
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
        return "促凋亡压力相对指数高", "error"
    if state.atp_percent < 30.0 or state.dna_damage_percent >= 60.0:
        return "细胞稳态严重受损", "error"
    if state.ros_percent >= 45.0 or state.er_stress_percent >= 45.0:
        return "细胞应激升高", "warning"
    if state.atp_percent < 55.0:
        return "能量供应不足", "warning"
    return "细胞内部稳态", "success"

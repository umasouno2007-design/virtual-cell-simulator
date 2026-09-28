"""细胞内部状态与培养环境耦合的回归测试。"""

import unittest

from cell import CellCulture
from intracellular import IntracellularState, intracellular_status


class IntracellularStateTestCase(unittest.TestCase):
    def test_low_oxygen_reduces_mitochondrial_function_and_atp_without_forcing_ros_direction(self) -> None:
        control_culture = CellCulture("hela")
        hypoxic_culture = CellCulture("hela")
        hypoxic_culture.oxygen_percent = 0.5
        control = IntracellularState()
        hypoxic = IntracellularState()

        for _ in range(12):
            control.step(control_culture, 1.0)
            hypoxic.step(hypoxic_culture, 1.0)

        self.assertLess(
            hypoxic.mitochondrial_potential_percent,
            control.mitochondrial_potential_percent,
        )
        self.assertLess(hypoxic.atp_percent, control.atp_percent)
        # ROS 方向取决于暴露、复氧、药物和抗氧化背景；模型不再把低氧直接写成
        # 单调 ROS 增加规则。
        self.assertGreaterEqual(hypoxic.ros_percent, 0.0)
        self.assertLessEqual(hypoxic.ros_percent, 100.0)

    def test_low_oxygen_has_no_direct_monotonic_ros_term(self) -> None:
        control_culture = CellCulture("hela")
        low_oxygen_culture = CellCulture("hela")
        low_oxygen_culture.oxygen_percent = 0.5
        control = IntracellularState()
        low_oxygen = IntracellularState()

        # 一步后已能看到膜电位目标不同；ROS 仍相同，证明模型没有把氧变量
        # 直接作为“越低越高”的 ROS 加项。后续 ROS 可受线粒体状态等间接因素影响。
        control.step(control_culture, 1.0)
        low_oxygen.step(low_oxygen_culture, 1.0)
        self.assertLess(
            low_oxygen.mitochondrial_potential_percent,
            control.mitochondrial_potential_percent,
        )
        self.assertAlmostEqual(low_oxygen.ros_percent, control.ros_percent, places=8)

    def test_drug_exposure_increases_damage_and_apoptosis_signal(self) -> None:
        culture = CellCulture("a549")
        culture.parameters.drug_ic50_um = 2.0
        culture.add_drug(20.0)
        state = IntracellularState()

        for _ in range(24):
            state.step(culture, 1.0)

        self.assertGreater(state.dna_damage_percent, 2.0)
        self.assertGreater(state.apoptosis_signal_percent, 2.0)

    def test_cycle_phase_follows_progress(self) -> None:
        self.assertEqual(IntracellularState._phase_from_progress(20.0), "G1")
        self.assertEqual(IntracellularState._phase_from_progress(60.0), "S")
        self.assertEqual(IntracellularState._phase_from_progress(80.0), "G2")
        self.assertEqual(IntracellularState._phase_from_progress(95.0), "M")

    def test_oxidative_stress_and_antioxidant_response(self) -> None:
        state = IntracellularState()
        state.apply_oxidative_stress(20.0)
        stressed_ros = state.ros_percent
        self.assertGreater(state.dna_damage_percent, 2.0)
        state.apply_antioxidant_response(15.0)
        self.assertLess(state.ros_percent, stressed_ros)

    def test_status_reports_severe_apoptosis(self) -> None:
        state = IntracellularState(apoptosis_signal_percent=75.0)
        self.assertEqual(intracellular_status(state), ("促凋亡压力相对指数高", "error"))


if __name__ == "__main__":
    unittest.main()

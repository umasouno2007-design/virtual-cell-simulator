"""细胞内部状态与培养环境耦合的回归测试。"""

import unittest
from itertools import product
from math import isfinite, isnan

from cell import CellCulture
from intracellular import IntracellularState, intracellular_status
from microenvironment import MicroenvironmentState


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

    def test_invalid_teaching_pulse_does_not_reverse_or_reset_state(self) -> None:
        state = IntracellularState()
        before = state.snapshot()
        for action in (state.apply_oxidative_stress, state.apply_antioxidant_response):
            for invalid in (-1.0, float("nan"), float("inf"), True, "strong"):
                with self.subTest(action=action.__name__, intensity=invalid):
                    with self.assertRaisesRegex(ValueError, "教学干预强度"):
                        action(invalid)
        self.assertEqual(state.snapshot(), before)

    def test_long_single_cell_step_is_not_silently_shortened(self) -> None:
        state = IntracellularState()
        with self.assertRaisesRegex(ValueError, "单步时长不能超过 6 h"):
            state.step(CellCulture("hela"), 24.0)
        self.assertEqual(state.time_h, 0.0)

    def test_clock_precision_loss_is_rejected_before_state_changes(self) -> None:
        state = IntracellularState(time_h=1e20)
        before = state.snapshot()
        with self.assertRaisesRegex(ValueError, "模拟时钟无法安全推进"):
            state.step(MicroenvironmentState(), 0.25)
        self.assertEqual(state.snapshot(), before)

    def test_corrupt_single_cell_state_is_rejected_before_any_field_changes(self) -> None:
        state = IntracellularState(ros_percent=float("nan"))
        before = state.snapshot()
        with self.assertRaisesRegex(ValueError, "单细胞状态包含越界或非有限值"):
            state.step(MicroenvironmentState(), 0.25)
        for name, value in before.items():
            if name == "ROS_percent":
                self.assertTrue(isnan(state.snapshot()[name]))
            else:
                self.assertEqual(state.snapshot()[name], value)

    def test_six_hour_advance_matches_six_one_hour_advances(self) -> None:
        environment = MicroenvironmentState(
            local_oxygen_availability=0.25, glucose_mm=2.0, ph=7.0, drug_um=12.0,
        )
        one_step = IntracellularState()
        repeated_steps = IntracellularState()

        one_step.step(environment, 6.0)
        for _ in range(6):
            repeated_steps.step(environment, 1.0)

        self.assertEqual(one_step.snapshot(), repeated_steps.snapshot())

    def test_one_hour_advance_matches_quarter_hour_forecast_resolution(self) -> None:
        environment = MicroenvironmentState(local_oxygen_availability=0.4, glucose_mm=3.0, drug_um=8.0)
        one_step = IntracellularState()
        quarter_steps = IntracellularState()

        one_step.step(environment, 1.0)
        for _ in range(4):
            quarter_steps.step(environment, 0.25)

        self.assertEqual(one_step.snapshot(), quarter_steps.snapshot())

    def test_relative_indices_remain_bounded_at_environment_endpoints(self) -> None:
        index_fields = (
            "atp_percent", "mitochondrial_potential_percent", "glycolysis_percent",
            "ros_percent", "dna_damage_percent", "er_stress_percent",
            "autophagy_percent", "protein_synthesis_percent", "growth_signal_percent",
            "apoptosis_signal_percent", "cycle_progress_percent",
        )
        endpoints = product(
            (0.0, 1.0), (0.0, 100.0), (5.5, 9.0),
            (0.0, 50.0), (0.0, 1e6), (0.0, 100.0),
        )
        for oxygen, glucose, ph, temperature, drug, confluence in endpoints:
            with self.subTest(
                oxygen=oxygen, glucose=glucose, ph=ph,
                temperature=temperature, drug=drug, confluence=confluence,
            ):
                environment = MicroenvironmentState(
                    local_oxygen_availability=oxygen,
                    glucose_mm=glucose,
                    glucose_reference_mm=100.0,
                    ph=ph,
                    temperature_c=temperature,
                    drug_um=drug,
                    drug_ic50_um=1e-6,
                    doubling_time_h=1.0,
                    local_confluence_percent=confluence,
                )
                state = IntracellularState()
                for _ in range(10):
                    state.step(environment, 6.0)
                self.assertTrue(all(isfinite(float(getattr(state, field))) for field in index_fields))
                self.assertTrue(all(0.0 <= float(getattr(state, field)) <= 100.0 for field in index_fields))
                self.assertTrue(50.0 <= state.cytosolic_calcium_nm <= 1200.0)

    def test_status_reports_severe_apoptosis(self) -> None:
        state = IntracellularState(apoptosis_signal_percent=75.0)
        self.assertEqual(intracellular_status(state), ("促凋亡压力相对指数高", "error"))


if __name__ == "__main__":
    unittest.main()

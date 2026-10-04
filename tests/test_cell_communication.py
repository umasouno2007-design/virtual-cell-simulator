"""代表性子群通信层的边界与方向测试。"""

import copy
import math
import unittest
import pandas as pd

from cell_communication import CellCommunicationState, representative_subpopulation_points
from intracellular import IntracellularState
from simulation import new_simulation


class CellCommunicationTests(unittest.TestCase):
    def test_failed_later_substep_rolls_back_communication_and_receiver(self) -> None:
        communication = CellCommunicationState()
        intracellular = IntracellularState()
        before_communication = communication.snapshot()
        before_intracellular = intracellular.snapshot()
        original_finite = intracellular.finite
        calls = 0

        def fail_on_second_internal_step() -> bool:
            nonlocal calls
            calls += 1
            return calls < 3 and original_finite()

        intracellular.finite = fail_on_second_internal_step
        with self.assertRaisesRegex(ValueError, "单细胞状态无效"):
            communication.step(intracellular, 0.5, feedback_enabled=True)
        self.assertEqual(communication.snapshot(), before_communication)
        self.assertEqual(intracellular.snapshot(), before_intracellular)

    def test_unrepresentably_large_duration_is_rejected_as_user_input(self) -> None:
        state = CellCommunicationState()
        before = state.snapshot()
        with self.assertRaisesRegex(ValueError, "通信层时间步长"):
            state.step(IntracellularState(), 10**10000)
        self.assertEqual(state.snapshot(), before)

    def test_pandas_boolean_scalar_is_not_a_communication_duration(self) -> None:
        pandas_boolean = pd.Series([True]).iloc[0]
        state = CellCommunicationState()
        before = state.snapshot()
        with self.assertRaisesRegex(ValueError, "通信层时间步长"):
            state.step(IntracellularState(), pandas_boolean)
        self.assertEqual(state.snapshot(), before)

    def test_unrepresentably_large_index_is_rejected_without_state_changes(self) -> None:
        state = CellCommunicationState(stress_signal_index=10**10000)
        before = state.snapshot()
        self.assertFalse(state.finite())
        with self.assertRaisesRegex(ValueError, "通信状态包含越界、非有限或不守恒"):
            state.step(IntracellularState(), 0.25)
        self.assertEqual(state.snapshot(), before)

    def stressed_state(self) -> IntracellularState:
        return IntracellularState(
            atp_percent=28.0,
            ros_percent=78.0,
            er_stress_percent=72.0,
            dna_damage_percent=64.0,
            apoptosis_signal_percent=55.0,
        )

    def test_stress_increases_stressed_injured_and_signal_pool(self) -> None:
        baseline = CellCommunicationState()
        stressed = CellCommunicationState()
        normal = IntracellularState(atp_percent=90.0, ros_percent=5.0, er_stress_percent=3.0, apoptosis_signal_percent=1.0)
        for _ in range(6):
            baseline.step(normal, 1.0)
            stressed.step(self.stressed_state(), 1.0)
        self.assertGreater(stressed.stressed_fraction, baseline.stressed_fraction)
        self.assertGreater(stressed.injured_fraction, baseline.injured_fraction)
        self.assertGreater(stressed.stress_signal_index, baseline.stress_signal_index)

    def test_signal_pool_decays_without_sustained_release(self) -> None:
        state = CellCommunicationState(
            resilient_fraction=100.0, stressed_fraction=0.0, injured_fraction=0.0,
            stress_signal_index=90.0, receiver_response_index=90.0,
        )
        calm = IntracellularState(atp_percent=100.0, ros_percent=0.0, er_stress_percent=0.0, dna_damage_percent=0.0, apoptosis_signal_percent=0.0)
        state.step(calm, 1.0)
        self.assertLess(state.stress_signal_index, 90.0)

    def test_long_allowed_step_matches_quarter_hour_updates(self) -> None:
        one_step = CellCommunicationState(
            resilient_fraction=100.0, stressed_fraction=0.0, injured_fraction=0.0,
            stress_signal_index=90.0, receiver_response_index=90.0,
        )
        repeated_steps = copy.deepcopy(one_step)
        calm = IntracellularState(
            atp_percent=100.0, ros_percent=0.0, er_stress_percent=0.0,
            dna_damage_percent=0.0, apoptosis_signal_percent=0.0,
        )

        one_step.step(calm, 24.0)
        for _ in range(96):
            repeated_steps.step(calm, 0.25)

        self.assertEqual(one_step.snapshot(), repeated_steps.snapshot())
        self.assertGreater(one_step.stress_signal_index, 0.0)
        self.assertGreater(one_step.receiver_response_index, 0.0)
        self.assertEqual(one_step.time_h, 24.0)

    def test_invalid_time_step_does_not_advance_communication_state(self) -> None:
        state = CellCommunicationState()
        before = state.snapshot()
        for invalid in (-1.0, 25.0, float("nan"), float("inf"), None, True):
            with self.subTest(dt_h=invalid):
                with self.assertRaisesRegex(ValueError, "时间步长"):
                    state.step(IntracellularState(), invalid)
        state.step(IntracellularState(), 0.0)
        self.assertEqual(state.snapshot(), before)

    def test_zero_duration_still_validates_restored_states_and_feedback_switch(self) -> None:
        valid_cell = IntracellularState()
        invalid_cases = (
            (CellCommunicationState(stress_signal_index=float("nan")), valid_cell, False,
             "通信状态包含越界"),
            (CellCommunicationState(), IntracellularState(ros_percent=float("nan")), False,
             "通信层输入的单细胞状态无效"),
            (CellCommunicationState(), valid_cell, "false", "通信反馈开关必须是布尔值"),
        )
        for communication, intracellular, feedback, message in invalid_cases:
            with self.subTest(message=message):
                before_communication = communication.snapshot()
                before_intracellular = intracellular.snapshot()
                with self.assertRaisesRegex(ValueError, message):
                    communication.step(
                        intracellular, 0.0, feedback_enabled=feedback,
                    )
                self.assertEqual(communication.snapshot(), before_communication)
                for key, value in before_intracellular.items():
                    actual = intracellular.snapshot()[key]
                    if isinstance(value, float) and math.isnan(value):
                        self.assertTrue(math.isnan(actual))
                    else:
                        self.assertEqual(actual, value)

    def test_invalid_saved_communication_state_is_rejected_without_mutation(self) -> None:
        invalid_states = (
            CellCommunicationState(resilient_fraction=90.0),
            CellCommunicationState(stress_signal_index=float("nan")),
            CellCommunicationState(receiver_response_index=101.0),
            CellCommunicationState(time_h=-1.0),
        )
        for state in invalid_states:
            with self.subTest(state=state):
                before = state.snapshot()
                with self.assertRaisesRegex(ValueError, "通信状态包含越界"):
                    state.step(IntracellularState(), 0.25)
                self.assertEqual(state.snapshot(), before)

    def test_feedback_flag_requires_an_explicit_boolean(self) -> None:
        state = CellCommunicationState()
        before = state.snapshot()
        with self.assertRaisesRegex(ValueError, "通信反馈开关必须是布尔值"):
            state.step(IntracellularState(), 0.25, feedback_enabled="false")
        self.assertEqual(state.snapshot(), before)

    def test_invalid_upstream_cell_state_is_not_masked_as_low_stress(self) -> None:
        state = CellCommunicationState()
        before_communication = state.snapshot()
        invalid_cell = IntracellularState(ros_percent=float("nan"))
        before_cell = invalid_cell.snapshot()
        with self.assertRaisesRegex(ValueError, "通信层输入的单细胞状态无效"):
            state.step(invalid_cell, 0.25, feedback_enabled=True)
        self.assertEqual(state.snapshot(), before_communication)
        self.assertTrue(math.isnan(invalid_cell.ros_percent))
        for name, value in before_cell.items():
            if name != "ROS_percent":
                self.assertEqual(invalid_cell.snapshot()[name], value)

    def test_clock_precision_loss_is_rejected_before_communication_changes(self) -> None:
        state = CellCommunicationState(time_h=1e20)
        before = state.snapshot()
        with self.assertRaisesRegex(ValueError, "模拟时钟无法安全推进"):
            state.step(IntracellularState(), 0.25)
        self.assertEqual(state.snapshot(), before)

    def test_response_and_proportions_remain_bounded(self) -> None:
        state = CellCommunicationState()
        stress = self.stressed_state()
        for _ in range(80):
            state.step(stress, 2.0)
        self.assertGreaterEqual(state.receiver_response_index, 0.0)
        self.assertLessEqual(state.receiver_response_index, 100.0)
        self.assertAlmostEqual(
            state.resilient_fraction + state.stressed_fraction + state.injured_fraction,
            100.0,
            places=9,
        )
        for value in state.snapshot().values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 100.0 if value != state.time_h else 200.0)

    def test_feedback_off_does_not_change_existing_intracellular_state(self) -> None:
        intracellular = self.stressed_state()
        before = copy.deepcopy(intracellular.snapshot())
        communication = CellCommunicationState(stress_signal_index=80.0, receiver_response_index=80.0)
        communication.step(intracellular, 1.0, feedback_enabled=False)
        self.assertEqual(intracellular.snapshot(), before)

    def test_closed_feedback_does_not_change_primary_culture_dynamics(self) -> None:
        reference_cell, _ = new_simulation("a549")
        observed_cell, _ = new_simulation("a549")
        reference_intracellular = IntracellularState()
        observed_intracellular = IntracellularState()
        communication = CellCommunicationState()
        for _ in range(12):
            reference_cell.step(1.0)
            reference_intracellular.step(reference_cell, 1.0)
            observed_cell.step(1.0)
            observed_intracellular.step(observed_cell, 1.0)
            communication.step(observed_intracellular, 1.0, feedback_enabled=False)
        self.assertEqual(observed_cell.snapshot(), reference_cell.snapshot())

    def test_feedback_is_opt_in_and_representative_points_are_finite(self) -> None:
        intracellular = self.stressed_state()
        before_ros = intracellular.ros_percent
        communication = CellCommunicationState(stress_signal_index=90.0, receiver_response_index=90.0)
        communication.step(intracellular, 1.0, feedback_enabled=True)
        self.assertGreaterEqual(intracellular.ros_percent, before_ros)
        points = representative_subpopulation_points(communication, "信号释放", total_points=36)
        self.assertEqual(len(points), 36)
        self.assertEqual({point["group"] for point in points}, {"稳态/适应", "应激", "受损"})
        self.assertEqual({point["value"] for point in points}, {0.0, 35.0, 75.0})

    def test_map_release_uses_model_coefficients_and_current_subgroup_composition(self) -> None:
        baseline = CellCommunicationState()
        stressed = CellCommunicationState(
            resilient_fraction=40.0, stressed_fraction=35.0, injured_fraction=25.0,
        )
        baseline_points = representative_subpopulation_points(baseline, "信号释放", total_points=100)
        stressed_points = representative_subpopulation_points(stressed, "信号释放", total_points=100)
        baseline_groups = {name: sum(point["group"] == name for point in baseline_points) for name in {p["group"] for p in baseline_points}}
        stressed_groups = {name: sum(point["group"] == name for point in stressed_points) for name in {p["group"] for p in stressed_points}}
        self.assertNotEqual(baseline_groups, stressed_groups)
        self.assertEqual(
            {point["value"] for point in stressed_points},
            {0.0, 35.0, 75.0},
        )

    def test_fate_map_reads_the_existing_representative_apoptosis_index(self) -> None:
        communication = CellCommunicationState()
        intracellular = IntracellularState(apoptosis_signal_percent=37.5)
        with self.assertRaisesRegex(ValueError, "必须提供有效的当前代表性细胞状态"):
            representative_subpopulation_points(communication, "命运倾向")
        points = representative_subpopulation_points(
            communication, "命运倾向", intracellular=intracellular,
        )
        self.assertEqual({point["value"] for point in points}, {37.5})

    def test_subpopulation_map_rejects_invalid_state_and_view_types(self) -> None:
        with self.assertRaisesRegex(ValueError, "有效且比例守恒"):
            representative_subpopulation_points(
                CellCommunicationState(stressed_fraction=float("nan")),
            )
        with self.assertRaisesRegex(ValueError, "不支持的子群地图视图"):
            representative_subpopulation_points(CellCommunicationState(), [])
        with self.assertRaisesRegex(ValueError, "有效的当前代表性细胞状态"):
            representative_subpopulation_points(
                CellCommunicationState(), "命运倾向", intracellular="invalid",
            )
        for point_count in (True, float("nan"), float("inf"), 9.5, 10**10000, []):
            with self.subTest(total_points=type(point_count).__name__):
                with self.assertRaisesRegex(ValueError, "示意点数"):
                    representative_subpopulation_points(
                        CellCommunicationState(), total_points=point_count,
                    )

    def test_larger_teaching_map_keeps_all_points_inside_plot_bounds(self) -> None:
        points = representative_subpopulation_points(CellCommunicationState(), total_points=100)
        self.assertEqual(len(points), 100)
        self.assertTrue(all(0.0 <= point["x"] <= 6.3 for point in points))
        self.assertTrue(all(0.0 <= point["y"] <= 5.7 for point in points))


if __name__ == "__main__":
    unittest.main()

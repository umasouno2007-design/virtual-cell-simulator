"""代表性子群通信层的边界与方向测试。"""

import copy
import unittest

from cell_communication import CellCommunicationState, representative_subpopulation_points
from intracellular import IntracellularState
from simulation import new_simulation


class CellCommunicationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

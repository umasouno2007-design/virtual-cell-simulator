"""细胞内条件沙盒测试。"""

import unittest

from cell import CellCulture
from intracellular import IntracellularState
from intracellular_forecast import forecast_intracellular_state


class IntracellularForecastTestCase(unittest.TestCase):
    def test_forecast_does_not_mutate_live_state(self) -> None:
        cell = CellCulture("hela")
        state = IntracellularState()
        before_oxygen = cell.oxygen_percent
        before_atp = state.atp_percent
        report = forecast_intracellular_state(
            cell, state, attribute="oxygen_percent", value=1.0, horizon_h=6.0
        )
        self.assertEqual(cell.oxygen_percent, before_oxygen)
        self.assertEqual(state.atp_percent, before_atp)
        self.assertEqual(report["candidate_cell"]["oxygen_setpoint_percent"], cell.oxygen_setpoint_percent)
        self.assertLess(
            report["candidate_state"]["mitochondrial_potential_percent"], state.mitochondrial_potential_percent
        )

    def test_forecast_rejects_invalid_values_without_silent_clipping(self) -> None:
        cell, state = CellCulture("hela"), IntracellularState()
        for value, horizon in ((float("nan"), 1.0), (22.0, 1.0), (1.0, -1.0),
                               (1.0, 49.0), (1.0, float("inf")), (True, 1.0)):
            with self.subTest(value=value, horizon=horizon):
                with self.assertRaisesRegex(ValueError, "候选|推演|有限"):
                    forecast_intracellular_state(
                        cell, state, attribute="oxygen_percent", value=value, horizon_h=horizon,
                    )
        self.assertEqual(cell.time_h, 0.0)
        self.assertEqual(state.time_h, 0.0)

    def test_forecast_reports_actual_completed_duration_if_cell_is_inactive(self) -> None:
        cell = CellCulture("hela", viable_cells=0.0)
        result = forecast_intracellular_state(
            cell, IntracellularState(), attribute="glucose_mm", value=5.0, horizon_h=6.0,
        )
        self.assertEqual(result["completed_h"], 0.0)


if __name__ == "__main__":
    unittest.main()

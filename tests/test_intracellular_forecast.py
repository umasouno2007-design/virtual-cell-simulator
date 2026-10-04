"""细胞内条件沙盒测试。"""

import unittest
import pandas as pd

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
        pandas_boolean = pd.Series([True]).iloc[0]
        for value, horizon in ((float("nan"), 1.0), (22.0, 1.0), (1.0, -1.0),
                               (1.0, 49.0), (1.0, float("inf")), (True, 1.0),
                               (pandas_boolean, 1.0), (1.0, pandas_boolean)):
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

    def test_forecast_rejects_invalid_objects_misaligned_clocks_and_unknown_keys(self) -> None:
        cell = CellCulture("hela")
        cell.step(1.0)
        with self.assertRaisesRegex(ValueError, "时钟不一致"):
            forecast_intracellular_state(
                cell, IntracellularState(), attribute="glucose_mm", value=5.0, horizon_h=1.0,
            )
        negative_cell, negative_state = CellCulture(), IntracellularState()
        negative_cell.time_h = negative_state.time_h = -1.0
        with self.assertRaisesRegex(ValueError, "非负小时数"):
            forecast_intracellular_state(
                negative_cell, negative_state, attribute="glucose_mm", value=5.0, horizon_h=1.0,
            )
        with self.assertRaisesRegex(ValueError, "培养状态对象"):
            forecast_intracellular_state(
                None, IntracellularState(), attribute="glucose_mm", value=5.0, horizon_h=1.0,
            )
        with self.assertRaisesRegex(KeyError, "未知条件"):
            forecast_intracellular_state(
                CellCulture(), IntracellularState(), attribute=[], value=5.0, horizon_h=1.0,
            )


if __name__ == "__main__":
    unittest.main()

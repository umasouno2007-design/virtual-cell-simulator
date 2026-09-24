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
        self.assertLess(
            report["candidate_state"]["mitochondrial_potential_percent"], state.mitochondrial_potential_percent
        )


if __name__ == "__main__":
    unittest.main()

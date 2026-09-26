"""两参数粗校准的回归测试。"""

import unittest

import pandas as pd

from calibration import fit_growth_and_uptake
from cell import CellCulture


class CalibrationTestCase(unittest.TestCase):
    def test_fit_uses_measurements_and_returns_bounded_parameters(self) -> None:
        cell = CellCulture("hela")
        initial = cell.snapshot()
        cell.parameters.growth_scale = 1.4
        cell.parameters.uptake_scale = 1.6
        history = [initial]
        for _ in range(24):
            cell.step(1.0)
            history.append(cell.snapshot())
        measurements = pd.DataFrame(history[::6])[["time_h", "viable_cells", "glucose_mM", "lactate_mM"]]
        result = fit_growth_and_uptake(CellCulture("hela"), [initial], measurements)
        self.assertAlmostEqual(result.growth_scale, 1.4, places=1)
        self.assertAlmostEqual(result.uptake_scale, 1.6, places=1)
        self.assertLess(result.normalized_rmse, 0.01)
        self.assertEqual(len(result.grid_scores or []), 600)

    def test_zero_weight_is_supported_but_negative_is_rejected(self) -> None:
        cell = CellCulture("hela")
        initial = cell.snapshot()
        history = [initial]
        for _ in range(12):
            cell.step(1.0)
            history.append(cell.snapshot())
        measurements = pd.DataFrame(history[::6])[["time_h", "viable_cells", "glucose_mM"]]
        result = fit_growth_and_uptake(CellCulture("hela"), [initial], measurements, {"viable_cells": 1.0, "glucose_mM": 0.0})
        self.assertTrue(result.grid_scores)
        with self.assertRaisesRegex(ValueError, "非负"):
            fit_growth_and_uptake(CellCulture("hela"), [initial], measurements, {"viable_cells": -1})


if __name__ == "__main__":
    unittest.main()

"""实测 CSV 导入和模拟对比测试。"""

import unittest

import pandas as pd

from experiment_data import comparison_frame, residual_summary, standardize_measurements


class ExperimentDataTestCase(unittest.TestCase):
    def test_chinese_headers_are_standardized(self) -> None:
        source = "时间,活细胞数,葡萄糖,pH\n0,100000,5.5,7.4\n24,180000,3.2,7.2\n".encode("utf-8-sig")
        data, notes = standardize_measurements(source)
        self.assertEqual(list(data.columns), ["time_h", "viable_cells", "glucose_mM", "pH"])
        self.assertEqual(len(data), 2)
        self.assertTrue(notes)

    def test_time_column_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "时间列"):
            standardize_measurements("葡萄糖\n5.5\n".encode())

    def test_comparison_interpolates_and_calculates_residual(self) -> None:
        simulation = pd.DataFrame({"time_h": [0, 2], "viable_cells": [100.0, 200.0]})
        observations = pd.DataFrame({"time_h": [1], "viable_cells": [140.0]})
        comparison = comparison_frame(simulation, observations)
        self.assertAlmostEqual(comparison.loc[0, "viable_cells_simulated"], 150.0)
        self.assertAlmostEqual(comparison.loc[0, "viable_cells_residual"], 10.0)
        self.assertAlmostEqual(residual_summary(comparison).loc[0, "MAE"], 10.0)


if __name__ == "__main__":
    unittest.main()

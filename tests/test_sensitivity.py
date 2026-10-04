"""敏感性分析不改写模型状态且能处理边界输入。"""

import unittest
import pandas as pd

from cell import CellCulture
from sensitivity import SENSITIVITY_PARAMETERS, run_sensitivity, simulate_one_factor


class SensitivityTestCase(unittest.TestCase):
    def test_one_factor_returns_three_scenarios_without_mutating_source(self) -> None:
        cell = CellCulture("a549")
        before = cell.snapshot()
        result = simulate_one_factor(cell, "growth_scale", 24)
        self.assertEqual(set(result["scenario"]), {"低情景", "基准", "高情景"})
        self.assertEqual(cell.snapshot(), before)
        self.assertGreater(result["viable_cells"].min(), 0)
        self.assertTrue(result[["viable_cells", "glucose_mM", "lactate_mM", "pH"]].notna().all().all())

    def test_sensitivity_baseline_row_preserves_current_rate_observations(self) -> None:
        cell = CellCulture("a549")
        cell.step(2.0)
        source_snapshot = cell.snapshot()
        result = simulate_one_factor(cell, "growth_scale", 1.0)
        first_row = result.iloc[0]
        for key, value in source_snapshot.items():
            self.assertEqual(first_row[key], value, msg=key)

    def test_all_default_parameters_have_endpoint_summaries(self) -> None:
        _, summary = run_sensitivity(CellCulture("hela"), 12)
        self.assertEqual(set(summary["parameter"]), set(SENSITIVITY_PARAMETERS))
        self.assertEqual(len(summary), 3 * len(SENSITIVITY_PARAMETERS))

    def test_invalid_horizon_is_rejected(self) -> None:
        pandas_boolean = pd.Series([True]).iloc[0]
        for invalid in (0, -1, 169, None, "later", True, pandas_boolean, float("nan"), float("inf"), 10**10000):
            with self.subTest(horizon=invalid):
                with self.assertRaisesRegex(ValueError, "分析时长"):
                    simulate_one_factor(CellCulture(), "growth_scale", invalid)

    def test_invalid_analysis_objects_and_unhashable_parameter_names_are_domain_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "培养状态对象"):
            simulate_one_factor(None, "growth_scale")
        with self.assertRaisesRegex(ValueError, "培养状态对象"):
            run_sensitivity(None)
        with self.assertRaisesRegex(ValueError, "未知敏感性参数"):
            simulate_one_factor(CellCulture(), [], 1.0)


if __name__ == "__main__":
    unittest.main()

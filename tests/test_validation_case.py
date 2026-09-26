"""教学验证案例的可重复性测试。"""

import unittest
from pathlib import Path

from scripts.validate_a549_teaching_case import run_case


class ValidationCaseTestCase(unittest.TestCase):
    def test_a549_teaching_case_has_train_and_holdout_metrics(self) -> None:
        result = run_case(output_dir=None)

        self.assertEqual(result["data_kind"], "teaching_synthetic_not_experimental")
        self.assertEqual(result["training_time_h"], [0.0, 12.0, 24.0, 36.0])
        self.assertEqual(result["validation_time_h"], [48.0, 60.0, 72.0])
        self.assertGreaterEqual(len(result["training_metrics"]), 2)
        self.assertGreaterEqual(len(result["validation_metrics"]), 2)
        self.assertGreater(result["fitted_parameters"]["growth_scale"], 0)
        self.assertGreater(result["fitted_parameters"]["uptake_scale"], 0)
        for row in result["validation_metrics"]:
            self.assertGreaterEqual(row["MAE"], 0)
            self.assertGreaterEqual(row["RMSE"], 0)


if __name__ == "__main__":
    unittest.main()

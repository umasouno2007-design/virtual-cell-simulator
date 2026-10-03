"""教学验证案例的可重复性测试。"""

import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys

from scripts.validate_a549_teaching_case import (
    DEFAULT_DATA, _template_from_observed_start, run_case,
)
import pandas as pd
from version import MODEL_VERSION


class ValidationCaseTestCase(unittest.TestCase):
    def test_a549_teaching_case_has_train_and_holdout_metrics(self) -> None:
        result = run_case(output_dir=None)

        self.assertEqual(result["data_kind"], "teaching_synthetic_not_experimental")
        self.assertEqual(result["model_version"], MODEL_VERSION)
        self.assertEqual(result["data_source"], "data/a549_teaching_synthetic.csv")
        self.assertEqual(len(result["data_file_sha256"]), 64)
        self.assertEqual(result["initial_conditions"]["viable_cells"], 250000.0)
        committed_summary = json.loads(
            (DEFAULT_DATA.parents[1] / "assets" / "validation" / "a549_teaching_case" / "summary.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result, committed_summary)
        self.assertEqual(result["training_time_h"], [0.0, 12.0, 24.0, 36.0])
        self.assertEqual(result["validation_time_h"], [48.0, 60.0, 72.0])
        self.assertGreaterEqual(len(result["training_metrics"]), 2)
        self.assertGreaterEqual(len(result["validation_metrics"]), 2)
        self.assertGreater(result["fitted_parameters"]["growth_scale"], 0)
        self.assertGreater(result["fitted_parameters"]["uptake_scale"], 0)
        for row in result["validation_metrics"]:
            self.assertGreaterEqual(row["MAE"], 0)
            self.assertGreaterEqual(row["RMSE"], 0)

    def test_custom_data_is_not_misrepresented_as_bundled_teaching_data(self) -> None:
        with TemporaryDirectory() as temporary:
            custom = Path(temporary) / "unverified.csv"
            custom.write_bytes(DEFAULT_DATA.read_bytes())
            result = run_case(data_path=custom, output_dir=None)
        self.assertEqual(result["data_kind"], "user_supplied_unverified")
        self.assertEqual(result["data_source"], "user-supplied CSV (path withheld)")
        self.assertNotIn(str(custom), str(result))

    def test_invalid_holdout_observation_blocks_custom_case(self) -> None:
        with TemporaryDirectory() as temporary:
            custom = Path(temporary) / "invalid_holdout.csv"
            custom.write_text(
                "time_h,viable_cells,glucose_mM,pH\n"
                "0,100,5,7.4\n12,120,4.8,7.3\n24,140,4.5,7.3\n36,160,4.1,7.2\n"
                "48,180,3.8,7.2\n60,200,3.5,7.1\n72,220,3.2,15\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "pH 超出"):
                run_case(data_path=custom, output_dir=None)

    def test_custom_cli_data_requires_explicit_output_location(self) -> None:
        with TemporaryDirectory() as temporary:
            custom = Path(temporary) / "unverified.csv"
            custom.write_bytes(DEFAULT_DATA.read_bytes())
            command = [
                sys.executable,
                str(DEFAULT_DATA.parents[1] / "scripts" / "validate_a549_teaching_case.py"),
                "--data", str(custom),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("必须显式指定 --output-dir", completed.stderr)

    def test_custom_initial_observation_sets_replay_start(self) -> None:
        observations = pd.DataFrame({
            "time_h": [0.0, 12.0],
            "viable_cells": [500000.0, 600000.0],
            "glucose_mM": [7.0, 6.5],
            "lactate_mM": [1.0, 1.5],
        })
        template, initial = _template_from_observed_start(observations)
        self.assertEqual(template.viable_cells, 500000.0)
        self.assertEqual(template.glucose_mm, 7.0)
        self.assertEqual(template.lactate_mm, 1.0)
        self.assertEqual(initial["viable_cells"], 500000.0)
        observations.loc[0, "viable_cells"] = None
        with self.assertRaisesRegex(ValueError, "0 h 观测必须包含"):
            _template_from_observed_start(observations)


if __name__ == "__main__":
    unittest.main()

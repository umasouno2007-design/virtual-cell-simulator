"""两参数粗校准的回归测试。"""

import unittest

import pandas as pd

from calibration import _score, fit_growth_and_uptake, fit_with_temporal_holdout
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

    def test_measurements_before_simulation_clock_are_rejected(self) -> None:
        cell = CellCulture("hela")
        cell.time_h = 6.0
        initial = cell.snapshot()
        measurements = pd.DataFrame({
            "time_h": [0.0, 12.0],
            "viable_cells": [initial["viable_cells"], initial["viable_cells"] * 1.1],
        })
        with self.assertRaisesRegex(ValueError, "早于模拟历史起点"):
            fit_growth_and_uptake(cell, [initial], measurements)

    def test_measurements_without_time_column_get_clear_error(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({"viable_cells": [100.0, 120.0]})
        with self.assertRaisesRegex(ValueError, "缺少 time_h"):
            fit_growth_and_uptake(cell, [cell.snapshot()], measurements)

    def test_non_finite_measurement_time_is_rejected_before_replay(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({
            "time_h": [0.0, float("inf")],
            "viable_cells": [100.0, 200.0],
        })
        with self.assertRaisesRegex(ValueError, "非有限"):
            fit_growth_and_uptake(cell, [cell.snapshot()], measurements)

    def test_non_finite_observation_is_rejected(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({
            "time_h": [0.0, 24.0],
            "viable_cells": [100.0, float("inf")],
        })
        with self.assertRaisesRegex(ValueError, "无穷值"):
            fit_growth_and_uptake(cell, [cell.snapshot()], measurements)

    def test_zero_weight_excludes_metric_from_normalization(self) -> None:
        comparison = pd.DataFrame({
            "viable_cells_observed": [100.0, 200.0],
            "viable_cells_residual": [10.0, 20.0],
            "glucose_mM_observed": [10.0, 20.0],
            "glucose_mM_residual": [10.0, 20.0],
        })
        cell_only = _score(comparison, {"viable_cells": 1.0, "glucose_mM": 0.0, "lactate_mM": 0.0})
        zero_glucose = _score(comparison, {"viable_cells": 1.0, "glucose_mM": 0.0})
        self.assertAlmostEqual(cell_only, zero_glucose)

    def test_all_zero_eligible_weights_are_rejected(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 120.0]})
        with self.assertRaisesRegex(ValueError, "至少一个具备观测值"):
            fit_growth_and_uptake(cell, [cell.snapshot()], measurements, {"viable_cells": 0.0})

    def test_invalid_negative_observation_is_rejected(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({
            "time_h": [0.0, 24.0],
            "glucose_mM": [10.0, -1.0],
        })
        with self.assertRaisesRegex(ValueError, "负值"):
            fit_growth_and_uptake(cell, [cell.snapshot()], measurements)

    def test_midcourse_culture_intervention_blocks_unreplayed_fit(self) -> None:
        cell = CellCulture("hela")
        initial = cell.snapshot()
        cell.step(6.0)
        measurements = pd.DataFrame({
            "time_h": [0.0, 6.0],
            "viable_cells": [initial["viable_cells"], cell.viable_cells],
        })
        with self.assertRaisesRegex(ValueError, "不重放干预"):
            fit_growth_and_uptake(
                cell, [initial, cell.snapshot()], measurements,
                events=[{"event": "全量换液", "time_h": 3.0}],
            )

    def test_initial_condition_edit_uses_latest_same_time_snapshot(self) -> None:
        cell = CellCulture("hela")
        before = cell.snapshot()
        cell.ph = 6.8
        after = cell.snapshot()
        cell.step(6.0)
        measurements = pd.DataFrame({
            "time_h": [0.0, 6.0],
            "viable_cells": [after["viable_cells"], cell.viable_cells],
        })
        result = fit_growth_and_uptake(
            cell, [before, after, cell.snapshot()], measurements,
            events=[{"event": "环境调整", "time_h": 0.0}],
        )
        self.assertEqual(result.fitted_history[0]["pH"], 6.8)

    def test_temporal_holdout_is_excluded_from_parameter_search(self) -> None:
        cell = CellCulture("hela")
        history = [cell.snapshot()]
        for _ in range(24):
            cell.step(1.0)
            history.append(cell.snapshot())
        measurements = pd.DataFrame(history[::4])[["time_h", "viable_cells", "glucose_mM"]].copy()
        measurements.loc[measurements.index[-1], "viable_cells"] *= 1.5
        result = fit_with_temporal_holdout(CellCulture("hela"), history, measurements)
        self.assertEqual(result.training_time_h, [0.0, 4.0, 8.0, 12.0, 16.0])
        self.assertEqual(result.holdout_time_h, [20.0, 24.0])
        self.assertTrue(result.training_metrics)
        self.assertTrue(result.holdout_metrics)
        self.assertGreater(
            next(row["RMSE"] for row in result.holdout_metrics if row["指标"] == "活细胞数"),
            next(row["RMSE"] for row in result.training_metrics if row["指标"] == "活细胞数"),
        )

    def test_viability_above_one_hundred_is_rejected(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({
            "time_h": [0.0, 24.0],
            "viable_cells": [100.0, 120.0],
            "viability_percent": [101.0, 95.0],
        })
        with self.assertRaisesRegex(ValueError, "存活率不能超过 100%"):
            fit_growth_and_uptake(cell, [cell.snapshot()], measurements)

    def test_boolean_or_text_weights_are_rejected(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 120.0]})
        for invalid_weight in (True, "heavy"):
            with self.subTest(weight=invalid_weight):
                with self.assertRaisesRegex(ValueError, "权重必须为数值"):
                    fit_growth_and_uptake(
                        cell, [cell.snapshot()], measurements,
                        {"viable_cells": invalid_weight},
                    )


if __name__ == "__main__":
    unittest.main()

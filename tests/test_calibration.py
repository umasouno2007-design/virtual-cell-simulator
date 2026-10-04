"""两参数粗校准的回归测试。"""

import unittest
from itertools import count
from math import isclose, isfinite

import pandas as pd

from calibration import _score, fit_growth_and_uptake, fit_with_temporal_holdout, replay_from_initial
from cell import CellCulture


class CalibrationTestCase(unittest.TestCase):
    def test_invalid_calibration_container_types_return_domain_errors(self) -> None:
        cell = CellCulture("hela")
        for measurements, events in (
            (None, None),
            (pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 120.0]}), "bad events"),
            (pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 120.0]}), ["bad event"]),
        ):
            with self.subTest(measurements=measurements is None, events=events):
                with self.assertRaisesRegex(ValueError, "校准观测|校准干预记录"):
                    fit_growth_and_uptake(cell, [cell.snapshot()], measurements, events=events)

        with self.assertRaisesRegex(ValueError, "校准观测"):
            fit_with_temporal_holdout(cell, [cell.snapshot()], None)

    def test_temporal_holdout_rejects_boolean_time_before_numeric_conversion(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({
            "time_h": [0.0, 12.0, True, 36.0, 48.0],
            "viable_cells": [100.0, 110.0, 120.0, 130.0, 140.0],
        })
        with self.assertRaisesRegex(ValueError, "校准时间列不能包含布尔值"):
            fit_with_temporal_holdout(cell, [cell.snapshot()], measurements)

    def test_grid_search_rejects_boolean_model_and_intervention_times(self) -> None:
        cell = CellCulture("hela")
        initial = cell.snapshot()
        later = dict(initial, time_h=1.0)
        measurements = pd.DataFrame({
            "time_h": [0.0, 1.0], "viable_cells": [initial["viable_cells"], initial["viable_cells"]],
        })

        boolean_history = [dict(initial, time_h=True), later]
        with self.assertRaisesRegex(ValueError, "模拟历史时间不能使用布尔值"):
            fit_growth_and_uptake(cell, boolean_history, measurements)

        with self.assertRaisesRegex(ValueError, "干预记录的模拟时间无效"):
            fit_growth_and_uptake(
                cell, [initial, later], measurements,
                events=[{"event": "全量换液", "time_h": True}],
            )

    def test_oversized_observation_is_reported_as_quality_error_not_overflow(self) -> None:
        cell = CellCulture("hela")
        huge = 10**10000
        measurements = pd.DataFrame({
            "time_h": pd.Series([0, 24, 48], dtype=object),
            "viable_cells": pd.Series([100, huge, 180], dtype=object),
        })
        with self.assertRaisesRegex(ValueError, "无穷值"):
            fit_growth_and_uptake(cell, [cell.snapshot()], measurements)

    def test_oversized_time_and_weight_inputs_are_rejected_before_search(self) -> None:
        cell = CellCulture("a549")
        initial = cell.snapshot()
        huge = 10**10000
        with self.assertRaisesRegex(ValueError, "校准重演时间"):
            replay_from_initial(cell, initial, [huge], 1.0, 1.0)
        with self.assertRaisesRegex(ValueError, "最多接受 5,000 个目标时间点"):
            replay_from_initial(cell, initial, count(0), 1.0, 1.0)
        pandas_boolean = pd.Series([True]).iloc[0]
        for invalid_time in ([True], [pandas_boolean], "24"):
            with self.subTest(target_times=invalid_time):
                with self.assertRaisesRegex(ValueError, "校准重演时间"):
                    replay_from_initial(cell, initial, invalid_time, 1.0, 1.0)
        for growth, uptake in ((True, 1.0), (float("nan"), 1.0), (2.1, 1.0), (1.0, 3.1)):
            with self.subTest(growth_scale=growth, uptake_scale=uptake):
                with self.assertRaisesRegex(ValueError, "校准重演参数"):
                    replay_from_initial(cell, initial, [], growth, uptake)

        for field, bad_value in (("time_h", True), ("viable_cells", True), ("glucose_mM", float("inf"))):
            malformed_initial = dict(initial)
            malformed_initial[field] = bad_value
            with self.subTest(initial_field=field):
                with self.assertRaisesRegex(ValueError, "校准重演起点字段"):
                    replay_from_initial(cell, malformed_initial, [], 1.0, 1.0)

        for field, bad_value in (("time_h", -1.0), ("viable_cells", -1.0), ("oxygen_percent", 22.0), ("pH", 9.0)):
            malformed_initial = dict(initial)
            malformed_initial[field] = bad_value
            with self.subTest(initial_range_field=field):
                with self.assertRaisesRegex(ValueError, "超出当前培养模型范围"):
                    replay_from_initial(cell, malformed_initial, [], 1.0, 1.0)

        measurements = pd.DataFrame({
            "time_h": [0.0, 24.0], "viable_cells": [100.0, 120.0],
        })
        with self.assertRaisesRegex(ValueError, "校准指标权重"):
            fit_growth_and_uptake(
                cell, [initial], measurements, {"viable_cells": huge},
            )

        comparison = pd.DataFrame({
            "viable_cells_observed": [100.0, 120.0],
            "viable_cells_residual": [0.0, 1.0],
        })
        with self.assertRaisesRegex(ValueError, "校准指标权重"):
            _score(comparison, {"viable_cells": huge})
        for invalid_weights in ([], {"viable_cells": True}, {"unknown_metric": 1.0}):
            with self.subTest(score_weights=invalid_weights):
                with self.assertRaisesRegex(ValueError, "权重"):
                    _score(comparison, invalid_weights)

    def test_normalized_score_is_stable_for_extreme_finite_values_and_weights(self) -> None:
        comparison = pd.DataFrame({
            "viable_cells_observed": [0.0, 0.0, 0.0],
            "viable_cells_residual": [1e308, 1e308, 1e308],
        })
        score = _score(comparison, {"viable_cells": 1e308})
        self.assertEqual(score, 1e308)

        opposite_sign = pd.DataFrame({
            "viable_cells_observed": [-1e308, 1e308],
            "viable_cells_residual": [1e308, 1e308],
        })
        self.assertEqual(_score(opposite_sign), 1.0)

        repeated_metrics = pd.DataFrame({
            f"{field}_{suffix}": [0.0, 0.0, 0.0]
            for field in ("viable_cells", "glucose_mM", "lactate_mM")
            for suffix in ("observed",)
        })
        for field in ("viable_cells", "glucose_mM", "lactate_mM"):
            repeated_metrics[f"{field}_residual"] = [1.7e308] * 3
        self.assertTrue(isclose(
            _score(repeated_metrics, {field: 1e308 for field in ("viable_cells", "glucose_mM", "lactate_mM")}),
            1.7e308,
            rel_tol=1e-15,
        ))
        self.assertEqual(
            _score(
                comparison,
                {"viable_cells": 1e-308},
            ),
            1e308,
        )
        largest = float.fromhex("0x1.fffffffffffffp+1023")
        maximum_frame = pd.DataFrame({
            "viable_cells_observed": [0.0, 0.0],
            "viable_cells_residual": [largest, largest],
        })
        maximum_score = _score(maximum_frame)
        self.assertTrue(maximum_score <= largest)
        self.assertTrue(isfinite(maximum_score))

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

    def test_calibration_flags_observed_initial_state_mismatch_without_changing_fit(self) -> None:
        cell = CellCulture("a549")
        initial = cell.snapshot()
        cell.step(1.0)
        observations = pd.DataFrame([initial, cell.snapshot()])[["time_h", "viable_cells", "glucose_mM"]]
        observations.loc[0, "viable_cells"] *= 1.2
        result = fit_growth_and_uptake(CellCulture("a549"), [initial], observations)
        self.assertTrue(result.grid_scores)
        self.assertTrue(any("活细胞数" in message for message in result.warnings or []))
        self.assertFalse(any("葡萄糖" in message for message in result.warnings or []))

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

    def test_calibration_rejects_mixed_or_reversed_simulation_history(self) -> None:
        cell = CellCulture("a549")
        initial = cell.snapshot()
        cell.step(1.0)
        later = cell.snapshot()
        observations = pd.DataFrame([initial, later])[["time_h", "viable_cells"]]
        with self.assertRaisesRegex(ValueError, "单调不减"):
            fit_growth_and_uptake(cell, [later, initial], observations)
        mixed = dict(later, cell_type="hela")
        with self.assertRaisesRegex(ValueError, "不同细胞系或模型版本"):
            fit_growth_and_uptake(cell, [initial, mixed], observations)
        invalid = dict(initial, glucose_mM=float("nan"))
        with self.assertRaisesRegex(ValueError, "模拟历史字段 glucose_mM"):
            fit_growth_and_uptake(cell, [invalid, later], observations)

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

    def test_replay_rejects_unbounded_or_invalid_time_before_stepping(self) -> None:
        cell = CellCulture("hela")
        initial = cell.snapshot()
        for targets, message in (
            ([float("inf")], "有限"),
            ([-1.0], "不能早于"),
            ([169.0], "最长支持 168 h"),
        ):
            with self.subTest(targets=targets):
                with self.assertRaisesRegex(ValueError, message):
                    replay_from_initial(cell, initial, targets, 1.0, 1.0)
        self.assertEqual(cell.time_h, 0.0)

    def test_replay_preserves_nondefault_oxygen_setpoint(self) -> None:
        low_oxygen = CellCulture("a549")
        low_oxygen.oxygen_setpoint_percent = 2.0
        initial = low_oxygen.snapshot()
        low_oxygen.step(1.0)
        template = CellCulture("a549")
        replayed, rows = replay_from_initial(template, initial, [1.0], 1.0, 1.0)
        self.assertAlmostEqual(replayed.oxygen_percent, low_oxygen.oxygen_percent)
        self.assertAlmostEqual(rows[-1]["oxygen_percent"], low_oxygen.oxygen_percent)

        legacy_initial = dict(initial)
        legacy_initial.pop("oxygen_setpoint_percent")
        template.oxygen_setpoint_percent = 2.0
        legacy_replayed, _ = replay_from_initial(template, legacy_initial, [1.0], 1.0, 1.0)
        self.assertAlmostEqual(legacy_replayed.oxygen_percent, low_oxygen.oxygen_percent)

    def test_replay_rejects_mixed_cell_line_or_model_version(self) -> None:
        template = CellCulture("a549")
        other_line = CellCulture("hela").snapshot()
        with self.assertRaisesRegex(ValueError, "细胞系与当前模板不一致"):
            replay_from_initial(template, other_line, [1.0], 1.0, 1.0)
        old_version = template.snapshot()
        old_version["model_version"] = "0.9.0"
        with self.assertRaisesRegex(ValueError, "模型版本不一致"):
            replay_from_initial(template, old_version, [1.0], 1.0, 1.0)

    def test_grid_search_rejects_extreme_finite_measurement_horizon(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({
            "time_h": [0.0, 1e12],
            "viable_cells": [100.0, 120.0],
        })
        with self.assertRaisesRegex(ValueError, "最长支持"):
            fit_growth_and_uptake(cell, [cell.snapshot()], measurements)
        with self.assertRaisesRegex(ValueError, "最长支持"):
            fit_with_temporal_holdout(cell, [cell.snapshot()], measurements)

    def test_calibration_entries_enforce_csv_row_resource_cap(self) -> None:
        cell = CellCulture("hela")
        times = list(range(5_001))
        measurements = pd.DataFrame({
            "time_h": times,
            "viable_cells": [100.0 + value for value in times],
        })
        for fit in (fit_growth_and_uptake, fit_with_temporal_holdout):
            with self.subTest(fit=fit.__name__):
                with self.assertRaisesRegex(ValueError, "最多接受 5,000 行观测"):
                    fit(cell, [cell.snapshot()], measurements)

    def test_direct_grid_search_rejects_duplicate_measurement_time(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({
            "time_h": [0.0, 24.0, 24.0],
            "viable_cells": [100.0, 150.0, 180.0],
        })
        with self.assertRaisesRegex(ValueError, "重复加权"):
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

    def test_score_rejects_uncovered_observations_instead_of_ignoring_them(self) -> None:
        comparison = pd.DataFrame({
            "viable_cells_observed": [100.0, 200.0],
            "viable_cells_residual": [0.0, float("nan")],
        })
        self.assertEqual(_score(comparison), float("inf"))

    def test_score_ignores_ineligible_single_point_metric(self) -> None:
        comparison = pd.DataFrame({
            "viable_cells_observed": [100.0, 200.0],
            "viable_cells_residual": [0.0, 10.0],
            "glucose_mM_observed": [5.0, float("nan")],
            "glucose_mM_residual": [float("nan"), float("nan")],
        })
        self.assertLess(_score(comparison), float("inf"))

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

    def test_temporal_calibration_respects_quality_report_metadata(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({
            "time_h": [0.0, 24.0, 48.0],
            "viable_cells": [100.0, 150.0, 200.0],
        })
        measurements.attrs["invalid_time_count"] = 1
        with self.assertRaisesRegex(ValueError, "原始 CSV"):
            fit_with_temporal_holdout(cell, [cell.snapshot()], measurements)

    def test_temporal_calibration_checks_unfitted_observed_fields(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({
            "time_h": [0.0, 24.0, 48.0],
            "viable_cells": [100.0, 150.0, 200.0],
            "oxygen_percent": [21.0, 20.0, 101.0],
        })
        with self.assertRaisesRegex(ValueError, "氧百分比"):
            fit_with_temporal_holdout(cell, [cell.snapshot()], measurements)

    def test_direct_grid_search_checks_unfitted_observed_fields(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({
            "time_h": [0.0, 24.0, 48.0],
            "viable_cells": [100.0, 150.0, 200.0],
            "pH": [7.4, 7.2, 15.0],
        })
        with self.assertRaisesRegex(ValueError, "pH 超出"):
            fit_growth_and_uptake(cell, [cell.snapshot()], measurements)

    def test_direct_grid_search_respects_original_csv_quality_metadata(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({
            "time_h": [0.0, 24.0, 48.0],
            "viable_cells": [100.0, 150.0, 200.0],
        })
        measurements.attrs["invalid_time_count"] = 1
        with self.assertRaisesRegex(ValueError, "原始 CSV"):
            fit_growth_and_uptake(cell, [cell.snapshot()], measurements)

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

    def test_invalid_weight_container_or_unknown_metric_is_rejected(self) -> None:
        cell = CellCulture("hela")
        measurements = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 120.0]})
        for invalid_weights in ([], "viable_cells", {"cell_count": 2.0}):
            with self.subTest(weights=invalid_weights):
                with self.assertRaisesRegex(ValueError, "权重"):
                    fit_growth_and_uptake(
                        cell, [cell.snapshot()], measurements,
                        invalid_weights,
                    )


if __name__ == "__main__":
    unittest.main()

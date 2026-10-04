"""实测 CSV 导入和模拟对比测试。"""

import unittest

import pandas as pd

from experiment_data import comparison_frame, residual_summary, standardize_measurements


class ExperimentDataTestCase(unittest.TestCase):
    def test_alignment_and_residual_apis_reject_wrong_container_types(self) -> None:
        with self.assertRaisesRegex(ValueError, "两个 Pandas 表格"):
            comparison_frame([], pd.DataFrame())
        with self.assertRaisesRegex(ValueError, "对齐结果表格"):
            residual_summary([])

    def test_chinese_headers_are_standardized(self) -> None:
        source = "时间,活细胞数,葡萄糖,pH\n0,100000,5.5,7.4\n24,180000,3.2,7.2\n".encode("utf-8-sig")
        data, notes = standardize_measurements(source)
        self.assertEqual(list(data.columns), ["time_h", "viable_cells", "glucose_mM", "pH"])
        self.assertEqual(len(data), 2)
        self.assertTrue(notes)

    def test_time_column_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "时间列"):
            standardize_measurements("葡萄糖\n5.5\n".encode())

    def test_empty_csv_and_non_byte_payloads_have_readable_errors(self) -> None:
        for source in (b"", b"\n", b"time_h,viable_cells\n"):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, "为空或缺少表头|不含数据行"):
                    standardize_measurements(source)
        with self.assertRaisesRegex(ValueError, "内容无效"):
            standardize_measurements(None)

    def test_malformed_csv_structure_has_readable_error(self) -> None:
        source = b'time_h,viable_cells\n0,"100\n24,150\n'
        with self.assertRaisesRegex(ValueError, "表格结构无法解析"):
            standardize_measurements(source)

    def test_invalid_source_time_is_not_silently_cleaned_for_model_use(self) -> None:
        from data_quality import quality_report

        source = b"time_h,viable_cells\n0,100\nunknown,120\n24,150\n"
        data, notes = standardize_measurements(source)
        self.assertEqual(len(data), 2)
        self.assertEqual(data.attrs["invalid_time_count"], 1)
        self.assertTrue(any("无法解析" in note for note in notes))
        report = quality_report(data)
        self.assertFalse(report["is_minimum_model_ready"])
        self.assertTrue(any("原始 CSV" in issue for issue, _ in report["blocked"]))

    def test_source_time_order_warning_survives_sorting(self) -> None:
        from data_quality import quality_report

        data, _ = standardize_measurements(b"time_h,viable_cells\n24,120\n0,100\n48,150\n")
        self.assertEqual(data["time_h"].tolist(), [0, 24, 48])
        self.assertTrue(any("时间倒序" in issue for issue, _ in quality_report(data)["warnings"]))

    def test_duplicate_time_keeps_last_row_in_original_file(self) -> None:
        source = b"time_h,viable_cells\n24,100\n0,50\n24,130\n48,180\n"
        data, notes = standardize_measurements(source)
        self.assertEqual(data["time_h"].tolist(), [0, 24, 48])
        self.assertEqual(data.loc[data["time_h"] == 24, "viable_cells"].iloc[0], 130)
        self.assertEqual(data.attrs["duplicate_time_count"], 2)
        self.assertTrue(any("重复时间" in note for note in notes))

    def test_recognized_all_missing_metric_remains_visible_to_quality_report(self) -> None:
        from data_quality import quality_report

        data, _ = standardize_measurements(
            b"time_h,viable_cells,glucose_mM\n0,100,\n24,150,\n48,200,\n"
        )
        self.assertIn("glucose_mM", data.columns)
        self.assertTrue(data["glucose_mM"].isna().all())
        report = quality_report(data)
        self.assertTrue(any("葡萄糖" in issue and "缺失值" in issue for issue, _ in report["warnings"]))

    def test_invalid_numeric_token_is_blocked_but_explicit_na_is_missing(self) -> None:
        from data_quality import quality_report

        data, notes = standardize_measurements(
            b"time_h,viable_cells,glucose_mM\n0,100,5.0\n24,150,five\n48,200,NA\n"
        )
        self.assertEqual(data.attrs["invalid_numeric_counts"]["glucose_mM"], 1)
        self.assertTrue(any("无法解析为数值" in note for note in notes))
        self.assertTrue(any("葡萄糖" in issue and "无法解析" in issue for issue, _ in quality_report(data)["blocked"]))

        valid, _ = standardize_measurements(
            b"time_h,viable_cells,glucose_mM\n0,100,5.0\n24,150,NA\n48,200,\n"
        )
        self.assertEqual(valid.attrs["invalid_numeric_counts"]["glucose_mM"], 0)
        self.assertFalse(quality_report(valid)["blocked"])

    def test_ambiguous_metric_aliases_are_not_silently_resolved(self) -> None:
        source = "time_h,glucose_mM,葡萄糖\n0,5.5,10.0\n24,4.5,9.0\n".encode("utf-8")
        with self.assertRaisesRegex(ValueError, "对应多个 CSV 列"):
            standardize_measurements(source)

    def test_duplicate_csv_header_mangled_by_pandas_is_rejected(self) -> None:
        source = b"time_h,glucose_mM,glucose_mM\n0,5.5,10.0\n24,4.5,9.0\n"
        with self.assertRaisesRegex(ValueError, "对应多个 CSV 列"):
            standardize_measurements(source)

    def test_unquoted_thousands_separator_cannot_shift_time_axis(self) -> None:
        source = b"time_h,viable_cells\n0,1,000\n24,2,000\n"
        with self.assertRaisesRegex(ValueError, "列数与表头不一致"):
            standardize_measurements(source)

    def test_explicitly_quoted_comma_is_not_silently_shifted(self) -> None:
        source = b'time_h,viable_cells\n0,"1,000"\n24,"2,000"\n'
        data, _ = standardize_measurements(source)
        self.assertEqual(data["time_h"].tolist(), [0, 24])
        # 千位格式仍需用户显式转换；不能误认为 1 或 2 个细胞。
        self.assertEqual(data.attrs["invalid_numeric_counts"]["viable_cells"], 2)

    def test_dissolved_oxygen_alias_is_not_assumed_to_be_model_proxy(self) -> None:
        source = b"time_h,viable_cells,DO\n0,100,8\n24,130,7\n"
        data, notes = standardize_measurements(source)
        self.assertNotIn("oxygen_percent", data.columns)
        self.assertTrue(any("未自动映射" in note for note in notes))
        explicit, _ = standardize_measurements(
            b"time_h,viable_cells,oxygen_percent\n0,100,18\n24,130,17\n"
        )
        self.assertIn("oxygen_percent", explicit.columns)

    def test_oversized_csv_is_rejected_before_alignment(self) -> None:
        from experiment_data import MAX_CSV_BYTES, MAX_CSV_ROWS

        with self.assertRaisesRegex(ValueError, "5 MiB"):
            standardize_measurements(b"x" * (MAX_CSV_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "5 MiB"):
            standardize_measurements(bytearray(MAX_CSV_BYTES + 1))
        rows = b"time_h,viable_cells\n" + b"0,100\n" * (MAX_CSV_ROWS + 1)
        with self.assertRaisesRegex(ValueError, "行解析上限"):
            standardize_measurements(rows)

    def test_comparison_interpolates_and_calculates_residual(self) -> None:
        simulation = pd.DataFrame({"time_h": [0, 2], "viable_cells": [100.0, 200.0]})
        observations = pd.DataFrame({"time_h": [1], "viable_cells": [140.0]})
        comparison = comparison_frame(simulation, observations)
        self.assertAlmostEqual(comparison.loc[0, "viable_cells_simulated"], 150.0)
        self.assertAlmostEqual(comparison.loc[0, "viable_cells_residual"], 10.0)
        self.assertAlmostEqual(residual_summary(comparison).loc[0, "MAE"], 10.0)

    def test_error_summary_avoids_overflow_for_large_finite_residuals(self) -> None:
        summary = residual_summary(pd.DataFrame({"viable_cells_residual": [1e308, 1e308]}))
        self.assertEqual(summary.loc[0, "MAE"], 1e308)
        self.assertEqual(summary.loc[0, "RMSE"], 1e308)

    def test_error_summary_rejects_non_finite_residuals(self) -> None:
        with self.assertRaisesRegex(ValueError, "非有限值"):
            residual_summary(pd.DataFrame({"viable_cells_residual": [float("inf")]}))

    def test_error_summary_rejects_unparseable_nonempty_residuals(self) -> None:
        with self.assertRaisesRegex(ValueError, "无法解析"):
            residual_summary(pd.DataFrame({"viable_cells_residual": [0.5, "bad"]}))

    def test_comparison_uses_last_same_time_simulation_snapshot(self) -> None:
        simulation = pd.DataFrame({
            "time_h": [1.0, 0.0, 1.0, 2.0],
            "glucose_mM": [4.0, 5.0, 6.0, 5.5],
        })
        observed = pd.DataFrame({"time_h": [1.0], "glucose_mM": [6.0]})
        comparison = comparison_frame(simulation, observed)
        self.assertEqual(comparison.loc[0, "glucose_mM_simulated"], 6.0)

    def test_comparison_rejects_boolean_times_and_measurements(self) -> None:
        simulation = pd.DataFrame({
            "time_h": [0.0, 24.0], "viable_cells": [100.0, 200.0],
        })
        boolean_time = pd.DataFrame({"time_h": [False, True], "viable_cells": [100, 200]})
        with self.assertRaisesRegex(ValueError, "实测字段 时间（h）包含布尔值"):
            comparison_frame(simulation, boolean_time)

        boolean_measurement = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [True, False]})
        with self.assertRaisesRegex(ValueError, "实测字段 活细胞数包含布尔值"):
            comparison_frame(simulation, boolean_measurement)

    def test_comparison_rejects_non_numeric_nonfinite_negative_and_duplicate_times(self) -> None:
        simulation = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 200.0]})
        for times in ([0.0, "bad"], [0.0, float("inf")], [-1.0, 24.0], [0.0, 0.0]):
            with self.subTest(times=times):
                observed = pd.DataFrame({"time_h": times, "viable_cells": [100.0, 150.0]})
                with self.assertRaisesRegex(ValueError, "时间列|重复"):
                    comparison_frame(simulation, observed)

        duplicate_simulation = pd.DataFrame({
            "time_h": [0.0, 24.0, 24.0], "viable_cells": [100.0, 180.0, 200.0],
        })
        aligned = comparison_frame(
            duplicate_simulation,
            pd.DataFrame({"time_h": [24.0], "viable_cells": [200.0]}),
        )
        self.assertEqual(aligned.loc[0, "viable_cells_simulated"], 200.0)

    def test_comparison_rejects_unparseable_or_nonfinite_measurements(self) -> None:
        simulation = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 200.0]})
        for values, message in (([100.0, "unknown"], "无法解析"), ([100.0, float("inf")], "非有限")):
            with self.subTest(values=values):
                observed = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": values})
                with self.assertRaisesRegex(ValueError, message):
                    comparison_frame(simulation, observed)

    def test_comparison_reports_nested_cell_values_as_invalid_numeric_data(self) -> None:
        simulation = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 120.0]})
        observed = pd.DataFrame({
            "time_h": [0.0, 24.0],
            "viable_cells": pd.Series([100.0, [110.0, 120.0]], dtype=object),
        })
        with self.assertRaisesRegex(ValueError, "实测字段 活细胞数包含无法解析的非空值"):
            comparison_frame(simulation, observed)

    def test_comparison_rejects_negative_numeric_metrics_on_either_side(self) -> None:
        simulation = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 200.0]})
        observed = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, -200.0]})
        with self.assertRaisesRegex(ValueError, "实测字段 活细胞数包含负值"):
            comparison_frame(simulation, observed)

        invalid_simulation = simulation.assign(viable_cells=[100.0, -200.0])
        valid_observed = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 200.0]})
        with self.assertRaisesRegex(ValueError, "模拟字段 活细胞数包含负值"):
            comparison_frame(invalid_simulation, valid_observed)

    def test_comparison_rejects_values_outside_model_state_domains(self) -> None:
        cases = (
            ("viability_percent", [0.0, 60.0], 101.0, "存活率（%）超出当前模型状态范围 0–100"),
            ("oxygen_percent", [0.0, 18.0], 22.0, "氧（%）超出当前模型状态范围 0–21"),
            ("pH", [6.5, 7.4], 8.1, "pH超出当前模型状态范围 6.2–8"),
        )
        for field, in_range, out_of_range, message in cases:
            with self.subTest(field=field):
                valid = pd.DataFrame({"time_h": [0.0, 24.0], field: in_range})
                invalid_observation = valid.assign(**{field: [in_range[0], out_of_range]})
                with self.assertRaisesRegex(ValueError, message):
                    comparison_frame(valid, invalid_observation)
                invalid_simulation = valid.assign(**{field: [in_range[0], out_of_range]})
                with self.assertRaisesRegex(ValueError, message.replace("实测字段", "模拟字段")):
                    comparison_frame(invalid_simulation, valid)

    def test_direct_alignment_and_summary_enforce_resource_limits(self) -> None:
        from experiment_data import MAX_CSV_ROWS, MAX_SIMULATION_ALIGNMENT_ROWS

        observed = pd.DataFrame({"time_h": [0.0] * (MAX_CSV_ROWS + 1)})
        with self.assertRaisesRegex(ValueError, "最多接受 5,000 行观测"):
            comparison_frame(pd.DataFrame({"time_h": [0.0]}), observed)
        simulation = pd.DataFrame({"time_h": [0.0] * (MAX_SIMULATION_ALIGNMENT_ROWS + 1)})
        with self.assertRaisesRegex(ValueError, "最多接受 25,000 行模拟历史"):
            comparison_frame(simulation, pd.DataFrame({"time_h": [0.0]}))
        with self.assertRaisesRegex(ValueError, "最多接受 5,000 行观测"):
            residual_summary(pd.DataFrame({"viable_cells_residual": [0.0] * (MAX_CSV_ROWS + 1)}))

    def test_comparison_turns_unrepresentably_large_python_integers_into_domain_errors(self) -> None:
        huge = 10**10000
        simulation = pd.DataFrame({
            "time_h": pd.Series([0, 24], dtype=object),
            "viable_cells": pd.Series([100, 200], dtype=object),
        })
        observed = pd.DataFrame({
            "time_h": pd.Series([0, 24], dtype=object),
            "viable_cells": pd.Series([100, huge], dtype=object),
        })
        with self.assertRaisesRegex(ValueError, "数值或缺失值|非有限|无法解析"):
            comparison_frame(simulation, observed)

        oversized_time = pd.DataFrame({
            "time_h": pd.Series([0, huge], dtype=object),
            "viable_cells": pd.Series([100, 200], dtype=object),
        })
        with self.assertRaisesRegex(ValueError, "时间列"):
            comparison_frame(simulation, oversized_time)

    def test_comparison_does_not_extrapolate_beyond_simulation_history(self) -> None:
        simulation = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 200.0]})
        observed = pd.DataFrame({"time_h": [12.0, 48.0], "viable_cells": [140.0, 300.0]})
        comparison = comparison_frame(simulation, observed)
        self.assertEqual(comparison.loc[0, "viable_cells_simulated"], 150.0)
        self.assertTrue(pd.isna(comparison.loc[1, "viable_cells_simulated"]))


if __name__ == "__main__":
    unittest.main()

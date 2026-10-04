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

    def test_comparison_does_not_extrapolate_beyond_simulation_history(self) -> None:
        simulation = pd.DataFrame({"time_h": [0.0, 24.0], "viable_cells": [100.0, 200.0]})
        observed = pd.DataFrame({"time_h": [12.0, 48.0], "viable_cells": [140.0, 300.0]})
        comparison = comparison_frame(simulation, observed)
        self.assertEqual(comparison.loc[0, "viable_cells_simulated"], 150.0)
        self.assertTrue(pd.isna(comparison.loc[1, "viable_cells_simulated"]))


if __name__ == "__main__":
    unittest.main()

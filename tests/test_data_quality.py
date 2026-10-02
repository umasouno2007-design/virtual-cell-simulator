import unittest
import pandas as pd

from data_quality import quality_report


class DataQualityTests(unittest.TestCase):
    def test_negative_value_blocks_minimum_model_readiness(self):
        result = quality_report(pd.DataFrame({"time_h": [0, 24], "glucose_mM": [10, -1]}))
        self.assertFalse(result["is_minimum_model_ready"])
        self.assertTrue(any("负值" in item[0] for item in result["blocked"]))

    def test_short_series_warns_about_holdout(self):
        result = quality_report(pd.DataFrame({"time_h": [0, 24, 48], "viable_cells": [1, 2, 3]}))
        self.assertTrue(any("留出" in item[0] for item in result["warnings"]))

    def test_missing_initial_observation_and_unsorted_direct_data_are_warned(self):
        data = pd.DataFrame({"time_h": [24, 12, 48], "viable_cells": [2, 1, 3]})
        result = quality_report(data)
        self.assertTrue(any("时间倒序" in issue for issue, _ in result["warnings"]))
        self.assertTrue(any("起始时间点" in issue for issue, _ in result["warnings"]))

    def test_duplicate_metadata_warns(self):
        data = pd.DataFrame({"time_h": [0, 24], "viable_cells": [1, 2]})
        data.attrs["duplicate_time_count"] = 2
        result = quality_report(data)
        self.assertTrue(any("重复" in item[0] for item in result["warnings"]))

    def test_non_finite_time_or_measurement_blocks_readiness(self):
        bad_time = quality_report(pd.DataFrame({"time_h": [0, float("inf")], "viable_cells": [1, 2]}))
        self.assertTrue(any("非有限" in item[0] for item in bad_time["blocked"]))

        bad_value = quality_report(pd.DataFrame({"time_h": [0, 24, 48], "glucose_mM": [10, float("inf"), 8]}))
        self.assertTrue(any("无穷值" in item[0] for item in bad_value["blocked"]))

    def test_missing_measurement_values_are_reported_as_warning(self):
        result = quality_report(pd.DataFrame({"time_h": [0, 24, 48], "glucose_mM": [10, None, 8]}))
        self.assertTrue(any("缺失值" in item[0] for item in result["warnings"]))

    def test_direct_dataframe_text_is_not_counted_as_numeric_observation(self):
        data = pd.DataFrame({
            "time_h": [0, 24, 48], "glucose_mM": ["5.0", "five", "NA"],
        })
        result = quality_report(data)
        self.assertFalse(result["is_minimum_model_ready"])
        self.assertTrue(any("无法解析为数值" in issue for issue, _ in result["blocked"]))
        self.assertTrue(any("缺少可校准指标" in issue for issue, _ in result["blocked"]))

    def test_invalid_oxygen_or_ph_scale_is_blocked(self):
        high_oxygen = quality_report(pd.DataFrame({
            "time_h": [0, 24, 48], "oxygen_percent": [21, 25, 101], "viable_cells": [1, 2, 3],
        }))
        self.assertTrue(any("氧百分比" in item[0] for item in high_oxygen["blocked"]))

        high_ph = quality_report(pd.DataFrame({
            "time_h": [0, 24, 48], "pH": [7.2, 7.4, 15], "viable_cells": [1, 2, 3],
        }))
        self.assertTrue(any("pH 超出" in item[0] for item in high_ph["blocked"]))

    def test_oxygen_saturation_percent_is_not_silently_compared_as_model_proxy(self):
        saturation = quality_report(pd.DataFrame({
            "time_h": [0, 24, 48], "oxygen_percent": [80, 75, 70], "viable_cells": [1, 2, 3],
        }))
        self.assertTrue(any("超过模型 0–21%" in issue for issue, _ in saturation["blocked"]))

        within_range = quality_report(pd.DataFrame({
            "time_h": [0, 24, 48], "oxygen_percent": [18, 17, 16], "viable_cells": [1, 2, 3],
        }))
        self.assertTrue(any("氧列需要单独核对" in issue for issue, _ in within_range["warnings"]))

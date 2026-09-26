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

    def test_duplicate_metadata_warns(self):
        data = pd.DataFrame({"time_h": [0, 24], "viable_cells": [1, 2]})
        data.attrs["duplicate_time_count"] = 2
        result = quality_report(data)
        self.assertTrue(any("重复" in item[0] for item in result["warnings"]))

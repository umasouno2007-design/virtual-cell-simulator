"""Shared numerical helper boundaries."""

import unittest
import pandas as pd

from numeric_utils import checked_time_advance, clamp_finite


class ClampFiniteTests(unittest.TestCase):
    def test_clamps_finite_values_and_maps_nonfinite_values_to_lower_bound(self) -> None:
        self.assertEqual(clamp_finite(-4.0), 0.0)
        self.assertEqual(clamp_finite(50.0), 50.0)
        self.assertEqual(clamp_finite(140.0), 100.0)
        self.assertEqual(clamp_finite(float("nan")), 0.0)
        self.assertEqual(clamp_finite(float("inf"), -1.0, 1.0), -1.0)

    def test_malformed_values_are_not_silently_coerced(self) -> None:
        with self.assertRaises((TypeError, ValueError)):
            clamp_finite(None)

    def test_boolean_clock_values_are_not_accepted_as_numeric_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "模拟时钟无法安全推进"):
            checked_time_advance(True, 0.25)
        with self.assertRaisesRegex(ValueError, "模拟时钟无法安全推进"):
            checked_time_advance(0.0, False)

    def test_numpy_boolean_clock_values_are_not_accepted_as_numeric_time(self) -> None:
        pandas_boolean = pd.Series([True]).iloc[0]
        with self.assertRaisesRegex(ValueError, "模拟时钟无法安全推进"):
            checked_time_advance(pandas_boolean, 0.25)
        with self.assertRaisesRegex(ValueError, "模拟时钟无法安全推进"):
            checked_time_advance(0.0, pandas_boolean)


if __name__ == "__main__":
    unittest.main()

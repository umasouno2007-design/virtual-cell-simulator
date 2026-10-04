"""Shared numerical helper boundaries."""

import unittest

from numeric_utils import clamp_finite


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


if __name__ == "__main__":
    unittest.main()

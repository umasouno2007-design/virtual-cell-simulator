"""细胞周期导航测试。"""

import unittest
import pandas as pd

from cell_cycle_navigation import next_cycle_checkpoint


class CellCycleNavigationTestCase(unittest.TestCase):
    def test_g1_navigation_targets_s_phase_boundary(self) -> None:
        checkpoint = next_cycle_checkpoint(20.0, 80.0, 32.0)
        self.assertEqual(checkpoint["next_phase"], "S")
        self.assertEqual(checkpoint["target_progress"], 45.0)
        self.assertGreater(checkpoint["estimated_hours"], 0)

    def test_m_navigation_wraps_to_g1(self) -> None:
        checkpoint = next_cycle_checkpoint(95.0, 100.0, 24.0)
        self.assertEqual(checkpoint["next_phase"], "G1")
        self.assertEqual(checkpoint["target_progress"], 0.0)
        self.assertAlmostEqual(checkpoint["estimated_hours"], 1.2)

    def test_invalid_or_unrepresentable_inputs_are_rejected(self) -> None:
        pandas_boolean = pd.Series([True]).iloc[0]
        for values in (
            (-1.0, 80.0, 32.0), (101.0, 80.0, 32.0),
            (20.0, -1.0, 32.0), (20.0, 101.0, 32.0),
            (20.0, 80.0, 0.0), (20.0, 80.0, 501.0),
            (float("nan"), 80.0, 32.0), (20.0, float("inf"), 32.0),
            (20.0, 80.0, 10**10000), (pandas_boolean, 80.0, 32.0),
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    next_cycle_checkpoint(*values)


if __name__ == "__main__":
    unittest.main()

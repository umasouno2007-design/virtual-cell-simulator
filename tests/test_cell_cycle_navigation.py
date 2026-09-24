"""细胞周期导航测试。"""

import unittest

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


if __name__ == "__main__":
    unittest.main()

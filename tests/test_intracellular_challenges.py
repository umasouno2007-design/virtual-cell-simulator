"""细胞内互动挑战判定测试。"""

import unittest

from intracellular_challenges import evaluate_challenge


class IntracellularChallengeTestCase(unittest.TestCase):
    def test_oxidative_recovery_requires_all_status_checks(self) -> None:
        report = evaluate_challenge("oxidative_recovery", {
            "ros_percent": 18.0,
            "dna_damage_percent": 9.0,
            "apoptosis_signal_percent": 12.0,
        })
        self.assertTrue(report["completed"])
        self.assertEqual(report["progress"], 1.0)

    def test_energy_checkpoint_reports_partial_progress(self) -> None:
        report = evaluate_challenge("energy_checkpoint", {
            "mitochondrial_potential_percent": 75.0,
            "atp_percent": 55.0,
            "cycle_progress_percent": 25.0,
        })
        self.assertFalse(report["completed"])
        self.assertAlmostEqual(report["progress"], 2 / 3)


if __name__ == "__main__":
    unittest.main()

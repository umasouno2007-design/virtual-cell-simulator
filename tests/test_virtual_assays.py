"""虚拟检测的可重复性与边界测试。"""

import unittest

from virtual_assays import simulate_virtual_assay


class VirtualAssayTestCase(unittest.TestCase):
    def test_zero_noise_is_reproducible_and_traces_source_metric(self) -> None:
        snapshot = {"ATP_percent": 80.0}
        rows = simulate_virtual_assay(
            "atp_luminescence", snapshot, replicates=3, noise_percent=0, seed=8
        )
        self.assertEqual([row["value"] for row in rows], [80000.0, 80000.0, 80000.0])
        self.assertTrue(all(row["is_synthetic_demo"] for row in rows))
        self.assertTrue(all(row["source_metric"] == "ATP_percent" for row in rows))

    def test_same_seed_produces_same_noisy_replicates(self) -> None:
        snapshot = {"ROS_percent": 30.0}
        first = simulate_virtual_assay("ros_fluorescence", snapshot, seed=11)
        second = simulate_virtual_assay("ros_fluorescence", snapshot, seed=11)
        self.assertEqual(first, second)

    def test_invalid_synthetic_assay_inputs_are_rejected_not_clipped(self) -> None:
        snapshot = {"ROS_percent": 30.0}
        for kwargs in (
            {"replicates": 0}, {"replicates": 13}, {"replicates": 2.5},
            {"noise_percent": float("nan")}, {"noise_percent": -1.0},
            {"noise_percent": 31.0}, {"seed": True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    simulate_virtual_assay("ros_fluorescence", snapshot, **kwargs)
        for invalid in (-1.0, 101.0, float("inf"), float("nan"), True):
            with self.subTest(index=invalid):
                with self.assertRaises(ValueError):
                    simulate_virtual_assay("ros_fluorescence", {"ROS_percent": invalid})


if __name__ == "__main__":
    unittest.main()

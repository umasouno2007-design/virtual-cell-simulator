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


if __name__ == "__main__":
    unittest.main()

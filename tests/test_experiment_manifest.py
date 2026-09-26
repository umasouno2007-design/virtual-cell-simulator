"""实验配置快照测试。"""

import unittest

from cell import CellCulture
from experiment_manifest import build_manifest


class ExperimentManifestTestCase(unittest.TestCase):
    def test_manifest_is_compact_and_traces_parameters(self) -> None:
        cell = CellCulture("hela")
        manifest = build_manifest(
            cell, app_version="test", preset_name="标准培养", app_mode="细胞培养",
            time_multiplier=60, history=[cell.snapshot()], events=[{"event": "创建实验"}],
            scheduled_actions=[{"at_time_h": 24, "action": "补充葡萄糖", "status": "pending"}],
            experiment_metadata={"passage_number": "P12", "mycoplasma_status": "阴性"},
        )
        self.assertEqual(manifest["schema"], "e-cell-experiment-manifest/v1")
        self.assertEqual(manifest["experiment"]["profile_key"], "hela")
        self.assertIn("growth_scale", manifest["parameters"])
        self.assertEqual(manifest["history_summary"]["point_count"], 1)
        self.assertEqual(manifest["events"][0]["event"], "创建实验")
        self.assertEqual(manifest["scheduled_actions"][0]["at_time_h"], 24)
        self.assertEqual(manifest["experiment_metadata"]["passage_number"], "P12")


if __name__ == "__main__":
    unittest.main()

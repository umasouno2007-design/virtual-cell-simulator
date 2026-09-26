import unittest

from scenario import export_scenario, import_scenario
from cell import CellCulture


class ScenarioTests(unittest.TestCase):
    def test_export_import_replays_same_step(self):
        original = CellCulture("a549")
        original.oxygen_percent = 12.0
        payload = export_scenario(original, duration_h=24, dt_h=1)
        restored, imported = import_scenario(payload)
        original.step(6)
        restored.step(6)
        self.assertEqual(imported["schema"], "e-cell-scenario/v1")
        self.assertAlmostEqual(original.viable_cells, restored.viable_cells, places=7)
        self.assertAlmostEqual(original.glucose_mm, restored.glucose_mm, places=7)

    def test_missing_field_is_explained(self):
        with self.assertRaisesRegex(ValueError, "缺少字段"):
            import_scenario({"schema": "e-cell-scenario/v1"})

    def test_illegal_range_is_rejected(self):
        payload = export_scenario(CellCulture("a549"))
        payload["run"]["dt_h"] = -1
        with self.assertRaisesRegex(ValueError, "总时长或步长"):
            import_scenario(payload)

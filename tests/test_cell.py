"""研究型培养模型的基础测试。"""

import unittest

from cell import CellCulture
from profiles import CELL_PROFILES
from simulation import new_simulation, run_steps


class CellCultureTestCase(unittest.TestCase):
    def test_all_profiles_can_start(self) -> None:
        for key in CELL_PROFILES:
            cell, history = new_simulation(key)
            self.assertEqual(cell.profile_key, key)
            self.assertEqual(len(history), 1)
            self.assertGreater(cell.viable_cells, 0)

    def test_standard_culture_grows_and_uses_glucose(self) -> None:
        cell = CellCulture("hela")
        cells_before = cell.viable_cells
        glucose_before = cell.glucose_mm
        cell.step(1.0)
        self.assertGreater(cell.viable_cells, cells_before)
        self.assertLess(cell.glucose_mm, glucose_before)
        self.assertGreater(cell.lactate_mm, 0)

    def test_profile_media_conditions_are_distinct(self) -> None:
        hela = CellCulture("hela")
        a549 = CellCulture("a549")
        self.assertNotEqual(hela.profile.medium, a549.profile.medium)
        self.assertNotEqual(hela.glucose_mm, a549.glucose_mm)

    def test_low_ph_reduces_growth(self) -> None:
        control = CellCulture("hela")
        acidic = CellCulture("hela")
        acidic.ph = 6.6
        control.step(4.0)
        acidic.step(4.0)
        self.assertGreater(control.viable_cells, acidic.viable_cells)

    def test_drug_effect_depends_on_ic50(self) -> None:
        control = CellCulture("a549")
        treated = CellCulture("a549")
        treated.parameters.drug_ic50_um = 2.0
        treated.add_drug(20.0)
        control.step(4.0)
        treated.step(4.0)
        self.assertGreater(control.viable_cells, treated.viable_cells)

    def test_medium_exchange_restores_medium(self) -> None:
        cell = CellCulture("hek293")
        cell.glucose_mm = 0.5
        cell.lactate_mm = 12.0
        cell.drug_um = 5.0
        cell.exchange_medium(1.0)
        self.assertAlmostEqual(cell.glucose_mm, cell.profile.initial_glucose_mm)
        self.assertEqual(cell.lactate_mm, 0.0)
        self.assertEqual(cell.drug_um, 0.0)

    def test_glucose_can_be_supplemented(self) -> None:
        cell = CellCulture("hela")
        before = cell.glucose_mm
        cell.add_glucose(1.5)
        self.assertAlmostEqual(cell.glucose_mm, before + 1.5)

    def test_high_density_has_contact_inhibition(self) -> None:
        low = CellCulture("hek293")
        high = CellCulture("hek293", viable_cells=6.5e4 * 25.0)
        self.assertGreater(
            low.growth_modifiers()["contact"],
            high.growth_modifiers()["contact"],
        )

    def test_snapshot_has_units(self) -> None:
        snapshot = CellCulture("hela").snapshot()
        for key in ("time_h", "glucose_mM", "lactate_mM", "temperature_C", "drug_uM"):
            self.assertIn(key, snapshot)

    def test_run_steps_records_each_step(self) -> None:
        cell, history = new_simulation("a549")
        completed = run_steps(cell, history, 12, 0.5)
        self.assertEqual(completed, 12)
        self.assertEqual(len(history), 13)
        self.assertAlmostEqual(cell.time_h, 6.0)

    def test_invalid_initial_values_and_state_do_not_create_nonfinite_snapshot(self) -> None:
        cell = CellCulture("hela", culture_volume_ml=-1, surface_area_cm2=float("nan"), viable_cells=-5)
        self.assertEqual(cell.viable_cells, 0.0)
        self.assertGreaterEqual(cell.culture_volume_ml, 0.1)
        self.assertGreaterEqual(cell.surface_area_cm2, 0.1)
        cell.viable_cells = 1000
        cell.glucose_mm = float("nan")
        cell.lactate_mm = -3
        cell.oxygen_percent = float("inf")
        cell.step(1.0)
        snapshot = cell.snapshot()
        self.assertGreaterEqual(snapshot["glucose_mM"], 0)
        self.assertGreaterEqual(snapshot["lactate_mM"], 0)
        self.assertLessEqual(snapshot["oxygen_percent"], 21)

    def test_zero_saturation_parameters_do_not_divide_by_zero(self) -> None:
        cell = CellCulture("hela")
        cell.parameters.glucose_half_saturation_mm = 0
        cell.parameters.glutamine_half_saturation_mm = 0
        cell.parameters.oxygen_half_saturation_percent = 0
        cell.parameters.lactate_inhibition_mm = 0
        cell.glucose_mm = 0
        cell.glutamine_mm = 0
        cell.oxygen_percent = 0
        modifiers = cell.growth_modifiers()
        self.assertTrue(all(0 <= value <= 1 for value in modifiers.values()))


if __name__ == "__main__":
    unittest.main()

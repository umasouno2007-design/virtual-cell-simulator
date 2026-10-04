"""研究型培养模型的基础测试。"""

import math
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
        for key in ("time_h", "glucose_mM", "lactate_mM", "temperature_C", "drug_uM", "oxygen_setpoint_percent", "model_version"):
            self.assertIn(key, snapshot)
        self.assertNotEqual(snapshot["model_version"], "")

    def test_run_steps_records_each_step(self) -> None:
        cell, history = new_simulation("a549")
        completed = run_steps(cell, history, 12, 0.5)
        self.assertEqual(completed, 12)
        self.assertEqual(len(history), 13)
        self.assertAlmostEqual(cell.time_h, 6.0)

    def test_run_steps_rejects_non_progressing_or_truncated_step(self) -> None:
        cell, history = new_simulation("a549")
        for invalid in (0.0, -1.0, 7.0, float("nan"), float("inf"), True):
            with self.subTest(dt_h=invalid):
                with self.assertRaisesRegex(ValueError, "每步时长"):
                    run_steps(cell, history, 1, invalid)
        self.assertEqual(len(history), 1)
        self.assertEqual(cell.time_h, 0.0)

    def test_run_steps_rejects_non_integer_count_without_partial_progress(self) -> None:
        cell, history = new_simulation("a549")
        for invalid in (-1, 1.5, True, "2", float("nan"), None):
            with self.subTest(steps=invalid):
                with self.assertRaisesRegex(ValueError, "模拟步数"):
                    run_steps(cell, history, invalid)
                self.assertEqual(cell.time_h, 0.0)
                self.assertEqual(len(history), 1)
        self.assertEqual(run_steps(cell, history, 0), 0)

    def test_direct_step_rejects_truncated_or_nonfinite_duration(self) -> None:
        cell = CellCulture("hela")
        before = cell.snapshot()
        for invalid in (-1.0, 6.1, float("nan"), float("inf"), None, True):
            with self.subTest(dt_h=invalid):
                with self.assertRaisesRegex(ValueError, "培养单步时长"):
                    cell.step(invalid)
        cell.step(0.0)
        self.assertEqual(cell.snapshot(), before)

    def test_nonfinite_culture_actions_leave_state_unchanged(self) -> None:
        cell = CellCulture("hela")
        before = cell.snapshot()
        actions = (
            (cell.exchange_medium, float("nan")),
            (cell.add_drug, float("inf")),
            (cell.add_glucose, float("nan")),
        )
        for action, invalid in actions:
            with self.subTest(action=action.__name__):
                with self.assertRaisesRegex(ValueError, "有限数值"):
                    action(invalid)
        self.assertEqual(cell.snapshot(), before)

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

    def test_nonfinite_environment_does_not_contaminate_growth_history(self) -> None:
        cell = CellCulture("hela")
        cell.temperature_c = float("nan")
        cell.co2_percent = float("inf")
        cell.osmolality_mosm_kg = float("nan")
        cell.oxygen_setpoint_percent = float("inf")
        cell.step(1.0)
        snapshot = cell.snapshot()
        self.assertTrue(all(math.isfinite(value) for value in snapshot.values() if isinstance(value, float)))
        self.assertEqual(cell.temperature_c, cell.profile.temperature_c)
        self.assertEqual(cell.co2_percent, cell.profile.co2_percent)

    def test_nonfinite_model_parameter_is_rejected_before_growth_calculation(self) -> None:
        for invalid in (float("nan"), float("inf"), True, "fast"):
            cell = CellCulture("hela")
            cell.parameters.growth_scale = invalid
            with self.subTest(value=invalid):
                with self.assertRaisesRegex(ValueError, "growth_scale"):
                    cell.step(1.0)
                self.assertEqual(cell.time_h, 0.0)

    def test_culture_clock_precision_loss_is_rejected_before_state_changes(self) -> None:
        cell = CellCulture("hela")
        cell.time_h = 1e20
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "模拟时钟无法安全推进"):
            cell.step(0.25)
        self.assertEqual(cell.snapshot(), before)

    def test_large_finite_cell_counts_do_not_fake_zero_viability_or_overflow(self) -> None:
        cell = CellCulture("hela", viable_cells=1.7e308)
        cell.dead_cells = 1.7e308
        self.assertAlmostEqual(cell.viability_percent, 50.0)

        cell = CellCulture("hela", surface_area_cm2=1e305, viable_cells=1.7e308)
        cell.parameters.growth_scale = 20.0
        with self.assertRaisesRegex(ValueError, "细胞数量超出当前软件的数值安全范围"):
            cell.step(1.0)
        self.assertTrue(math.isfinite(cell.viable_cells))
        self.assertEqual(cell.time_h, 0.0)

    def test_negative_rate_or_uptake_cannot_create_negative_outputs(self) -> None:
        for name in ("death_rate_per_h", "uptake_scale", "oxygen_transfer_per_h"):
            cell = CellCulture("hela")
            before = cell.snapshot()
            setattr(cell.parameters, name, -0.1)
            with self.subTest(parameter=name):
                with self.assertRaisesRegex(ValueError, name):
                    cell.step(1.0)
                self.assertEqual(cell.snapshot(), before)

    def test_extreme_finite_growth_and_drug_inputs_stay_bounded(self) -> None:
        cell = CellCulture("hela")
        cell.parameters.growth_scale = 1e308
        with self.assertRaisesRegex(ValueError, "数值安全范围"):
            cell.step(1.0)
        self.assertEqual(cell.time_h, 0.0)

        treated = CellCulture("hela")
        treated.drug_um = 1e308
        treated.parameters.drug_hill = 100.0
        modifier = treated.growth_modifiers()["drug"]
        self.assertTrue(math.isfinite(modifier))
        self.assertGreaterEqual(modifier, 0.0)
        self.assertLessEqual(modifier, 1.0)

    def test_stable_hill_calculation_matches_original_formula_in_normal_range(self) -> None:
        cell = CellCulture("hela")
        for concentration in (0.0, 2.0, 10.0, 20.0):
            cell.drug_um = concentration
            expected = 1.0 / (
                1.0 + (concentration / cell.parameters.drug_ic50_um) ** cell.parameters.drug_hill
            )
            with self.subTest(drug_um=concentration):
                self.assertAlmostEqual(cell.growth_modifiers()["drug"], expected)

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

    def test_direct_growth_modifiers_do_not_propagate_nonfinite_environment(self) -> None:
        cell = CellCulture("hela")
        cell.ph = float("nan")
        cell.temperature_c = float("inf")
        cell.osmolality_mosm_kg = float("nan")
        cell.viable_cells = float("inf")
        modifiers = cell.growth_modifiers()
        self.assertTrue(all(math.isfinite(value) and 0 <= value <= 1 for value in modifiers.values()))


if __name__ == "__main__":
    unittest.main()

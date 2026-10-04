"""研究型培养模型的基础测试。"""

import math
import unittest
from dataclasses import fields
import pandas as pd

from cell import CellCulture, ModelParameters
from profiles import CELL_PROFILES
from simulation import new_simulation, run_steps


class CellCultureTestCase(unittest.TestCase):
    def test_all_profiles_can_start(self) -> None:
        for key in CELL_PROFILES:
            cell, history = new_simulation(key)
            self.assertEqual(cell.profile_key, key)
            self.assertEqual(len(history), 1)
            self.assertGreater(cell.viable_cells, 0)

    def test_unknown_cell_profile_is_not_silently_replaced_with_hela(self) -> None:
        for invalid in ("A549", "typo", None, []):
            with self.subTest(profile=invalid):
                with self.assertRaisesRegex(ValueError, "不支持的细胞系配置"):
                    CellCulture(invalid)

    def test_unknown_experiment_preset_is_not_silently_replaced_with_standard(self) -> None:
        for invalid in ("低氧", "typo", None, []):
            with self.subTest(preset=invalid):
                with self.assertRaisesRegex(ValueError, "不支持的实验预设"):
                    new_simulation("a549", preset_name=invalid)

    def test_boolean_culture_constructor_inputs_are_rejected(self) -> None:
        invalid_inputs = (
            {"culture_volume_ml": True},
            {"surface_area_cm2": False},
            {"viable_cells": True},
        )
        for kwargs in invalid_inputs:
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, "不能使用布尔值代替"):
                    CellCulture("a549", **kwargs)

    def test_constructor_rejects_wrong_parameter_container_instead_of_using_defaults(self) -> None:
        for invalid in ({}, [], False, "growth_scale=2"):
            with self.subTest(parameters=invalid):
                with self.assertRaisesRegex(ValueError, "ModelParameters 对象或 None"):
                    CellCulture("hela", parameters=invalid)

    def test_pandas_boolean_scalar_is_not_accepted_as_culture_number(self) -> None:
        pandas_boolean = pd.Series([True]).iloc[0]
        with self.assertRaisesRegex(ValueError, "不能使用布尔值代替"):
            CellCulture("a549", viable_cells=pandas_boolean)
        cell = CellCulture("a549")
        with self.assertRaisesRegex(ValueError, "培养单步时长"):
            cell.step(pandas_boolean)
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "不能使用布尔值代替"):
            cell.add_drug(pandas_boolean)
        self.assertEqual(cell.snapshot(), before)

    def test_boolean_culture_actions_are_rejected_without_state_changes(self) -> None:
        cell = CellCulture("a549")
        before = cell.snapshot()
        for action in (
            lambda: cell.exchange_medium(True),
            lambda: cell.add_drug(True),
            lambda: cell.add_glucose(True),
        ):
            with self.subTest(action=action):
                with self.assertRaisesRegex(ValueError, "不能使用布尔值代替"):
                    action()
                self.assertEqual(cell.snapshot(), before)

    def test_negative_culture_actions_are_rejected_not_silently_clipped(self) -> None:
        cell = CellCulture("a549")
        before = cell.snapshot()
        for action in (
            lambda: cell.exchange_medium(-0.1),
            lambda: cell.add_drug(-1.0),
            lambda: cell.add_glucose(-1.0),
        ):
            with self.subTest(action=action):
                with self.assertRaisesRegex(ValueError, "不能为负数"):
                    action()
                self.assertEqual(cell.snapshot(), before)

    def test_medium_exchange_rejects_fraction_above_one_without_mutation(self) -> None:
        cell = CellCulture("a549")
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "换液比例必须在 0–1 范围内"):
            cell.exchange_medium(1.01)
        self.assertEqual(cell.snapshot(), before)

    def test_unrepresentably_large_constructor_and_action_values_are_handled_safely(self) -> None:
        huge = 10**10000
        cell = CellCulture(
            "a549", culture_volume_ml=huge, surface_area_cm2=huge, viable_cells=huge,
        )
        self.assertEqual(cell.culture_volume_ml, 0.1)
        self.assertEqual(cell.surface_area_cm2, 0.1)
        self.assertEqual(cell.viable_cells, 0.0)
        before = cell.snapshot()
        for action in (
            lambda: cell.exchange_medium(huge),
            lambda: cell.add_drug(huge),
            lambda: cell.add_glucose(huge),
        ):
            with self.subTest(action=action):
                with self.assertRaisesRegex(ValueError, "有限数值"):
                    action()
                self.assertEqual(cell.snapshot(), before)

    def test_medium_exchange_is_atomic_when_a_late_field_is_invalid(self) -> None:
        cell = CellCulture("a549")
        cell.glucose_mm = 2.0
        cell.glutamine_mm = "invalid"
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "培养状态 glutamine_mm"):
            cell.exchange_medium(0.5)
        self.assertEqual(cell.snapshot(), before)

    def test_medium_exchange_rejects_nonfinite_state_without_partial_changes(self) -> None:
        cell = CellCulture("a549")
        cell.osmolality_mosm_kg = float("inf")
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "不是有效有限数值"):
            cell.exchange_medium(0.5)
        self.assertEqual(cell.snapshot(), before)

    def test_medium_exchange_rejects_unrepresentably_large_state_atomically(self) -> None:
        cell = CellCulture("a549")
        cell.glucose_mm = 10**10000
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "培养状态 glucose_mm"):
            cell.exchange_medium(0.5)
        self.assertEqual(cell.snapshot(), before)

    def test_glucose_addition_rejects_invalid_existing_medium_without_mutation(self) -> None:
        for invalid in (-1.0, True, "invalid", float("nan"), float("inf"), 10**10000):
            with self.subTest(value_type=type(invalid).__name__):
                cell = CellCulture("a549")
                cell.glucose_mm = invalid
                before = cell.snapshot()
                with self.assertRaisesRegex(ValueError, "培养状态 glucose_mm"):
                    cell.add_glucose(1.0)
                self.assertEqual(cell.snapshot(), before)

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

    def test_run_steps_rolls_back_the_whole_batch_when_a_later_step_fails(self) -> None:
        cell, history = new_simulation("a549")
        before_cell = cell.snapshot()
        before_history = [row.copy() for row in history]
        original_step = cell.step
        calls = 0

        def fail_second_step(dt_h: float) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected failure")
            original_step(dt_h)

        cell.step = fail_second_step
        with self.assertRaisesRegex(RuntimeError, "injected failure"):
            run_steps(cell, history, steps=3, dt_h=1.0)
        self.assertEqual(cell.snapshot(), before_cell)
        self.assertEqual(history, before_history)

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
        for invalid in (-1, 1.5, True, "2", float("nan"), None, 10**10000, 10_001):
            with self.subTest(steps=invalid):
                with self.assertRaisesRegex(ValueError, "模拟步数"):
                    run_steps(cell, history, invalid)
                self.assertEqual(cell.time_h, 0.0)
                self.assertEqual(len(history), 1)
        self.assertEqual(run_steps(cell, history, 0), 0)

    def test_run_steps_rejects_wrong_state_and_history_containers(self) -> None:
        cell, history = new_simulation("a549")
        with self.assertRaisesRegex(ValueError, "CellCulture 对象"):
            run_steps(object(), history, steps=0)
        with self.assertRaisesRegex(ValueError, "历史必须是可追加的列表"):
            run_steps(cell, tuple(history), steps=1)
        self.assertEqual(cell.time_h, 0.0)
        self.assertEqual(history, [cell.snapshot()])

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

    def test_unrepresentably_large_integer_parameter_is_rejected_atomically(self) -> None:
        cell = CellCulture("a549")
        cell.parameters.growth_scale = 10**10000
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "growth_scale"):
            cell.step(0.25)
        self.assertEqual(cell.snapshot(), before)

    def test_unrepresentably_large_duration_is_rejected_as_user_input(self) -> None:
        cell = CellCulture("hela")
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "培养单步时长"):
            cell.step(10**10000)
        self.assertEqual(cell.snapshot(), before)

        cell, history = new_simulation("a549")
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "每步时长"):
            run_steps(cell, history, steps=1, dt_h=10**10000)
        self.assertEqual(cell.snapshot(), before)
        self.assertEqual(len(history), 1)

    def test_every_model_parameter_rejects_invalid_types_and_nonfinite_values_atomically(self) -> None:
        for model_field in fields(ModelParameters):
            for invalid in (True, float("nan"), float("inf"), "invalid"):
                with self.subTest(parameter=model_field.name, value=invalid):
                    cell = CellCulture("a549")
                    setattr(cell.parameters, model_field.name, invalid)
                    before = cell.snapshot()
                    with self.assertRaisesRegex(ValueError, model_field.name):
                        cell.step(0.25)
                    self.assertEqual(cell.snapshot(), before)

    def test_each_parameter_sign_constraint_is_explicitly_covered(self) -> None:
        nonnegative = {
            "growth_scale", "uptake_scale", "death_rate_per_h",
            "glucose_half_saturation_mm", "glutamine_half_saturation_mm",
            "oxygen_half_saturation_percent", "lactate_inhibition_mm",
            "oxygen_transfer_per_h",
        }
        positive = {"drug_ic50_um", "drug_hill", "buffer_capacity_mm_per_ph"}
        self.assertEqual(nonnegative | positive, {field.name for field in fields(ModelParameters)})
        for name in sorted(nonnegative | positive):
            invalid_values = [-1.0, 0.0] if name in positive else [-1.0]
            for invalid in invalid_values:
                with self.subTest(parameter=name, value=invalid):
                    cell = CellCulture("a549")
                    setattr(cell.parameters, name, invalid)
                    before = cell.snapshot()
                    with self.assertRaisesRegex(ValueError, name):
                        cell.step(0.25)
                    self.assertEqual(cell.snapshot(), before)

    def test_invalid_model_parameter_does_not_partially_repair_culture_state(self) -> None:
        cell = CellCulture("hela")
        cell.oxygen_setpoint_percent = 30.0
        cell.parameters.growth_scale = float("nan")
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "growth_scale"):
            cell.step(1.0)
        self.assertEqual(cell.snapshot(), before)

    def test_numeric_safety_failure_rolls_back_all_pre_step_cleanup(self) -> None:
        cell = CellCulture("hela")
        cell.oxygen_setpoint_percent = 30.0
        cell.parameters.growth_scale = 1e6
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "增长指数超出"):
            cell.step(1.0)
        self.assertEqual(cell.snapshot(), before)

    def test_culture_clock_precision_loss_is_rejected_before_state_changes(self) -> None:
        cell = CellCulture("hela")
        cell.time_h = 1e20
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "模拟时钟无法安全推进"):
            cell.step(0.25)
        self.assertEqual(cell.snapshot(), before)

    def test_boolean_culture_clock_is_rejected_before_state_changes(self) -> None:
        cell = CellCulture("hela")
        cell.time_h = True
        before = cell.snapshot()
        with self.assertRaisesRegex(ValueError, "模拟时钟无法安全推进"):
            cell.step(0.25)
        self.assertEqual(cell.snapshot(), before)

    def test_boolean_culture_state_fields_are_rejected_before_state_changes(self) -> None:
        numeric_fields = (
            "viable_cells", "dead_cells", "glucose_mm", "glutamine_mm",
            "lactate_mm", "oxygen_percent", "drug_um", "oxygen_setpoint_percent",
            "ph", "temperature_c", "co2_percent", "osmolality_mosm_kg",
            "energy_index", "last_growth_rate_per_h", "last_death_rate_per_h",
        )
        for field in numeric_fields:
            with self.subTest(field=field):
                cell = CellCulture("a549")
                setattr(cell, field, True)
                before = cell.snapshot()
                with self.assertRaisesRegex(ValueError, f"培养状态 {field}"):
                    cell.step(0.25)
                self.assertEqual(cell.snapshot(), before)

    def test_large_finite_cell_counts_do_not_fake_zero_viability_or_overflow(self) -> None:
        cell = CellCulture("hela", viable_cells=1.7e308)
        cell.dead_cells = 1.7e308
        self.assertAlmostEqual(cell.viability_percent, 50.0)
        with self.assertRaisesRegex(ValueError, "总细胞数超出.*有限数值范围"):
            _ = cell.total_cells

        cell = CellCulture("a549", surface_area_cm2=2e303, viable_cells=1e308)
        cell.parameters.growth_scale = 1000.0
        with self.assertRaisesRegex(ValueError, "细胞数量超出当前软件的数值安全范围"):
            cell.step(1.0)
        self.assertTrue(math.isfinite(cell.viable_cells))
        self.assertEqual(cell.time_h, 0.0)

    def test_constructor_rejects_dimensions_that_overflow_capacity_or_volume_scaling(self) -> None:
        with self.assertRaisesRegex(ValueError, "承载容量超出.*数值安全范围"):
            CellCulture("hela", surface_area_cm2=1e305)
        with self.assertRaisesRegex(ValueError, "培养体积超出.*数值安全范围"):
            CellCulture("hela", culture_volume_ml=1e305)

    def test_mutated_culture_dimensions_are_revalidated_before_calculation(self) -> None:
        for name, invalid in (("surface_area_cm2", True), ("surface_area_cm2", 1e305),
                              ("culture_volume_ml", float("inf"))):
            with self.subTest(name=name, value=invalid):
                cell = CellCulture("hela")
                before = (cell.time_h, cell.viable_cells, cell.glucose_mm)
                setattr(cell, name, invalid)
                with self.assertRaisesRegex(ValueError, f"{name}|数值安全范围"):
                    cell.step(0.25)
                self.assertEqual((cell.time_h, cell.viable_cells, cell.glucose_mm), before)
                with self.assertRaisesRegex(ValueError, f"{name}|数值安全范围"):
                    _ = cell.carrying_capacity

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

    def test_direct_growth_modifiers_reject_boolean_environment_values(self) -> None:
        cell = CellCulture("hela")
        cell.glucose_mm = True
        with self.assertRaisesRegex(ValueError, "培养状态 glucose_mm 不能使用布尔值"):
            cell.growth_modifiers()


if __name__ == "__main__":
    unittest.main()

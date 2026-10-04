"""单细胞环境解耦与小型代表性群体的方向性测试。"""

import copy
import math
import unittest

from cell import CellCulture
from intracellular import MAX_INTERNAL_STEP_H, IntracellularState
from microcolony import MicrocolonyState
from microenvironment import MicroenvironmentState


class MicroenvironmentAndMicrocolonyTests(unittest.TestCase):
    def test_unknown_selected_cell_cannot_silently_show_first_cell(self) -> None:
        colony = MicrocolonyState(cell_count=3)
        for invalid in (0, 4, True, "1"):
            with self.subTest(cell_id=invalid):
                with self.assertRaisesRegex(ValueError, "编号不在当前微群体"):
                    colony.selected_snapshot(invalid)
                with self.assertRaisesRegex(ValueError, "编号不在当前微群体"):
                    colony.selected_history(invalid)

    def test_single_cell_runs_without_cell_culture(self) -> None:
        environment = MicroenvironmentState(local_oxygen_availability=0.35, glucose_mm=2.0, ph=7.1)
        state = IntracellularState()
        state.step(environment, 2.0)
        self.assertEqual(state.time_h, 2.0)
        self.assertGreaterEqual(state.atp_percent, 0.0)
        self.assertLessEqual(state.atp_percent, 100.0)

    def test_non_finite_time_step_is_rejected_and_environment_is_sanitized(self) -> None:
        state = IntracellularState()
        before = state.snapshot()
        with self.assertRaisesRegex(ValueError, "单细胞单步时长"):
            state.step(MicroenvironmentState(), math.nan)
        self.assertEqual(state.snapshot(), before)
        environment = MicroenvironmentState(time_h=math.inf, glucose_mm=math.nan).normalized()
        self.assertTrue(math.isfinite(environment.time_h))
        self.assertTrue(math.isfinite(environment.glucose_mm))

    def test_normalized_copy_cleans_environment_without_mutating_source(self) -> None:
        source = MicroenvironmentState(time_h=math.inf, glucose_mm=math.nan, ph=20.0)
        before = dict(source.__dict__)
        clean = source.normalized_copy()
        self.assertIsNot(clean, source)
        self.assertEqual(source.__dict__, before)
        self.assertEqual(clean.time_h, 0.0)
        self.assertEqual(clean.glucose_mm, 0.0)
        self.assertEqual(clean.ph, 9.0)

    def test_single_cell_and_colony_steps_do_not_mutate_shared_environment(self) -> None:
        environment = MicroenvironmentState(glucose_mm=math.nan, ph=20.0)
        before = dict(environment.__dict__)
        IntracellularState().step(environment, 0.25)
        MicrocolonyState(cell_count=3).step(environment, 0.25)
        self.assertEqual(environment.__dict__, before)

    def test_invalid_single_and_colony_steps_do_not_silently_return(self) -> None:
        environment = MicroenvironmentState()
        state = IntracellularState()
        colony = MicrocolonyState(cell_count=3)
        for invalid in (-1.0, math.nan, math.inf, None, True):
            with self.subTest(dt_h=invalid):
                with self.assertRaisesRegex(ValueError, "单细胞单步时长"):
                    state.step(environment, invalid)
                with self.assertRaisesRegex(ValueError, "微群体单步时长"):
                    colony.step(environment, invalid)
        state.step(environment, 0.0)
        colony.step(environment, 0.0)
        self.assertEqual(state.time_h, 0.0)
        self.assertEqual(colony.time_h, 0.0)

    def test_colony_clock_precision_loss_is_rejected_before_any_cell_changes(self) -> None:
        colony = MicrocolonyState(cell_count=3)
        colony.time_h = 1e20
        for cell in colony.cells:
            cell.state.time_h = colony.time_h
        before = [cell.state.snapshot() for cell in colony.cells]
        with self.assertRaisesRegex(ValueError, "模拟时钟无法安全推进"):
            colony.step(MicroenvironmentState(), 0.25)
        self.assertEqual(colony.time_h, 1e20)
        self.assertEqual([cell.state.snapshot() for cell in colony.cells], before)

    def test_culture_derived_environment_matches_direct_schema(self) -> None:
        culture = CellCulture("a549")
        derived = MicroenvironmentState.from_culture(culture)
        direct = MicroenvironmentState(**{
            "time_h": culture.time_h,
            "local_oxygen_availability": culture.oxygen_percent / 18.6,
            "glucose_mm": culture.glucose_mm,
            "glucose_reference_mm": culture.profile.initial_glucose_mm,
            "lactate_mm": culture.lactate_mm,
            "ph": culture.ph,
            "temperature_c": culture.temperature_c,
            "drug_um": culture.drug_um,
            "local_confluence_percent": culture.confluence_percent,
            "doubling_time_h": culture.profile.doubling_time_h,
            "drug_ic50_um": culture.parameters.drug_ic50_um,
        }).normalized()
        self.assertEqual(set(derived.snapshot()), set(direct.snapshot()))
        self.assertAlmostEqual(derived.local_oxygen_availability, direct.local_oxygen_availability)
        self.assertAlmostEqual(derived.glucose_reference_mm, culture.profile.initial_glucose_mm)

    def test_legacy_culture_input_matches_explicit_microenvironment_path(self) -> None:
        culture = CellCulture("a549")
        legacy_path = IntracellularState()
        explicit_path = IntracellularState()
        legacy_path.step(culture, 2.0)
        explicit_path.step(MicroenvironmentState.from_culture(culture), 2.0)
        self.assertEqual(legacy_path.snapshot(), explicit_path.snapshot())

    def test_lactate_is_recorded_but_not_silently_mapped_to_cell_state(self) -> None:
        baseline = MicroenvironmentState(lactate_mm=0.0)
        high_lactate = MicroenvironmentState(lactate_mm=40.0)
        baseline_state = IntracellularState()
        high_lactate_state = IntracellularState()
        baseline_state.step(baseline, 2.0)
        high_lactate_state.step(high_lactate, 2.0)
        self.assertEqual(baseline_state.snapshot(), high_lactate_state.snapshot())
        self.assertEqual(baseline.snapshot()["lactate_mM"], 0.0)
        self.assertEqual(high_lactate.snapshot()["lactate_mM"], 40.0)

    def test_profile_reference_keeps_baseline_glucose_response_neutral(self) -> None:
        for profile_key in ("hela", "hek293", "a549"):
            culture = CellCulture(profile_key)
            environment = MicroenvironmentState.from_culture(culture)
            self.assertAlmostEqual(environment.glucose_mm, environment.glucose_reference_mm)
            reference = MicroenvironmentState(
                local_oxygen_availability=environment.local_oxygen_availability,
                glucose_mm=5.5, glucose_reference_mm=5.5,
                ph=environment.ph, temperature_c=environment.temperature_c,
                drug_um=environment.drug_um, local_confluence_percent=environment.local_confluence_percent,
                doubling_time_h=environment.doubling_time_h, drug_ic50_um=environment.drug_ic50_um,
            )
            profile_state, reference_state = IntracellularState(), IntracellularState()
            profile_state.step(environment, 1.0)
            reference_state.step(reference, 1.0)
            self.assertAlmostEqual(profile_state.glycolysis_percent, reference_state.glycolysis_percent)

    def test_microcolony_states_stay_finite_and_heterogeneous(self) -> None:
        colony = MicrocolonyState(cell_count=12)
        environment = MicroenvironmentState(drug_um=20.0, local_oxygen_availability=0.3)
        for _ in range(12):
            colony.step(environment, 1.0)
        self.assertTrue(colony.finite())
        atp_values = {round(cell.state.atp_percent, 5) for cell in colony.cells}
        self.assertGreater(len(atp_values), 1)

    def test_long_microcolony_step_is_not_silently_shortened(self) -> None:
        colony = MicrocolonyState(cell_count=3)
        with self.assertRaisesRegex(ValueError, "单步时长不能超过 6 h"):
            colony.step(MicroenvironmentState(), 24.0)
        self.assertEqual(colony.time_h, 0.0)

    def test_subgroup_summary_conserves_representative_cells_and_percentage(self) -> None:
        colony = MicrocolonyState(cell_count=17)
        rows = colony.subgroup_summary()
        self.assertEqual(sum(row["代表性细胞数"] for row in rows), 17)
        self.assertAlmostEqual(sum(row["占代表性细胞比例（%）"] for row in rows), 100.0)
        self.assertEqual(len(rows), 4)

    def test_subgroup_trajectory_uses_recorded_denominator_at_each_time(self) -> None:
        environment = MicroenvironmentState()
        colony = MicrocolonyState(cell_count=5)
        colony.step(environment, 1.0)
        trajectory = colony.subgroup_trajectory()
        by_time = {}
        for row in trajectory:
            by_time.setdefault(row["time_h"], []).append(row)
        self.assertEqual(by_time[0.0][0]["该时点记录细胞数"], 5)
        self.assertEqual(by_time[1.0][0]["该时点记录细胞数"], 5)
        self.assertAlmostEqual(sum(row["占该时点记录比例（%）"] for row in by_time[1.0]), 100.0)

        colony.history = [row for row in colony.history if not (row["time_h"] == 1.0 and row["cell_id"] == 5)]
        truncated = colony.subgroup_trajectory()
        time_one = [row for row in truncated if row["time_h"] == 1.0]
        self.assertEqual(time_one[0]["该时点记录细胞数"], 4)
        self.assertAlmostEqual(sum(row["占该时点记录比例（%）"] for row in time_one), 100.0)

    def test_microcolony_finite_guard_covers_all_state_fields(self) -> None:
        colony = MicrocolonyState(cell_count=3)
        colony.cells[0].state.cytosolic_calcium_nm = math.nan
        self.assertFalse(colony.finite())
        with self.assertRaisesRegex(ValueError, "越界或非有限"):
            colony.step(MicroenvironmentState(), 1.0)
        with self.assertRaisesRegex(ValueError, "3–50"):
            MicrocolonyState(cell_count=2)

    def test_minimum_and_maximum_colonies_stay_finite_under_extreme_conditions(self) -> None:
        environment = MicroenvironmentState(
            local_oxygen_availability=0.0,
            glucose_mm=0.0,
            ph=5.5,
            temperature_c=50.0,
            drug_um=1e6,
        )
        for count in (3, 50):
            with self.subTest(cell_count=count):
                colony = MicrocolonyState(cell_count=count, communication_enabled=True)
                colony.step(environment, 6.0)
                self.assertTrue(colony.finite())
                self.assertEqual(len(colony.cells), count)
                expected_steps = round(6.0 / MAX_INTERNAL_STEP_H)
                self.assertEqual(len(colony.history), (expected_steps + 1) * count)
                for cell in colony.cells:
                    numeric_state = (
                        value for value in cell.state.snapshot().values()
                        if isinstance(value, (int, float))
                    )
                    self.assertTrue(all(math.isfinite(value) for value in numeric_state))

    def test_six_hour_colony_advance_matches_six_hourly_requests(self) -> None:
        environment = MicroenvironmentState(local_oxygen_availability=0.25, glucose_mm=2.0, drug_um=12.0)
        one_step = MicrocolonyState(cell_count=5, communication_enabled=True)
        repeated_steps = MicrocolonyState(cell_count=5, communication_enabled=True)

        one_step.step(environment, 6.0)
        for _ in range(6):
            repeated_steps.step(environment, 1.0)

        self.assertEqual(one_step.summary(), repeated_steps.summary())
        self.assertEqual(one_step.history, repeated_steps.history)

    def test_reset_can_record_the_active_environment_without_fabricating_initial_inputs(self) -> None:
        colony = MicrocolonyState(cell_count=3)
        self.assertNotIn("local_oxygen_availability", colony.history[0])
        environment = MicroenvironmentState(local_oxygen_availability=0.3, glucose_mm=2.0)
        colony.reset(3, environment)
        self.assertEqual(colony.history[0]["local_oxygen_availability"], 0.3)
        self.assertEqual(colony.history[0]["glucose_mM"], 2.0)
        self.assertEqual(colony.history[0]["environment_time_h"], 0.0)

    def test_communication_off_has_no_neighbor_feedback(self) -> None:
        environment = MicroenvironmentState(drug_um=20.0)
        single = MicrocolonyState(cell_count=3, communication_enabled=False)
        many = MicrocolonyState(cell_count=20, communication_enabled=False)
        single.step(environment, 1.0)
        many.step(environment, 1.0)
        self.assertEqual(single.cells[0].local_signal_index, 0.0)
        self.assertEqual(many.cells[0].local_signal_index, 0.0)
        self.assertAlmostEqual(single.cells[0].state.ros_percent, many.cells[0].state.ros_percent)

    def test_communication_is_opt_in(self) -> None:
        environment = MicroenvironmentState(drug_um=80.0, local_oxygen_availability=0.2)
        off = MicrocolonyState(cell_count=12, communication_enabled=False)
        on = MicrocolonyState(cell_count=12, communication_enabled=True)
        for _ in range(10):
            off.step(environment, 1.0)
            on.step(environment, 1.0)
        self.assertEqual(max(cell.local_signal_index for cell in off.cells), 0.0)
        self.assertGreater(max(cell.local_signal_index for cell in on.cells), 0.0)
        self.assertTrue(on.finite())

    def test_history_records_communication_setting_used_at_each_step(self) -> None:
        environment = MicroenvironmentState()
        colony = MicrocolonyState(cell_count=3, communication_enabled=False)
        colony.step(environment, 1.0)
        colony.communication_enabled = True
        colony.step(environment, 1.0)
        by_time = {}
        for row in colony.history:
            by_time.setdefault(row["time_h"], set()).add(row["communication_enabled"])
        self.assertEqual(by_time[0.0], {False})
        self.assertEqual(by_time[1.0], {False})
        self.assertEqual(by_time[2.0], {True})


if __name__ == "__main__":
    unittest.main()

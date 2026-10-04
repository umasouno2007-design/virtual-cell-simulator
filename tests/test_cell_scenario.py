"""单细胞和微型细胞群场景的导入导出测试。"""

import copy
import unittest

import pandas as pd

from cell_scenario import (
    add_traceability_fields,
    environment_change_event,
    export_microcolony_scenario,
    export_single_cell_scenario,
    import_microcolony_scenario,
    import_single_cell_scenario,
    single_cell_history_row,
    truncate_microcolony_scenario_history,
)
from intracellular import IntracellularState
from microcolony import MicrocolonyState
from microenvironment import MicroenvironmentState


class CellScenarioTests(unittest.TestCase):
    def test_single_and_colony_traceability_metadata_has_valid_types(self):
        payloads = (
            (export_single_cell_scenario(MicroenvironmentState(), IntracellularState(), [], []), import_single_cell_scenario),
            (export_microcolony_scenario(MicrocolonyState(cell_count=3), MicroenvironmentState()), import_microcolony_scenario),
        )
        for original, importer in payloads:
            for field, bad in (("created_at", []), ("evidence_level", {"rule": "verified"}),
                               ("evidence_level", {"rule": []}),
                               ("limitations", None)):
                with self.subTest(schema=original["schema"], field=field):
                    payload = copy.deepcopy(original)
                    payload[field] = bad
                    with self.assertRaisesRegex(ValueError, field):
                        importer(payload)

    def test_environment_change_event_contains_only_changed_fields(self):
        environment = MicroenvironmentState(glucose_mm=2.0)
        original = environment.snapshot()
        environment.glucose_mm = 3.0
        event = environment_change_event(original, environment, 4.0)
        self.assertEqual(event["event_type"], "environment_update")
        self.assertEqual(event["changes"], {"glucose_mM": {"from": 2.0, "to": 3.0}})
        self.assertIsNone(environment_change_event(environment.snapshot(), environment, 4.0))

    def test_single_cell_trace_row_binds_state_to_environment_without_mutation(self):
        environment = MicroenvironmentState(local_oxygen_availability=0.35, glucose_mm=2.1)
        state = IntracellularState()
        environment.time_h = 12.0
        state.time_h = 12.0
        row = single_cell_history_row(state, environment)
        self.assertEqual(row["time_h"], 12.0)
        self.assertEqual(row["local_oxygen_availability"], 0.35)
        self.assertEqual(row["glucose_mM"], 2.1)
        self.assertEqual(row["doubling_time_h"], environment.doubling_time_h)
        self.assertEqual(row["drug_ic50_uM"], environment.drug_ic50_um)
        self.assertTrue(row["environment_recorded"])
        self.assertTrue(row["environment_inputs_complete"])
        self.assertNotIn("local_oxygen_availability", state.snapshot())

    def test_traceability_export_marks_legacy_environment_as_not_recorded(self):
        old_row = IntracellularState().snapshot()
        new_row = single_cell_history_row(IntracellularState(), MicroenvironmentState())
        exported = add_traceability_fields([old_row, new_row], evidence_level="B/C")
        self.assertFalse(exported[0]["environment_recorded"])
        self.assertFalse(exported[0]["environment_inputs_complete"])
        self.assertTrue(exported[1]["environment_recorded"])
        self.assertTrue(exported[1]["environment_inputs_complete"])
        self.assertTrue(all(item["model_version"] for item in exported))
        self.assertTrue(all(item["limitations"] for item in exported))
        self.assertNotIn("model_version", old_row)

    def test_truncated_history_is_not_mislabeled_as_initial_state(self):
        state = IntracellularState(time_h=8.0)
        row = single_cell_history_row(state, MicroenvironmentState(time_h=8.0))
        payload = export_single_cell_scenario(
            MicroenvironmentState(time_h=8.0), state, [row], [],
        )
        self.assertFalse(payload["history_starts_at_zero"])
        self.assertTrue(payload["history_window_truncated"])
        self.assertEqual(payload["history_start_time_h"], 8.0)
        self.assertIsNone(payload["initial_state"])
        self.assertEqual(payload["first_recorded_state"], row)

    def test_history_window_metadata_must_match_stored_rows(self):
        state = IntracellularState()
        payload = export_single_cell_scenario(
            MicroenvironmentState(), state, [state.snapshot()], [],
        )
        payload["history_starts_at_zero"] = False
        with self.assertRaisesRegex(ValueError, "history_starts_at_zero 与历史记录不一致"):
            import_single_cell_scenario(payload)

    def test_environment_snapshot_rows_cannot_claim_missing_or_invalid_inputs(self):
        state = IntracellularState()
        environment = MicroenvironmentState()
        row = single_cell_history_row(state, environment)
        payload = export_single_cell_scenario(environment, state, [row], [])
        payload["history"][0]["glucose_mM"] = -1.0
        with self.assertRaisesRegex(ValueError, "glucose_mM 超出允许范围"):
            import_single_cell_scenario(payload)
        payload = export_single_cell_scenario(environment, state, [row], [])
        del payload["history"][0]["local_oxygen_availability"]
        with self.assertRaisesRegex(ValueError, "环境快照字段不完整"):
            import_single_cell_scenario(payload)
        legacy = state.snapshot()
        legacy["environment_recorded"] = True
        payload = export_single_cell_scenario(environment, state, [legacy], [])
        with self.assertRaisesRegex(ValueError, "标记与实际字段不一致"):
            import_single_cell_scenario(payload)

    def test_legacy_environment_snapshot_remains_importable_but_is_incomplete(self):
        state = IntracellularState()
        environment = MicroenvironmentState()
        row = single_cell_history_row(state, environment)
        del row["doubling_time_h"]
        del row["drug_ic50_uM"]
        del row["environment_inputs_complete"]
        payload = export_single_cell_scenario(environment, state, [row], [])
        _, _, restored, _ = import_single_cell_scenario(payload)
        self.assertTrue(restored[0]["environment_recorded"])
        exported = add_traceability_fields(restored, evidence_level="B/C")
        self.assertFalse(exported[0]["environment_inputs_complete"])

    def test_partial_new_environment_input_is_rejected(self):
        state = IntracellularState()
        environment = MicroenvironmentState()
        row = single_cell_history_row(state, environment)
        del row["drug_ic50_uM"]
        payload = export_single_cell_scenario(environment, state, [row], [])
        with self.assertRaisesRegex(ValueError, "环境模型输入字段不完整"):
            import_single_cell_scenario(payload)

    def test_environment_snapshot_time_must_match_state_time(self):
        state = IntracellularState(time_h=2.0)
        environment = MicroenvironmentState(time_h=2.0)
        row = single_cell_history_row(state, environment)
        payload = export_single_cell_scenario(environment, state, [row], [])
        payload["history"][0]["environment_time_h"] = 1.0
        with self.assertRaisesRegex(ValueError, "环境快照时间与状态时间不一致"):
            import_single_cell_scenario(payload)

        payload = export_single_cell_scenario(environment, state, [row], [])
        payload["environment"]["time_h"] = 1.0
        with self.assertRaisesRegex(ValueError, "当前微环境时间与单细胞状态时间不一致"):
            import_single_cell_scenario(payload)

    def test_single_cell_history_endpoint_must_match_continuation_state(self):
        state = IntracellularState()
        environment = MicroenvironmentState()
        payload = export_single_cell_scenario(
            environment, state, [single_cell_history_row(state, environment)], [],
        )
        payload["history"][-1]["ATP_percent"] -= 1.0
        payload["initial_state"] = payload["history"][0]
        payload["first_recorded_state"] = payload["history"][0]
        with self.assertRaisesRegex(ValueError, "历史末点与当前状态不一致"):
            import_single_cell_scenario(payload)

    def test_single_cell_round_trip_preserves_current_state_history_and_events(self):
        environment = MicroenvironmentState(glucose_mm=3.2, local_oxygen_availability=0.4)
        state = IntracellularState()
        history = [single_cell_history_row(state, environment)]
        state.step(environment, 1.0)
        environment.time_h = state.time_h
        history.append(single_cell_history_row(state, environment))
        events = [{"time_h": 1.0, "event": "推进 1 h"}, {
            "time_h": 1.0, "event": "教学性氧化压力脉冲",
            "event_type": "oxidative_stress", "input_index": 20.0,
            "environment": environment.snapshot(),
        }]
        payload = export_single_cell_scenario(environment, state, history, events)
        restored_environment, restored_state, restored_history, restored_events = import_single_cell_scenario(payload)
        self.assertEqual(restored_environment.time_h, state.time_h)
        self.assertEqual(restored_environment.local_oxygen_availability, environment.local_oxygen_availability)
        self.assertEqual(restored_environment.glucose_mm, environment.glucose_mm)
        self.assertEqual(restored_state, state)
        self.assertEqual(restored_history, history)
        self.assertEqual(restored_events, events)

        # A scenario is a resumable configuration, not merely a readable snapshot.
        state.step(environment, 1.0)
        restored_state.step(restored_environment, 1.0)
        self.assertEqual(restored_state.snapshot(), state.snapshot())

    def test_exported_scenario_is_a_snapshot_not_a_reference_to_live_history(self):
        environment = MicroenvironmentState()
        state = IntracellularState()
        history = [single_cell_history_row(state, environment)]
        events = [{"time_h": 0.0, "event": "original"}]
        payload = export_single_cell_scenario(environment, state, history, events)
        payload["history"][0]["ATP_percent"] = 0.0
        payload["events"][0]["event"] = "edited copy"
        self.assertEqual(history[0]["ATP_percent"], state.atp_percent)
        self.assertEqual(events[0]["event"], "original")

        colony = MicrocolonyState(cell_count=3)
        colony_payload = export_microcolony_scenario(colony, environment)
        colony_payload["history"][0]["ATP_percent"] = 0.0
        self.assertNotEqual(colony.history[0]["ATP_percent"], 0.0)

    def test_microcolony_round_trip_preserves_heterogeneity_and_trace(self):
        environment = MicroenvironmentState(local_oxygen_availability=0.5)
        colony = MicrocolonyState(cell_count=5, communication_enabled=True)
        colony.step(environment, 1.0)
        payload = export_microcolony_scenario(colony, environment)
        restored, restored_environment = import_microcolony_scenario(payload)
        self.assertEqual(restored.summary(), colony.summary())
        self.assertEqual(restored.history, colony.history)
        self.assertEqual(restored_environment.time_h, colony.time_h)
        self.assertEqual(restored_environment.local_oxygen_availability, environment.local_oxygen_availability)
        self.assertEqual(restored.communication_enabled, colony.communication_enabled)

        # 同一模型版本/输入下，从恢复点继续运行应得到相同的微群体轨迹。
        colony.step(environment, 1.0)
        restored.step(restored_environment, 1.0)
        self.assertEqual(restored.summary(), colony.summary())
        self.assertEqual(restored.history, colony.history)

    def test_microcolony_environment_snapshot_time_tracks_its_own_clock(self):
        environment = MicroenvironmentState(time_h=15.0)
        colony = MicrocolonyState(cell_count=3)
        colony.step(environment, 1.0)
        self.assertEqual(environment.time_h, 15.0)
        row = colony.history[-1]
        self.assertEqual(row["environment_time_h"], row["time_h"])
        payload = export_microcolony_scenario(colony, environment)
        payload["environment"]["time_h"] = 15.0
        with self.assertRaisesRegex(ValueError, "当前微环境时间与微群体模拟时间不一致"):
            import_microcolony_scenario(payload)

    def test_microcolony_history_rejects_non_boolean_communication_marker(self):
        environment = MicroenvironmentState()
        colony = MicrocolonyState(cell_count=3)
        colony.step(environment, 1.0)
        payload = export_microcolony_scenario(colony, environment)
        payload["history"][-1]["communication_enabled"] = "on"
        with self.assertRaisesRegex(ValueError, "通信开关必须是布尔值"):
            import_microcolony_scenario(payload)

    def test_microcolony_each_history_endpoint_matches_current_cell(self):
        colony = MicrocolonyState(cell_count=3, communication_enabled=True)
        environment = MicroenvironmentState()
        colony.step(environment, 1.0)
        payload = export_microcolony_scenario(colony, environment)
        payload["history"][-1]["ROS_percent"] += 1.0
        with self.assertRaisesRegex(ValueError, "历史末点与当前状态不一致"):
            import_microcolony_scenario(payload)

        payload = export_microcolony_scenario(colony, environment)
        payload["history"][-1]["local_signal_index"] = 100.0
        with self.assertRaisesRegex(ValueError, "当前局部信号不一致"):
            import_microcolony_scenario(payload)

    def test_runtime_history_truncation_recalculates_window_metadata_and_remains_importable(self):
        environment = MicroenvironmentState()
        colony = MicrocolonyState(cell_count=3)
        for _ in range(2):
            colony.step(environment, 1.0)
        payload = export_microcolony_scenario(colony, environment)
        compact = truncate_microcolony_scenario_history(payload, 5)
        self.assertTrue(compact["history_truncated_for_runtime"])
        self.assertFalse(compact["history_starts_at_zero"])
        self.assertTrue(compact["history_window_truncated"])
        self.assertEqual(compact["history_start_time_h"], 2.0)
        self.assertEqual(len(compact["history"]), 3)
        restored, _ = import_microcolony_scenario(compact)
        self.assertEqual(restored.history, compact["history"])
        # 每小时按四个 0.25 h 内部子步记录，2 h 加初始快照共 9 个时点。
        self.assertEqual(len(payload["history"]), 9 * colony.cell_count)

    def test_runtime_history_requires_a_complete_timepoint(self):
        payload = export_microcolony_scenario(MicrocolonyState(cell_count=3), MicroenvironmentState())
        with self.assertRaisesRegex(ValueError, "完整微群体时点"):
            truncate_microcolony_scenario_history(payload, 2)

    def test_missing_fields_and_invalid_ranges_are_rejected(self):
        env = MicroenvironmentState()
        payload = export_microcolony_scenario(MicrocolonyState(cell_count=3), env)
        invalid = copy.deepcopy(payload)
        invalid["cell_count"] = 2
        with self.assertRaisesRegex(ValueError, "3–50"):
            import_microcolony_scenario(invalid)
        invalid = copy.deepcopy(payload)
        del invalid["environment"]
        with self.assertRaises(ValueError):
            import_microcolony_scenario(invalid)
        invalid = copy.deepcopy(payload)
        invalid["cell_count"] = 3.5
        with self.assertRaisesRegex(ValueError, "必须是整数"):
            import_microcolony_scenario(invalid)

    def test_non_finite_state_is_rejected(self):
        env = MicroenvironmentState()
        payload = export_single_cell_scenario(env, IntracellularState(), [], [])
        payload["current_state"]["atp_percent"] = float("nan")
        with self.assertRaisesRegex(ValueError, "有限数值"):
            import_single_cell_scenario(payload)

    def test_cycle_label_must_match_model_progress_in_current_and_history_state(self):
        payload = export_single_cell_scenario(MicroenvironmentState(), IntracellularState(), [], [])
        payload["current_state"]["cycle_phase"] = "M"
        with self.assertRaisesRegex(ValueError, "阶段与进度不一致"):
            import_single_cell_scenario(payload)
        state = IntracellularState()
        payload = export_single_cell_scenario(
            MicroenvironmentState(), state, [state.snapshot()], [],
        )
        payload["history"][0]["cycle_phase"] = "S"
        with self.assertRaisesRegex(ValueError, "阶段与进度不一致"):
            import_single_cell_scenario(payload)

    def test_boolean_is_not_accepted_as_a_numeric_model_input(self):
        payload = export_single_cell_scenario(MicroenvironmentState(), IntracellularState(), [], [])
        payload["environment"]["glucose_mm"] = True
        with self.assertRaisesRegex(ValueError, "不能是布尔值"):
            import_single_cell_scenario(payload)

    def test_scenario_numeric_parser_rejects_pandas_boolean_and_overflow(self):
        payload = export_single_cell_scenario(MicroenvironmentState(), IntracellularState(), [], [])
        payload["environment"]["glucose_mm"] = pd.Series([True]).iloc[0]
        with self.assertRaisesRegex(ValueError, "glucose_mm.*不能是布尔值"):
            import_single_cell_scenario(payload)

        payload = export_single_cell_scenario(MicroenvironmentState(), IntracellularState(), [], [])
        payload["environment"]["glucose_mm"] = 10**10000
        with self.assertRaisesRegex(ValueError, "glucose_mm.*有限数值"):
            import_single_cell_scenario(payload)
        payload = export_single_cell_scenario(MicroenvironmentState(), IntracellularState(), [], [])
        payload["current_state"]["atp_percent"] = False
        with self.assertRaisesRegex(ValueError, "不能是布尔值"):
            import_single_cell_scenario(payload)

    def test_out_of_range_environment_is_rejected_without_silent_clipping(self):
        payload = export_single_cell_scenario(MicroenvironmentState(), IntracellularState(), [], [])
        payload["environment"]["local_oxygen_availability"] = 1.5
        with self.assertRaisesRegex(ValueError, "超出允许范围"):
            import_single_cell_scenario(payload)

    def test_malformed_or_inconsistent_history_is_rejected(self):
        state = IntracellularState()
        payload = export_single_cell_scenario(MicroenvironmentState(), state, [state.snapshot()], [])
        payload["history"][0]["ATP_percent"] = float("inf")
        with self.assertRaisesRegex(ValueError, "有限数值"):
            import_single_cell_scenario(payload)
        payload = export_single_cell_scenario(MicroenvironmentState(), state, [state.snapshot()], [])
        payload["current_state"]["time_h"] = 2.0
        payload["environment"]["time_h"] = 2.0
        with self.assertRaisesRegex(ValueError, "末时点"):
            import_single_cell_scenario(payload)

    def test_duplicate_microcolony_history_row_is_rejected(self):
        environment = MicroenvironmentState()
        colony = MicrocolonyState(cell_count=3)
        payload = export_microcolony_scenario(colony, environment)
        payload["history"].append(copy.deepcopy(payload["history"][0]))
        with self.assertRaisesRegex(ValueError, "不得重复"):
            import_microcolony_scenario(payload)

    def test_microcolony_history_rejects_incomplete_timepoints_and_invalid_ids(self):
        environment = MicroenvironmentState()
        colony = MicrocolonyState(cell_count=3)
        colony.step(environment, 1.0)
        payload = export_microcolony_scenario(colony, environment)
        payload["history"].pop(0)
        with self.assertRaisesRegex(ValueError, "每个时点必须包含全部"):
            import_microcolony_scenario(payload)

        payload = export_microcolony_scenario(colony, environment)
        payload["history"][0]["cell_id"] = True
        with self.assertRaisesRegex(ValueError, "cell_id 必须是整数"):
            import_microcolony_scenario(payload)

        payload = export_microcolony_scenario(colony, environment)
        payload["history"][0]["cycle_phase"] = "unknown"
        with self.assertRaisesRegex(ValueError, "细胞周期阶段无效"):
            import_microcolony_scenario(payload)
        payload = export_microcolony_scenario(colony, environment)
        payload["history"][0]["cycle_phase"] = "M"
        with self.assertRaisesRegex(ValueError, "阶段与进度不一致"):
            import_microcolony_scenario(payload)

    def test_microcolony_environment_snapshot_is_range_checked(self):
        environment = MicroenvironmentState()
        colony = MicrocolonyState(cell_count=3)
        colony.step(environment, 1.0)
        payload = export_microcolony_scenario(colony, environment)
        next(row for row in payload["history"] if row["time_h"] == 1.0)["pH"] = 10.0
        with self.assertRaisesRegex(ValueError, "环境字段 pH 超出允许范围"):
            import_microcolony_scenario(payload)

    def test_truncated_microcolony_history_round_trips_with_window_marker(self):
        environment = MicroenvironmentState()
        colony = MicrocolonyState(cell_count=3)
        colony.step(environment, 1.0)
        colony.history = colony.history[3:]
        payload = export_microcolony_scenario(colony, environment)
        self.assertFalse(payload["history_starts_at_zero"])
        self.assertTrue(payload["history_window_truncated"])
        restored, _ = import_microcolony_scenario(payload)
        self.assertEqual(restored.history, colony.history)

    def test_different_model_version_cannot_resume_old_state(self):
        payload = export_single_cell_scenario(MicroenvironmentState(), IntracellularState(), [], [])
        payload["model_version"] = "0.9.0"
        with self.assertRaisesRegex(ValueError, "模型版本"):
            import_single_cell_scenario(payload)

    def test_event_cannot_extend_beyond_current_timeline(self):
        payload = export_single_cell_scenario(
            MicroenvironmentState(), IntracellularState(), [IntracellularState().snapshot()],
            [{"time_h": 1.0, "event": "future"}],
        )
        with self.assertRaisesRegex(ValueError, "模拟时段"):
            import_single_cell_scenario(payload)

    def test_event_order_must_be_chronological(self):
        state = IntracellularState(time_h=4.0)
        payload = export_single_cell_scenario(
            MicroenvironmentState(time_h=4.0), state, [state.snapshot()], [
                {"time_h": 3.0, "event": "later in list"},
                {"time_h": 2.0, "event": "earlier in time"},
            ],
        )
        with self.assertRaisesRegex(ValueError, "事件必须按记录顺序"):
            import_single_cell_scenario(payload)

    def test_invalid_teaching_stress_event_is_rejected(self):
        payload = export_single_cell_scenario(
            MicroenvironmentState(), IntracellularState(), [IntracellularState().snapshot()],
            [{"time_h": 0.0, "event": "stress", "event_type": "oxidative_stress", "input_index": 150.0}],
        )
        with self.assertRaisesRegex(ValueError, "压力输入指数"):
            import_single_cell_scenario(payload)

    def test_environment_change_event_range_and_field_are_validated(self):
        state = IntracellularState()
        payload = export_single_cell_scenario(
            MicroenvironmentState(), state, [state.snapshot()], [{
                "time_h": 0.0, "event": "input changed", "event_type": "environment_update",
                "changes": {"glucose_mM": {"from": 5.5, "to": 3.0}},
            }],
        )
        self.assertEqual(import_single_cell_scenario(payload)[3][0]["changes"]["glucose_mM"]["to"], 3.0)
        payload["events"][0]["changes"] = {"secret_field": {"from": 1.0, "to": 2.0}}
        with self.assertRaisesRegex(ValueError, "未知的微环境变更字段"):
            import_single_cell_scenario(payload)
        payload["events"][0]["changes"] = {"glucose_mM": {"from": 5.5, "to": 150.0}}
        with self.assertRaisesRegex(ValueError, "超出允许范围"):
            import_single_cell_scenario(payload)

    def test_intervention_environment_snapshot_is_validated(self):
        state = IntracellularState()
        environment = MicroenvironmentState()
        payload = export_single_cell_scenario(
            environment, state, [state.snapshot()], [{
                "time_h": 0.0, "event": "stress", "event_type": "oxidative_stress",
                "input_index": 20.0, "environment": environment.snapshot(),
            }],
        )
        payload["events"][0]["environment"]["pH"] = 99.0
        with self.assertRaisesRegex(ValueError, "环境字段 pH 超出允许范围"):
            import_single_cell_scenario(payload)

    def test_legacy_intervention_snapshot_without_new_inputs_is_importable(self):
        state = IntracellularState()
        environment = MicroenvironmentState()
        snapshot = environment.snapshot()
        del snapshot["doubling_time_h"]
        del snapshot["drug_ic50_uM"]
        payload = export_single_cell_scenario(
            environment, state, [state.snapshot()], [{
                "time_h": 0.0, "event": "stress", "event_type": "oxidative_stress",
                "input_index": 20.0, "environment": snapshot,
            }],
        )
        _, _, _, events = import_single_cell_scenario(payload)
        self.assertEqual(events[0]["environment"], snapshot)


if __name__ == "__main__":
    unittest.main()

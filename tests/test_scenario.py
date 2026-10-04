import unittest

from scenario import export_scenario, import_scenario
from cell import CellCulture
from json_payload import MAX_JSON_PAYLOAD_BYTES, decode_json_object
from experiment_data import measurement_fingerprint
from version import MODEL_VERSION


class ScenarioTests(unittest.TestCase):
    def test_json_decoder_bounds_payload_size_and_nested_depth(self):
        oversized = b" " * (MAX_JSON_PAYLOAD_BYTES + 1)
        for payload in (oversized, oversized.decode("ascii")):
            with self.subTest(payload_type=type(payload).__name__):
                with self.assertRaisesRegex(ValueError, "5 MiB"):
                    decode_json_object(payload)

        deeply_nested = "[" * 20_000 + "{}" + "]" * 20_000
        with self.assertRaisesRegex(ValueError, "嵌套层级过深"):
            decode_json_object(deeply_nested)

    def test_optional_data_fingerprint_round_trips_without_raw_csv(self):
        fingerprint = measurement_fingerprint(b"time_h,viable_cells\n0,100\n24,200\n")
        payload = export_scenario(CellCulture("a549"), data_file_fingerprint=fingerprint)
        self.assertEqual(payload["data_file_fingerprint"], fingerprint)
        self.assertNotIn("raw_csv", payload)
        _, restored = import_scenario(payload)
        self.assertEqual(restored["data_file_fingerprint"], fingerprint)

    def test_invalid_data_fingerprint_is_rejected_on_export_and_import(self):
        for invalid in ("not-a-hash", "A" * 64, True):
            with self.subTest(fingerprint=invalid):
                with self.assertRaisesRegex(ValueError, "数据文件指纹"):
                    export_scenario(CellCulture("a549"), data_file_fingerprint=invalid)
                payload = export_scenario(CellCulture("a549"))
                payload["data_file_fingerprint"] = invalid
                with self.assertRaisesRegex(ValueError, "数据文件指纹"):
                    import_scenario(payload)

    def test_export_rejects_invalid_or_non_reproducible_run_window(self):
        cell = CellCulture("a549")
        for duration, step in ((0, 1), (169, 1), (float("nan"), 1), (True, 1), (72, 0), (72, 6.1), (72, float("inf")), (72, True), (10**10000, 1)):
            with self.subTest(duration_kind=type(duration).__name__, step=step if type(step) is not int or step < 100 else "large"):
                with self.assertRaisesRegex(ValueError, "场景(总时长|步长)"):
                    export_scenario(cell, duration_h=duration, dt_h=step)

        pandas_boolean = __import__("pandas").Series([True]).iloc[0]
        with self.assertRaisesRegex(ValueError, "场景总时长和步长必须是数值"):
            export_scenario(cell, duration_h=pandas_boolean)

    def test_export_normalizes_valid_run_window_to_numeric_values(self):
        payload = export_scenario(CellCulture("a549"), duration_h="48", dt_h="0.5")
        self.assertEqual(payload["run"], {"duration_h": 48.0, "dt_h": 0.5})
        import_scenario(payload)

    def test_export_never_silently_discards_malformed_events_or_invalid_state(self):
        with self.assertRaisesRegex(ValueError, "events 必须是计划操作列表"):
            export_scenario(CellCulture("a549"), events=())

        cell = CellCulture("a549")
        cell.oxygen_percent = 30.0
        with self.assertRaisesRegex(ValueError, "环境字段 oxygen_percent 超出"):
            export_scenario(cell)

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

    def test_evolved_culture_resumes_with_full_state(self):
        original = CellCulture("a549")
        original.step(4.0)
        original.add_drug(2.0)
        payload = export_scenario(original)
        restored, _ = import_scenario(payload)
        for field in ("time_h", "viable_cells", "dead_cells", "energy_index", "drug_um"):
            self.assertAlmostEqual(getattr(original, field), getattr(restored, field))
        original.step(2.0)
        restored.step(2.0)
        for field in ("time_h", "viable_cells", "dead_cells", "glucose_mm", "lactate_mm"):
            self.assertAlmostEqual(getattr(original, field), getattr(restored, field), places=7)

    def test_legacy_scene_without_resume_state_starts_at_zero(self):
        payload = export_scenario(CellCulture("a549"))
        payload.pop("resume_state")
        restored, _ = import_scenario(payload)
        self.assertEqual(restored.time_h, 0.0)
        self.assertEqual(restored.dead_cells, 0.0)

    def test_invalid_resume_state_is_rejected(self):
        payload = export_scenario(CellCulture("a549"))
        for name, value in (("time_h", -1), ("dead_cells", float("inf")),
                            ("energy_index", 101), ("last_growth_rate_per_h", True)):
            with self.subTest(name=name):
                payload["resume_state"][name] = value
                with self.assertRaisesRegex(ValueError, "续跑状态"):
                    import_scenario(payload)
                payload = export_scenario(CellCulture("a549"))

    def test_partial_or_unknown_resume_state_does_not_silently_default(self):
        payload = export_scenario(CellCulture("a549"))
        payload["resume_state"].pop("dead_cells")
        with self.assertRaisesRegex(ValueError, "续跑状态字段不完整"):
            import_scenario(payload)
        payload = export_scenario(CellCulture("a549"))
        payload["resume_state"]["dead_cell"] = 0.0
        with self.assertRaisesRegex(ValueError, "续跑状态字段不完整或未知"):
            import_scenario(payload)

    def test_traceability_metadata_must_be_readable_text(self):
        for field, value in (("created_at", []), ("evidence_level", ""),
                             ("calibration_status", False), ("limitations", {})):
            with self.subTest(field=field):
                payload = export_scenario(CellCulture("a549"))
                payload[field] = value
                with self.assertRaisesRegex(ValueError, f"场景元数据 {field}"):
                    import_scenario(payload)

    def test_missing_field_is_explained(self):
        with self.assertRaisesRegex(ValueError, "缺少字段"):
            import_scenario({"schema": "e-cell-scenario/v1"})

    def test_illegal_range_is_rejected(self):
        payload = export_scenario(CellCulture("a549"))
        payload["run"]["dt_h"] = -1
        with self.assertRaisesRegex(ValueError, "总时长或步长"):
            import_scenario(payload)

    def test_out_of_ui_environment_bounds_is_rejected(self):
        payload = export_scenario(CellCulture("a549"))
        payload["environment"]["pH"] = 9.0
        with self.assertRaisesRegex(ValueError, "超出当前模型界面范围"):
            import_scenario(payload)

    def test_incomplete_or_unknown_model_parameters_are_rejected(self):
        missing = export_scenario(CellCulture("a549"))
        missing["parameters"].pop("growth_scale")
        with self.assertRaisesRegex(ValueError, "模型参数不完整"):
            import_scenario(missing)

        unknown = export_scenario(CellCulture("a549"))
        unknown["parameters"]["unrecognized_parameter"] = 1.0
        with self.assertRaisesRegex(ValueError, "未知参数"):
            import_scenario(unknown)

    def test_invalid_initial_cell_count_is_not_silently_replaced(self):
        payload = export_scenario(CellCulture("a549"))
        payload["cell"]["initial_viable_cells"] = float("nan")
        with self.assertRaisesRegex(ValueError, "有限非负数"):
            import_scenario(payload)

    def test_invalid_scheduled_event_is_rejected_before_ui_execution(self):
        payload = export_scenario(CellCulture("a549"))
        payload["events"] = [{"at_time_h": 12, "action": "unknown", "value": 1}]
        with self.assertRaisesRegex(ValueError, "类型不受支持"):
            import_scenario(payload)

        payload["events"] = [{"at_time_h": float("inf"), "action": "补充葡萄糖", "value": 1}]
        with self.assertRaisesRegex(ValueError, "有限非负小时数"):
            import_scenario(payload)

    def test_valid_scheduled_event_round_trips(self):
        event = {"at_time_h": 12.0, "action": "补充葡萄糖", "value": 1.0, "status": "pending"}
        payload = export_scenario(CellCulture("a549"), events=[event])
        _, imported = import_scenario(payload)
        self.assertEqual(imported["events"], [event])

    def test_pending_event_cannot_claim_an_execution_timestamp(self):
        payload = export_scenario(CellCulture("a549"))
        payload["events"] = [{
            "at_time_h": 12.0, "action": "补充葡萄糖", "value": 1.0,
            "status": "pending", "executed_at_h": 12.0,
        }]
        with self.assertRaisesRegex(ValueError, "待执行操作却含实际处理时间"):
            import_scenario(payload)
        skipped = export_scenario(CellCulture("a549"), events=[{
            "at_time_h": 0.0, "action": "补充葡萄糖", "value": 1.0,
            "status": "skipped", "executed_at_h": 0.0,
        }])
        self.assertEqual(import_scenario(skipped)[1]["events"][0]["status"], "skipped")

    def test_exported_events_do_not_alias_session_actions(self):
        event = {"at_time_h": 12.0, "action": "补充葡萄糖", "value": 1.0, "status": "pending"}
        payload = export_scenario(CellCulture("a549"), events=[event])
        payload["events"][0]["value"] = 4.0
        self.assertEqual(event["value"], 1.0)

    def test_event_timing_must_match_resumed_clock(self):
        cell = CellCulture("a549")
        cell.step(6.0)
        payload = export_scenario(cell, events=[{
            "at_time_h": 5.0, "action": "补充葡萄糖", "value": 1.0,
            "status": "executed", "executed_at_h": 5.0,
        }])
        payload["events"][0]["status"] = "pending"
        payload["events"][0].pop("executed_at_h")
        with self.assertRaisesRegex(ValueError, "早于续跑起点"):
            import_scenario(payload)
        payload["events"][0]["status"] = "executed"
        payload["events"][0]["executed_at_h"] = 7.0
        with self.assertRaisesRegex(ValueError, "晚于续跑起点"):
            import_scenario(payload)

    def test_wrong_json_types_return_validation_errors_not_type_errors(self):
        bad_profile = export_scenario(CellCulture("a549"))
        bad_profile["cell"]["profile_key"] = []
        with self.assertRaisesRegex(ValueError, "未知细胞系"):
            import_scenario(bad_profile)

        bad_action = export_scenario(CellCulture("a549"))
        bad_action["events"] = [{"at_time_h": 0, "action": [], "value": 1}]
        with self.assertRaisesRegex(ValueError, "类型不受支持"):
            import_scenario(bad_action)

        bad_status = export_scenario(CellCulture("a549"))
        bad_status["events"] = [{"at_time_h": 0, "action": "补充葡萄糖", "value": 1, "status": []}]
        with self.assertRaisesRegex(ValueError, "状态不受支持"):
            import_scenario(bad_status)

    def test_scenario_from_another_model_version_is_not_silently_loaded(self):
        payload = export_scenario(CellCulture("a549"))
        payload["model_version"] = "0.0.0"
        with self.assertRaisesRegex(ValueError, "场景模型版本为"):
            import_scenario(payload)
        self.assertNotEqual(MODEL_VERSION, payload["model_version"])

    def test_boolean_is_not_accepted_as_numeric_scenario_input(self):
        payload = export_scenario(CellCulture("a549"))
        payload["cell"]["initial_viable_cells"] = True
        with self.assertRaisesRegex(ValueError, "initial_viable_cells"):
            import_scenario(payload)

        payload = export_scenario(CellCulture("a549"))
        payload["events"] = [{"at_time_h": 12, "action": "补充葡萄糖", "value": True}]
        with self.assertRaisesRegex(ValueError, "缺少有效的执行时间或操作量"):
            import_scenario(payload)

    def test_unrepresentably_large_json_numbers_are_rejected_as_invalid_scenario_fields(self):
        huge = 10**10000
        cases = (
            ("run", "duration_h", "培养体积、面积、总时长和步长"),
            ("parameters", "growth_scale", "模型参数必须为数值"),
            ("environment", "glucose_mM", "环境字段 glucose_mM 必须为数值"),
        )
        for section, field, message in cases:
            with self.subTest(section=section, field=field):
                payload = export_scenario(CellCulture("a549"))
                payload[section][field] = huge
                with self.assertRaisesRegex(ValueError, message):
                    import_scenario(payload)

        payload = export_scenario(CellCulture("a549"), events=[{
            "action": "补充葡萄糖", "at_time_h": 1.0, "value": 1.0,
        }])
        payload["events"][0]["at_time_h"] = huge
        with self.assertRaisesRegex(ValueError, "缺少有效的执行时间或操作量"):
            import_scenario(payload)

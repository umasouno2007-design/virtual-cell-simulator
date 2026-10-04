"""Streamlit 界面状态同步的回归测试。"""

import unittest
from pathlib import Path
import time
import json

from calibration import CalibrationResult
from cell import CellCulture
from scenario import export_scenario
from streamlit.testing.v1 import AppTest


class AppStateTestCase(unittest.TestCase):
    @staticmethod
    def _set_mode(app, value: str) -> None:
        next(item for item in app.radio if item.label == "模拟模式").set_value(value).run(timeout=30)

    def test_environment_change_updates_metrics_in_same_rerun(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        app.session_state["coarse_calibration"] = CalibrationResult(1.0, 1.0, 0.1, [])
        ph_input = next(item for item in app.number_input if item.label == "当前 pH")

        ph_input.set_value(6.8).run(timeout=30)

        self.assertEqual(app.session_state["cell"].ph, 6.8)
        self.assertEqual(app.session_state["history"][-1]["pH"], 6.8)
        self.assertNotIn("coarse_calibration", app.session_state)
        self.assertIn("pH 偏离推荐范围", app.warning[0].value)
        self.assertEqual(len(app.exception), 0)

    def test_long_session_histories_are_trimmed_to_checkpoint_limits(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        single_cell_row = dict(app.session_state["single_cell_history"][-1])
        colony_row = dict(app.session_state["microcolony_history"][-1])
        single_cell_event = {"time_h": 0.0, "event": "测试记录"}
        culture_event = {"time_h": 0.0, "event": "测试记录", "details": ""}
        app.session_state["single_cell_history"] = [
            {**single_cell_row, "time_h": float(i)} for i in range(2005)
        ]
        app.session_state["microcolony_history"] = [
            {**colony_row, "time_h": float(i)} for i in range(2005)
        ]
        app.session_state["single_cell_events"] = [
            {**single_cell_event, "time_h": float(i)} for i in range(505)
        ]
        app.session_state["events"] = [
            {**culture_event, "time_h": float(i)} for i in range(505)
        ]

        app.run(timeout=30)

        self.assertEqual(len(app.session_state["single_cell_history"]), 2000)
        self.assertEqual(len(app.session_state["microcolony_history"]), 2000)
        self.assertEqual(len(app.session_state["single_cell_events"]), 500)
        self.assertEqual(len(app.session_state["events"]), 500)
        self.assertEqual(app.session_state["single_cell_history"][0]["time_h"], 5.0)
        self.assertEqual(app.session_state["single_cell_events"][0]["time_h"], 5.0)
        self.assertEqual(len(app.exception), 0)

    def test_visual_overview_and_action_feedback_are_present(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")

        self.assertTrue(any("ec-context" in item.value for item in app.markdown))
        reset_button = next(item for item in app.button if item.label == "创建/重置实验")
        reset_button.click().run(timeout=30)
        self.assertTrue(any("操作完成" in item.value for item in app.success))
        self.assertEqual(len(app.exception), 0)

    def test_calibration_initial_mismatch_warning_is_visible(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        app.session_state["coarse_calibration"] = CalibrationResult(
            1.0, 1.0, 0.1, [], warnings=["活细胞数的起点观测与模拟初值不同；请核对时间原点。"],
        )
        app.run(timeout=30)
        self.assertTrue(any("起点观测与模拟初值不同" in item.value for item in app.warning))
        self.assertEqual(len(app.exception), 0)

    def test_oxygen_change_triggers_bubbles(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        oxygen_input = next(
            item for item in app.number_input if item.label == "氧设定值（%）"
        )

        oxygen_input.set_value(12.0).run(timeout=30)

        self.assertEqual(app.session_state["visual_effect"], "oxygen")
        self.assertEqual(len(app.exception), 0)

    def test_running_culture_catches_up_from_wall_clock(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        before = app.session_state["cell"].time_h
        app.session_state["running"] = True
        app.session_state["time_multiplier"] = 3600
        app.session_state["last_wall_time"] = time.time() - 1.0

        app.run(timeout=30)

        self.assertGreater(app.session_state["cell"].time_h, before + 0.9)
        self.assertEqual(len(app.exception), 0)

    def test_glucose_button_triggers_sugar_particles(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        before = app.session_state["cell"].glucose_mm
        glucose_button = next(
            item for item in app.button if item.label == "补充葡萄糖"
        )

        glucose_button.click().run(timeout=30)

        self.assertAlmostEqual(app.session_state["cell"].glucose_mm, before + 1.0)
        self.assertEqual(app.session_state["events"][-1]["event"], "补充葡萄糖")
        self.assertEqual(app.session_state["visual_effect"], "glucose")
        self.assertEqual(len(app.exception), 0)

    def test_quality_control_panel_is_available_without_changing_model(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")

        source = next(item for item in app.text_input if item.label == "细胞来源 / 供应商")
        source.set_value("ATCC").run(timeout=30)

        self.assertEqual(app.session_state["cell"].profile_key, "hela")
        self.assertEqual(len(app.exception), 0)

    def test_scheduled_action_executes_when_simulation_reaches_its_time(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        start_time = app.session_state["cell"].time_h
        app.session_state["scheduled_actions"] = [{
            "at_time_h": start_time + 0.5,
            "action": "补充葡萄糖",
            "value": 1.0,
            "status": "pending",
        }]
        duration = next(item for item in app.selectbox if item.label == "每步时长（h）")
        duration.set_value(1.0).run(timeout=30)
        advance_button = next(item for item in app.button if item.label == "单步推进")
        advance_button.click().run(timeout=30)

        action = app.session_state["scheduled_actions"][0]
        self.assertEqual(action["status"], "executed")
        self.assertAlmostEqual(action["executed_at_h"], start_time + 0.5, places=5)
        self.assertEqual(app.session_state["events"][-2]["event"], "计划执行：补充葡萄糖")
        self.assertEqual(len(app.exception), 0)

    def test_scheduled_intracellular_stress_is_applied_at_its_time(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        start_time = app.session_state["cell"].time_h
        initial_ros = app.session_state["intracellular"].ros_percent
        app.session_state["scheduled_actions"] = [{
            "at_time_h": start_time + 0.25,
            "action": "施加氧化刺激",
            "value": 30.0,
            "status": "pending",
        }]
        advance_button = next(item for item in app.button if item.label == "单步推进")
        advance_button.click().run(timeout=30)

        action = app.session_state["scheduled_actions"][0]
        self.assertEqual(action["status"], "executed")
        self.assertGreater(app.session_state["intracellular"].ros_percent, initial_ros + 20.0)
        self.assertEqual(app.session_state["events"][-2]["event"], "计划执行：施加氧化刺激")
        self.assertEqual(len(app.exception), 0)

    def test_intracellular_mode_renders_organelles_and_metrics(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")

        mode.set_value("单细胞实验室").run(timeout=30)

        cell_diagram = app.get("iframe")[0].proto.srcdoc
        self.assertIn("atlas-card", cell_diagram)
        self.assertIn("data:image/png;base64,", cell_diagram)
        self.assertIn("data-atp=", cell_diagram)
        for marker in (
            "cell-stage", "tag nucleus", "tag mitochondria", "tag rer",
            "tag ser", "tag golgi", "tag lysosome", "mito-glow", "rosPulse",
        ):
            self.assertIn(marker, cell_diagram)
        metric_grid = next(
            item for item in app.markdown
            if '<div class="vc-metric-grid">' in item.value
        )
        self.assertIn("ATP 水平", metric_grid.value)
        self.assertIn("DNA 损伤", metric_grid.value)
        self.assertIn("胞质 Ca²⁺ 代理", metric_grid.value)
        self.assertNotIn(" nM", metric_grid.value)
        self.assertTrue(any("不是实测胞质钙浓度" in item.value for item in app.caption))
        self.assertTrue(any("乳酸会记录到环境轨迹，但当前单细胞状态方程不直接使用" in item.value for item in app.caption))
        self.assertEqual(len(app.exception), 0)

    def test_single_cell_environment_and_intervention_are_recorded_as_events(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")
        mode.set_value("单细胞实验室").run(timeout=30)
        glucose = next(item for item in app.number_input if item.label == "葡萄糖（mM）")
        glucose.set_value(3.0).run(timeout=30)

        change = app.session_state["single_cell_events"][-1]
        self.assertEqual(change["event_type"], "environment_update")
        self.assertEqual(change["changes"]["glucose_mM"], {"from": 5.5, "to": 3.0})
        stress = next(item for item in app.button if item.label == "施加教学性氧化压力")
        stress.click().run(timeout=30)
        intervention = app.session_state["single_cell_events"][-1]
        self.assertEqual(intervention["event_type"], "oxidative_stress")
        self.assertEqual(intervention["input_index"], 20.0)
        self.assertEqual(intervention["environment"]["glucose_mM"], 3.0)
        change_table = next(
            item.value for item in app.dataframe
            if "变化速率（指数点/h）" in item.value.columns
        )
        ros_change = change_table.loc[change_table["指标"] == "ROS"].iloc[0]
        self.assertIsNone(ros_change["变化速率（指数点/h）"])
        self.assertGreater(ros_change["较上一条记录变化（指数点）"], 0.0)
        self.assertEqual(len(app.exception), 0)

    def test_loading_culture_environment_copies_inputs_without_advancing_culture(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        next(item for item in app.number_input if item.label == "当前 pH").set_value(6.8).run(timeout=30)
        culture_snapshot = app.session_state["cell"].snapshot()

        self._set_mode(app, "单细胞实验室")
        next(item for item in app.button if item.label == "从培养工作流载入当前环境").click().run(timeout=30)
        self.assertEqual(app.session_state["single_cell_environment"].ph, 6.8)
        self.assertEqual(app.session_state["cell"].snapshot(), culture_snapshot)
        self.assertEqual(len(app.exception), 0)

    def test_data_inspired_hypothesis_page_is_read_only_and_exportable(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        original_state = app.session_state["single_cell_state"].snapshot().copy()
        original_environment = app.session_state["single_cell_environment"].snapshot().copy()
        self._set_mode(app, "数据启发假设")

        self.assertTrue(any("GSE164241" in item.value for item in app.markdown))
        self.assertTrue(any("CASP3" in item.value and "OSscore" in item.value for item in app.markdown))
        self.assertTrue(any("本地口腔单细胞项目的结果表未包含" in item.value for item in app.warning))
        self.assertTrue(any("BM150" in item.value for item in app.warning))
        self.assertTrue(any(item.label == "导出教学假设情景 JSON" for item in app.get("download_button")))
        self.assertEqual(app.session_state["single_cell_state"].snapshot(), original_state)
        self.assertEqual(app.session_state["single_cell_environment"].snapshot(), original_environment)
        self.assertEqual(len(app.exception), 0)

    def test_context_bar_uses_mode_specific_time_and_calibration_status(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")
        self.assertEqual(mode.value, "单细胞实验室")
        culture_baseline = app.session_state["cell"].snapshot()
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertIn("t = 0.0 h", context)
        self.assertIn("细胞系未特异校准", context)
        self.assertNotIn("HeLa", context)
        self.assertIn("相对状态规则未校准", context)

        next(item for item in app.button if item.label == "推进 6 h").click().run(timeout=30)
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertIn("t = 6.0 h", context)
        self.assertNotIn("透明初值探索", context)
        self.assertEqual(app.session_state["cell"].time_h, 0.0)
        self.assertEqual(app.session_state["cell"].snapshot(), culture_baseline)

        next(item for item in app.button if item.label == "单步 1 h").click().run(timeout=30)
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertIn("t = 7.0 h", context)

        next(item for item in app.radio if item.label == "模拟模式").set_value("微型细胞群").run(timeout=30)
        next(item for item in app.button if item.label == "推进微群体 1 h").click().run(timeout=30)
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertIn("t = 1.0 h", context)
        self.assertIn("异质性/通信为教学规则", context)
        self.assertIn("细胞系未特异校准", context)
        self.assertEqual(app.session_state["cell"].snapshot(), culture_baseline)
        subgroup_table = next(
            item.value for item in app.dataframe
            if "占代表性细胞比例（%）" in item.value.columns
        )
        self.assertAlmostEqual(subgroup_table["占代表性细胞比例（%）"].sum(), 100.0)

        next(item for item in app.radio if item.label == "模拟模式").set_value("培养环境与数据工作流").run(timeout=30)
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertIn("t = 0.0 h", context)
        self.assertIn("HeLa", context)
        next(item for item in app.selectbox if item.label == "运行步数").select(6).run(timeout=30)
        next(item for item in app.button if item.label == "单步推进").click().run(timeout=30)
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertIn("t = 6.0 h", context)
        self.assertEqual(len(app.exception), 0)

    def test_calibration_ui_reports_a_real_temporal_holdout(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        csv_bytes = b"time_h,viable_cells,glucose_mM\n0,250000,5.5\n12,280000,5.2\n24,315000,4.9\n36,350000,4.5\n48,390000,4.1\n"
        next(item for item in app.file_uploader if item.label == "选择实测 CSV（最大 5 MiB）").upload(
            "teaching.csv", csv_bytes, "text/csv",
        ).run(timeout=30)
        next(item for item in app.button if item.label == "计算两参数粗校准").click().run(timeout=60)
        result = app.session_state["coarse_calibration"]
        self.assertEqual(result.training_time_h, [0.0, 12.0, 24.0])
        self.assertEqual(result.holdout_time_h, [36.0, 48.0])
        self.assertTrue(result.training_metrics)
        self.assertTrue(result.holdout_metrics)
        self.assertEqual(len(app.exception), 0)

    def test_measurement_alignment_warns_when_simulation_has_not_reached_observations(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        next(item for item in app.file_uploader if item.label == "选择实测 CSV（最大 5 MiB）").upload(
            "observations.csv",
            b"time_h,viable_cells\n0,250000\n24,280000\n48,315000\n",
            "text/csv",
        ).run(timeout=30)
        self.assertTrue(any("不在当前模拟轨迹" in item.value for item in app.warning))
        self.assertEqual(len(app.exception), 0)

    def test_measurement_dataset_replacement_and_explicit_removal_clear_stale_calibration(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        csv_a = b"time_h,viable_cells\n0,100\n24,250\n48,500\n72,700\n96,900\n"
        uploader = next(item for item in app.file_uploader if item.label == "选择实测 CSV（最大 5 MiB）")
        uploader.upload("first.csv", csv_a, "text/csv").run(timeout=30)
        self.assertEqual(app.session_state["measurement_data"].iloc[0]["viable_cells"], 100)
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertIn("模拟 + 实测 CSV", context)
        self.assertIn("通过：最低条件", context)
        import_timestamp = app.session_state["measurement_quality_report"]["imported_at"]
        app.run(timeout=30)
        self.assertEqual(
            app.session_state["measurement_quality_report"]["imported_at"],
            import_timestamp,
        )

        app.session_state["coarse_calibration"] = CalibrationResult(1.0, 1.0, 0.1, [])
        csv_b = b"time_h,viable_cells\n0,200\n24,350\n48,600\n72,900\n96,1100\n"
        next(item for item in app.file_uploader if item.label == "选择实测 CSV（最大 5 MiB）").upload(
            "second.csv", csv_b, "text/csv",
        ).run(timeout=30)
        self.assertEqual(app.session_state["measurement_data"].iloc[0]["viable_cells"], 200)
        self.assertNotIn("coarse_calibration", app.session_state)
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertIn("模拟 + 实测 CSV", context)

        app.session_state["coarse_calibration"] = CalibrationResult(1.0, 1.0, 0.1, [])
        self._set_mode(app, "单细胞实验室")
        self._set_mode(app, "培养环境与数据工作流")
        self.assertEqual(app.session_state["measurement_data"].iloc[0]["viable_cells"], 200)
        next(item for item in app.button if item.label == "移除当前实测数据及其校准结果").click().run(timeout=30)
        self.assertNotIn("measurement_data", app.session_state)
        self.assertNotIn("measurement_quality_report", app.session_state)
        self.assertNotIn("coarse_calibration", app.session_state)
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertIn("未导入实测数据", context)

        next(item for item in app.file_uploader if item.label == "选择实测 CSV（最大 5 MiB）").upload(
            "third.csv", csv_a, "text/csv",
        ).run(timeout=30)
        app.session_state["coarse_calibration"] = CalibrationResult(1.0, 1.0, 0.1, [])
        invalid_csv = b"unknown_column\n1\n2\n"
        next(item for item in app.file_uploader if item.label == "选择实测 CSV（最大 5 MiB）").upload(
            "invalid.csv", invalid_csv, "text/csv",
        ).run(timeout=30)
        self.assertNotIn("measurement_data", app.session_state)
        self.assertNotIn("coarse_calibration", app.session_state)
        self.assertTrue(any("无法读取实测数据" in item.value for item in app.error))
        self.assertEqual(len(app.exception), 0)

    def test_changing_culture_profile_preserves_csv_but_blocks_cross_profile_alignment(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        csv_bytes = b"time_h,viable_cells\n0,100\n24,250\n48,500\n72,700\n96,900\n"
        next(item for item in app.file_uploader if item.label == "选择实测 CSV（最大 5 MiB）").upload(
            "measurements.csv", csv_bytes, "text/csv",
        ).run(timeout=30)
        self.assertEqual(app.session_state["measurement_data_profile_key"], "hela")
        app.session_state["coarse_calibration"] = CalibrationResult(1.0, 1.0, 0.1, [])

        next(item for item in app.selectbox if item.label == "细胞类型").set_value("a549").run(timeout=30)
        next(item for item in app.button if item.label == "创建/重置实验").click().run(timeout=30)

        self.assertEqual(app.session_state["cell"].profile_key, "a549")
        self.assertEqual(app.session_state["measurement_data_profile_key"], "hela")
        self.assertIsNotNone(app.session_state["measurement_data"])
        self.assertNotIn("coarse_calibration", app.session_state)
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertIn("A549（肺腺癌）", context)
        self.assertIn("不同", context)
        self.assertTrue(any("格式检查" in item.value for item in app.warning))
        self.assertFalse(any(item.label == "运行透明两参数粗校准" for item in app.button))
        self.assertFalse(any("模拟—实测残差" in item.value for item in app.markdown))
        self.assertEqual(len(app.exception), 0)

    def test_scenario_import_syncs_profile_and_does_not_reapply_old_environment_widgets(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        next(item for item in app.number_input if item.label == "当前 pH").set_value(6.8).run(timeout=30)
        target = CellCulture("a549")
        target.ph = 7.15
        payload = json.dumps(export_scenario(target), ensure_ascii=False).encode("utf-8")
        next(item for item in app.file_uploader if item.label == "导入场景 JSON").upload(
            "scenario.json", payload, "application/json",
        ).run(timeout=30)
        next(item for item in app.button if item.label == "校验并载入场景").click().run(timeout=30)

        self.assertEqual(app.session_state["cell"].profile_key, "a549")
        self.assertEqual(app.session_state["profile_key"], "a549")
        self.assertAlmostEqual(app.session_state["cell"].ph, 7.15)
        self.assertAlmostEqual(app.session_state["environment_ph"], 7.15)
        self.assertEqual(len(app.exception), 0)

    def test_non_finite_csv_is_retained_for_review_but_excluded_from_primary_plot(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        csv_bytes = b"time_h,viable_cells,oxygen_percent\n0,100,20\n24,200,inf\n48,300,18\n"
        next(item for item in app.file_uploader if item.label == "选择实测 CSV（最大 5 MiB）").upload(
            "non_finite.csv", csv_bytes, "text/csv",
        ).run(timeout=30)
        self.assertIsNotNone(app.session_state["measurement_data"])
        self.assertTrue(
            any("无穷值" in item[0] for item in app.session_state["measurement_quality_report"]["blocked"]),
            app.session_state["measurement_quality_report"],
        )
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertIn("阻断：格式问题", context)
        self.assertFalse(any(item.label == "运行透明两参数粗校准" for item in app.button))
        self.assertEqual(len(app.exception), 0)

    def test_running_culture_context_bar_catches_up_with_live_clock(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        self._set_mode(app, "培养环境与数据工作流")
        start_time = app.session_state["cell"].time_h
        app.session_state["running"] = True
        app.session_state["time_multiplier"] = 3600
        app.session_state["last_wall_time"] = time.time() - 1.0

        app.run(timeout=30)
        context = next(item.value for item in app.markdown if '<div class="ec-context"' in item.value)
        self.assertGreater(app.session_state["cell"].time_h, start_time + 0.9)
        self.assertRegex(context, r"t = [1-9][0-9]*\.")
        self.assertEqual(len(app.exception), 0)

    def test_core_organelle_click_updates_focus_and_celldex(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")
        mode.set_value("单细胞实验室").run(timeout=30)
        mitochondria = next(item for item in app.button if item.label == "线粒体")
        mitochondria.click().run(timeout=30)
        self.assertEqual(app.session_state["focused_organelle"], "mitochondria")
        self.assertIn("mitochondria", app.session_state["celldex_discovered"])
        self.assertEqual(app.session_state["events"][-1]["event"], "探索细胞器")
        self.assertEqual(len(app.exception), 0)

    def test_intracellular_virtual_sample_is_recorded_and_traceable(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")
        mode.set_value("单细胞实验室").run(timeout=30)
        sample_button = next(item for item in app.button if item.label == "记录采样")
        sample_button.click().run(timeout=30)

        sample = app.session_state["intracellular_samples"][-1]
        self.assertEqual(sample["focus_readout"], "ATP")
        self.assertEqual(app.session_state["events"][-1]["event"], "记录虚拟采样")
        self.assertEqual(len(app.exception), 0)

    def test_virtual_assay_plate_is_explicitly_marked_as_synthetic(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")
        mode.set_value("单细胞实验室").run(timeout=30)
        plate_button = next(item for item in app.button if item.label == "生成合成检测读出")
        plate_button.click().run(timeout=30)

        rows = app.session_state["virtual_assay_rows"]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["is_synthetic_demo"] for row in rows))
        self.assertEqual(app.session_state["events"][-1]["event"], "生成虚拟检测")
        self.assertEqual(len(app.exception), 0)

    def test_intracellular_baseline_can_be_saved_for_intervention_comparison(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")
        mode.set_value("单细胞实验室").run(timeout=30)
        baseline_button = next(item for item in app.button if item.label == "设为当前基线")
        baseline_button.click().run(timeout=30)

        baseline = app.session_state["intracellular_baseline"]
        self.assertIsNotNone(baseline)
        self.assertIn("ATP_percent", baseline["snapshot"])
        self.assertEqual(app.session_state["events"][-1]["event"], "记录细胞内基线")
        self.assertEqual(len(app.exception), 0)

    def test_intracellular_observation_note_captures_hypothesis_and_state(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")
        mode.set_value("单细胞实验室").run(timeout=30)
        note_input = next(item for item in app.text_area if item.label == "观察或假设")
        note_input.set_value("ROS 的变化需要实测确认。").run(timeout=30)
        note_button = next(item for item in app.button if item.label == "保存观察笔记")
        note_button.click().run(timeout=30)

        note = app.session_state["intracellular_notes"][-1]
        self.assertEqual(note["focus"], "能量代谢")
        self.assertIn("ROS", note["note"])
        self.assertEqual(app.session_state["events"][-1]["event"], "保存细胞内观察笔记")
        self.assertEqual(len(app.exception), 0)

    def test_pathway_trace_highlights_related_organelle(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")
        mode.set_value("单细胞实验室").run(timeout=30)
        trace_button = next(item for item in app.button if item.label == "定位关联通路")
        trace_button.click().run(timeout=30)

        self.assertEqual(app.session_state["focused_organelle"], "mitochondria")
        self.assertEqual(app.session_state["events"][-1]["event"], "追踪细胞内信号链")
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()

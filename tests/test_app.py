"""Streamlit 界面状态同步的回归测试。"""

import unittest
from pathlib import Path
import time

from streamlit.testing.v1 import AppTest


class AppStateTestCase(unittest.TestCase):
    def test_environment_change_updates_metrics_in_same_rerun(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        ph_input = next(item for item in app.number_input if item.label == "当前 pH")

        ph_input.set_value(6.8).run(timeout=30)

        metric_grid = next(
            item for item in app.markdown
            if '<div class="vc-metric-grid">' in item.value
        )
        self.assertEqual(app.session_state["cell"].ph, 6.8)
        self.assertIn("6.80", metric_grid.value)
        self.assertIn("pH 偏离推荐范围", app.warning[0].value)
        self.assertEqual(len(app.exception), 0)

    def test_visual_overview_and_action_feedback_are_present(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)

        self.assertTrue(any("vc-overview" in item.value for item in app.get("html")))
        reset_button = next(item for item in app.button if item.label == "创建/重置实验")
        reset_button.click().run(timeout=30)
        self.assertTrue(any("操作完成" in item.value for item in app.success))
        self.assertEqual(len(app.exception), 0)

    def test_oxygen_change_triggers_bubbles(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        oxygen_input = next(
            item for item in app.number_input if item.label == "氧设定值（%）"
        )

        oxygen_input.set_value(12.0).run(timeout=30)

        self.assertTrue(
            any('data-effect="oxygen-' in item.value for item in app.get("html"))
        )
        self.assertEqual(len(app.exception), 0)

    def test_running_culture_catches_up_from_wall_clock(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
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
        before = app.session_state["cell"].glucose_mm
        glucose_button = next(
            item for item in app.button if item.label == "🍬 投入葡萄糖"
        )

        glucose_button.click().run(timeout=30)

        self.assertAlmostEqual(app.session_state["cell"].glucose_mm, before + 1.0)
        self.assertEqual(app.session_state["events"][-1]["event"], "补充葡萄糖")
        self.assertTrue(
            any("vc-html-sugar" in item.value for item in app.get("html"))
        )
        self.assertEqual(len(app.exception), 0)

    def test_quality_control_panel_is_available_without_changing_model(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)

        source = next(item for item in app.text_input if item.label == "细胞来源 / 供应商")
        source.set_value("ATCC").run(timeout=30)

        self.assertEqual(app.session_state["cell"].profile_key, "hela")
        self.assertEqual(len(app.exception), 0)

    def test_scheduled_action_executes_when_simulation_reaches_its_time(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
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

        mode.set_value("细胞生命活动").run(timeout=30)

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
        self.assertEqual(len(app.exception), 0)

    def test_core_organelle_click_updates_focus_and_celldex(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")
        mode.set_value("细胞生命活动").run(timeout=30)
        mitochondria = next(item for item in app.button if item.label == "⚡ 线粒体")
        mitochondria.click().run(timeout=30)
        self.assertEqual(app.session_state["focused_organelle"], "mitochondria")
        self.assertIn("mitochondria", app.session_state["celldex_discovered"])
        self.assertEqual(app.session_state["events"][-1]["event"], "探索细胞器")
        self.assertEqual(len(app.exception), 0)

    def test_intracellular_virtual_sample_is_recorded_and_traceable(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")
        mode.set_value("细胞生命活动").run(timeout=30)
        sample_button = next(item for item in app.button if item.label == "🔬 记录采样")
        sample_button.click().run(timeout=30)

        sample = app.session_state["intracellular_samples"][-1]
        self.assertEqual(sample["focus_readout"], "ATP")
        self.assertEqual(app.session_state["events"][-1]["event"], "记录虚拟采样")
        self.assertEqual(len(app.exception), 0)

    def test_virtual_assay_plate_is_explicitly_marked_as_synthetic(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")
        mode.set_value("细胞生命活动").run(timeout=30)
        plate_button = next(item for item in app.button if item.label == "生成虚拟读板")
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
        mode.set_value("细胞生命活动").run(timeout=30)
        baseline_button = next(item for item in app.button if item.label == "📍 设为当前基线")
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
        mode.set_value("细胞生命活动").run(timeout=30)
        note_input = next(item for item in app.text_area if item.label == "观察或假设")
        note_input.set_value("ROS 的变化需要实测确认。").run(timeout=30)
        note_button = next(item for item in app.button if item.label == "📝 保存观察笔记")
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
        mode.set_value("细胞生命活动").run(timeout=30)
        trace_button = next(item for item in app.button if item.label == "✨ 高亮并追踪此链")
        trace_button.click().run(timeout=30)

        self.assertEqual(app.session_state["focused_organelle"], "mitochondria")
        self.assertEqual(app.session_state["events"][-1]["event"], "追踪细胞内信号链")
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()

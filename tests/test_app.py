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
        app.button[0].click().run(timeout=30)
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
        self.assertTrue(
            any("vc-html-sugar" in item.value for item in app.get("html"))
        )
        self.assertEqual(len(app.exception), 0)

    def test_intracellular_mode_renders_organelles_and_metrics(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(app_path).run(timeout=30)
        mode = next(item for item in app.radio if item.label == "模拟模式")

        mode.set_value("细胞生命活动").run(timeout=30)

        cell_diagram = app.get("iframe")[0].proto.srcdoc
        self.assertIn("atlas-card", cell_diagram)
        self.assertIn("/app/static/cell-atlas-v1.png", cell_diagram)
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


if __name__ == "__main__":
    unittest.main()

"""单细胞变化摘要的边界测试。"""

import unittest

from intracellular import IntracellularState
from state_reporting import intracellular_change_summary


class IntracellularChangeSummaryTests(unittest.TestCase):
    def test_snapshot_keys_cover_all_primary_relative_indices(self):
        snapshot = IntracellularState().snapshot()
        rows = intracellular_change_summary([snapshot])
        self.assertEqual(len(rows), 10)
        self.assertEqual({row["指标"] for row in rows}, {
            "ATP", "线粒体功能", "糖酵解", "ROS", "DNA 损伤", "ER 应激",
            "自噬适应/回收", "蛋白合成", "增殖信号", "促凋亡压力",
        })

    def test_positive_time_step_reports_delta_and_rate(self):
        rows = intracellular_change_summary([
            {"time_h": 1.0, "ATP_percent": 60.0},
            {"time_h": 3.0, "ATP_percent": 70.0},
        ])
        atp = next(row for row in rows if row["指标"] == "ATP")
        self.assertEqual(atp["当前值（相对指数，0–100）"], 70.0)
        self.assertEqual(atp["较上一条记录变化（指数点）"], 10.0)
        self.assertEqual(atp["变化速率（指数点/h）"], 5.0)

    def test_same_time_intervention_keeps_delta_but_does_not_divide_by_zero(self):
        rows = intracellular_change_summary([
            {"time_h": 2.0, "ROS_percent": 20.0},
            {"time_h": 2.0, "ROS_percent": 35.0},
        ])
        ros = next(row for row in rows if row["指标"] == "ROS")
        self.assertEqual(ros["较上一条记录变化（指数点）"], 15.0)
        self.assertIsNone(ros["变化速率（指数点/h）"])
        self.assertIn("同一模拟时点", ros["说明"])

    def test_invalid_or_missing_history_is_safe(self):
        self.assertEqual(intracellular_change_summary([]), [])
        rows = intracellular_change_summary([
            {"time_h": 4.0, "ATP_percent": 10.0},
            {"time_h": 3.0, "ATP_percent": float("nan")},
        ])
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()

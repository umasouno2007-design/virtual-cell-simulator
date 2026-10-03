"""公开数据—模型假设映射的结构和只读导出回归测试。"""

import json
import csv
import tempfile
import unittest
from pathlib import Path

from data_model_hypotheses import (
    export_hypothesis_scenario_json,
    load_hypothesis_scenario,
    validate_hypothesis_scenario,
)
from cell_scenario import import_single_cell_scenario
from version import MODEL_VERSION
from scripts.run_data_inspired_hypothesis import run_scenario


class DataModelHypothesesTestCase(unittest.TestCase):
    def test_repository_mapping_keeps_observations_and_hypothesis_distinct(self) -> None:
        scenario = load_hypothesis_scenario()
        self.assertIn("GSE164241", scenario["source_data"]["dataset"])
        self.assertEqual(scenario["observed_pattern"]["cell_types"][0], "单核细胞")
        self.assertIn("TXN", scenario["observed_pattern"]["reported_genes"])
        self.assertIn("未提取", scenario["observed_pattern"]["reported_score"])
        self.assertIn("BM150", scenario["source_data"]["single_cell_sample_reference"])
        self.assertIn("GSM5005058", scenario["source_data"]["disease_sample_reference"])
        self.assertIn("单一 GSM", scenario["source_data"]["provenance_conflict"])
        self.assertIn("牙周炎样本使用其他 accession", scenario["source_data"]["provenance_conflict"])
        self.assertIn("不是", scenario["teaching_hypothesis"]["mapping_boundary"])
        self.assertEqual(scenario["evidence"]["model_mapping_grade"], "C")
        self.assertEqual(scenario["model_version"], MODEL_VERSION)
        self.assertFalse(scenario["teaching_scenario"]["default_enabled"])
        self.assertTrue(scenario["not_calibrated"])

    def test_local_mapping_template_cannot_be_mistaken_for_real_results(self) -> None:
        template_path = Path(__file__).resolve().parents[1] / "data" / "hypothesis_mapping_template.json"
        template = json.loads(template_path.read_text(encoding="utf-8"))
        self.assertEqual(template["status"], "template_only")
        self.assertIsNone(template["observations"][0]["reported_value"])
        self.assertEqual(template["observations"][0]["marker_genes"], [])
        self.assertFalse(template["model_mapping"]["parameter_calibration_allowed"])
        self.assertEqual(template["model_mapping"]["mapping_evidence_grade"], "C")

    def test_scenario_json_export_is_parseable_and_contains_no_calibration(self) -> None:
        payload = json.loads(export_hypothesis_scenario_json())
        scenario = load_hypothesis_scenario()
        validate_hypothesis_scenario(scenario)
        self.assertEqual(payload["schema"], "e-cell-single-cell/v1")
        self.assertEqual(payload["data_inspired_hypothesis"]["source_dataset"], "GSE164241")
        self.assertTrue(payload["data_inspired_hypothesis"]["source_dataset_url"].startswith("https://"))
        self.assertTrue(payload["data_inspired_hypothesis"]["source_disease_sample_url"].startswith("https://"))
        self.assertEqual(payload["data_inspired_hypothesis"]["source_provenance_status"], "unresolved_accession_scope")
        self.assertEqual(payload["data_inspired_hypothesis"]["model_mapping_grade"], "C")
        self.assertEqual(payload["data_inspired_hypothesis"]["parameter_calibration"], "none")
        self.assertIn("provenance unresolved", payload["data_inspired_hypothesis"]["public_observation_grade"])
        self.assertEqual(payload["data_inspired_hypothesis"]["reproduction_protocol"]["duration_h"], 24.0)
        self.assertTrue(payload["data_inspired_hypothesis"]["provenance_warning"])
        self.assertTrue(payload["data_inspired_hypothesis"]["not_calibrated"])
        self.assertEqual(scenario["teaching_scenario"]["relative_input_index"], 20.0)
        self.assertEqual(scenario["teaching_scenario"]["time_step_h"], 1.0)
        self.assertEqual(scenario["teaching_scenario"]["suggested_duration_h"], 24.0)
        self.assertTrue(any("阈值" in item for item in scenario["not_calibrated"]))
        _, state, history, events = import_single_cell_scenario(payload)
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(state.ros_percent, 30.0)
        self.assertEqual(events[0]["event_type"], "oxidative_stress")

        replay_a = import_single_cell_scenario(payload)
        replay_b = import_single_cell_scenario(payload)
        for env, replay_state, _, _ in (replay_a, replay_b):
            for _ in range(24):
                replay_state.step(env, 1.0)
                env.time_h = replay_state.time_h
        self.assertEqual(replay_a[1].snapshot(), replay_b[1].snapshot())

    def test_invalid_default_flag_and_out_of_range_intervention_are_rejected(self) -> None:
        scenario = load_hypothesis_scenario()
        scenario["teaching_scenario"]["default_enabled"] = True
        with self.assertRaisesRegex(ValueError, "不得成为模型默认"):
            validate_hypothesis_scenario(scenario)

        scenario = load_hypothesis_scenario()
        scenario["teaching_scenario"]["relative_input_index"] = 101
        with self.assertRaisesRegex(ValueError, "0–100"):
            validate_hypothesis_scenario(scenario)

    def test_incomplete_provenance_environment_and_calibration_claims_are_rejected(self) -> None:
        scenario = load_hypothesis_scenario()
        scenario["source_data"].pop("dataset_url")
        with self.assertRaisesRegex(ValueError, "accession、文献"):
            validate_hypothesis_scenario(scenario)

        scenario = load_hypothesis_scenario()
        scenario["source_data"]["dataset_url"] = "https://"
        with self.assertRaisesRegex(ValueError, "有效主机名"):
            validate_hypothesis_scenario(scenario)

        scenario = load_hypothesis_scenario()
        scenario["teaching_scenario"]["initial_environment"]["pH"] = True
        with self.assertRaisesRegex(ValueError, "必须为有限数值"):
            validate_hypothesis_scenario(scenario)

        scenario = load_hypothesis_scenario()
        scenario["evidence"]["parameter_calibration"] = "transcriptomics"
        with self.assertRaisesRegex(ValueError, "不得写为 e-cell 参数校准"):
            validate_hypothesis_scenario(scenario)

        scenario = load_hypothesis_scenario()
        scenario["model_version"] = "0.0.0"
        with self.assertRaisesRegex(ValueError, "基于模型 v0.0.0"):
            validate_hypothesis_scenario(scenario)

        scenario = load_hypothesis_scenario()
        scenario["source_data"]["provenance_status"] = "verified"
        with self.assertRaisesRegex(ValueError, "不能标为已核实"):
            validate_hypothesis_scenario(scenario)

    def test_reproduction_script_writes_repeatable_24_hour_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            json_path, csv_path = run_scenario(output_dir)
            first_json = json_path.read_bytes()
            first_csv = csv_path.read_bytes()
            second_json, second_csv = run_scenario(output_dir)
            self.assertEqual(first_json, second_json.read_bytes())
            self.assertEqual(first_csv, second_csv.read_bytes())
            with second_csv.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 25)
            self.assertAlmostEqual(float(rows[0]["time_h"]), 0.0)
            self.assertAlmostEqual(float(rows[-1]["time_h"]), 24.0)
            self.assertIn("model_version", rows[0])
            self.assertEqual(rows[-1]["source_provenance_status"], "unresolved_accession_scope")
            self.assertEqual(rows[-1]["parameter_calibration"], "none")
            self.assertTrue(rows[-1]["source_sample_url"].startswith("https://"))
            self.assertIn("不等同于", rows[-1]["interpretation_limit"])
            self.assertIn("calcium_relative_index", rows[-1])
            self.assertNotIn("calcium_nM", rows[-1])
            self.assertIn("ATP_relative_index", rows[-1])


if __name__ == "__main__":
    unittest.main()

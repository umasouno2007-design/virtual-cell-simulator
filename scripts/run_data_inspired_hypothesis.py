"""按数据启发假设 JSON 可重复运行教学情景，不拟合或改写模型参数。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cell_scenario import import_single_cell_scenario, single_cell_history_row
from data_model_hypotheses import export_hypothesis_scenario_json
from version import MODEL_VERSION

RELATIVE_INDEX_COLUMNS = {
    "ATP_percent": "ATP_relative_index",
    "mitochondrial_potential_percent": "mitochondrial_potential_relative_index",
    "glycolysis_percent": "glycolysis_relative_index",
    "ROS_percent": "ROS_relative_index",
    "calcium_nM": "calcium_relative_index",
    "DNA_damage_percent": "DNA_damage_relative_index",
    "ER_stress_percent": "ER_stress_relative_index",
    "autophagy_percent": "autophagy_relative_index",
    "protein_synthesis_percent": "protein_synthesis_relative_index",
    "growth_signal_percent": "growth_signal_relative_index",
    "apoptosis_signal_percent": "pro_apoptotic_pressure_relative_index",
    "cycle_progress_percent": "cycle_progress_relative_index",
}


def run_scenario(output_dir: Path) -> tuple[Path, Path]:
    """运行仓库内教学情景并写出场景 JSON 与相对状态时间线 CSV。

    输出不是转录组重分析或实验校准；CSV 指标为单细胞代理状态。
    """

    scenario_json = export_hypothesis_scenario_json()
    scenario_payload: dict[str, Any] = json.loads(scenario_json)
    environment, state, history, _events = import_single_cell_scenario(scenario_payload)
    protocol = scenario_payload["data_inspired_hypothesis"]["reproduction_protocol"]
    step_h = float(protocol["time_step_h"])
    duration_h = float(protocol["duration_h"])
    step_count = round(duration_h / step_h)
    provenance = scenario_payload["data_inspired_hypothesis"]

    for _ in range(step_count):
        state.step(environment, step_h)
        environment.time_h = state.time_h
        history.append(single_cell_history_row(state, environment))

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "oral_periodontitis_oxidative_stress_teaching_hypothesis.json"
    csv_path = output_dir / "single_cell_relative_state_timeline.csv"
    json_path.write_text(scenario_json, encoding="utf-8", newline="\n")
    for row in history:
        for old_name, relative_name in RELATIVE_INDEX_COLUMNS.items():
            if old_name in row:
                row[relative_name] = row.pop(old_name)
        row["model_version"] = MODEL_VERSION
        row["model_mapping_grade"] = provenance["model_mapping_grade"]
        row["parameter_calibration"] = "none"
        row["output_type"] = "teaching_relative_state_index"
        row["source_dataset"] = provenance["source_dataset"]
        row["source_provenance_status"] = provenance["source_provenance_status"]
        row["source_paper_url"] = provenance["source_paper_url"]
        row["source_dataset_url"] = provenance["source_dataset_url"]
        row["source_sample_url"] = provenance["source_sample_url"]
        row["source_disease_sample_url"] = provenance["source_disease_sample_url"]
        row["interpretation_limit"] = (
            "相对状态指数；教学规则；不等同于基因表达、蛋白/酶活、实验浓度、"
            "单细胞测量、公开数据重分析或临床结论。"
        )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    return json_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="复跑数据启发的单细胞教学情景（非模型校准）")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/data_inspired_hypothesis"),
        help="输出目录（默认：outputs/data_inspired_hypothesis）",
    )
    args = parser.parse_args()
    json_path, csv_path = run_scenario(args.output_dir)
    print(f"教学情景 JSON：{json_path}")
    print(f"单细胞相对状态时间线：{csv_path}")
    print("说明：结果来自现有教学规则；不是公开数据复现、实验测量或参数校准。")


if __name__ == "__main__":
    main()

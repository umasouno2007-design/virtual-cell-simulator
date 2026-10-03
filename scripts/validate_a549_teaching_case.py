"""运行 A549 教学合成数据的留出验证案例。

这不是独立生物学验证：数据是公开分发的教学合成数据，用于验证 e-cell 的
CSV 对齐、透明两参数粗校准、误差汇总与可视化流程可以重复运行。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calibration import fit_growth_and_uptake, replay_from_initial
from cell import CellCulture
from data_quality import quality_report
from experiment_data import (
    comparison_frame, measurement_fingerprint, residual_summary,
    standardize_measurements,
)
from version import MODEL_VERSION


DEFAULT_DATA = ROOT / "data" / "a549_teaching_synthetic.csv"
EXPECTED_TEACHING_SHA256 = "b6faa825617102a991a70fa5a65d4f65902564b5e2fd5fdf9c0e04b853ef3112"
TRAIN_TIMES = (0.0, 12.0, 24.0, 36.0)
VALIDATION_TIMES = (48.0, 60.0, 72.0)


def _summarize(comparison: pd.DataFrame) -> list[dict]:
    summary = residual_summary(comparison)
    return summary.to_dict(orient="records")


def _template_from_observed_start(observations: pd.DataFrame) -> tuple[CellCulture, dict]:
    """Use declared t=0 observations as the replay start, never an unrelated default."""

    start = observations.loc[observations["time_h"] == 0.0]
    if len(start) != 1:
        raise ValueError("案例要求恰好一个 0 h 初始观测点，以核对拟合起点。")
    row = start.iloc[0]
    if pd.isna(row["viable_cells"]) or pd.isna(row["glucose_mM"]):
        raise ValueError("0 h 观测必须包含活细胞数和葡萄糖，不能用模型默认值填补。")
    viable = float(row["viable_cells"])
    if viable <= 0:
        raise ValueError("0 h 活细胞数必须大于 0，才能从该起点重演培养动力学。")
    template = CellCulture("a549", viable_cells=viable)
    template.glucose_mm = float(row["glucose_mM"])
    initial = {"time_h": 0.0, "viable_cells": viable, "glucose_mM": template.glucose_mm}
    if "lactate_mM" in observations and pd.notna(row["lactate_mM"]):
        template.lactate_mm = float(row["lactate_mM"])
        initial["lactate_mM"] = template.lactate_mm
    return template, initial


def run_case(data_path: Path = DEFAULT_DATA, output_dir: Path | None = None) -> dict:
    """拟合训练点并对留出点报告误差，返回 JSON 可序列化结果。"""

    contents = data_path.read_bytes()
    fingerprint = measurement_fingerprint(contents)
    bundled_example = data_path.resolve() == DEFAULT_DATA.resolve()
    if bundled_example and fingerprint != EXPECTED_TEACHING_SHA256:
        raise ValueError("仓库教学合成 CSV 与记录的内容指纹不一致；请恢复原始示例后复跑。")
    observations, _ = standardize_measurements(contents)
    quality = quality_report(observations)
    if quality["blocked"]:
        raise ValueError(f"输入 CSV 不满足最低建模条件：{quality['blocked'][0][0]}。")
    if observations.attrs.get("duplicate_time_count", 0):
        raise ValueError("输入 CSV 含重复时间点；请在原始记录中核对并显式制作无歧义副本。")
    required = {"time_h", "viable_cells", "glucose_mM"}
    missing = required.difference(observations.columns)
    if missing:
        raise ValueError(f"示例数据缺少列：{', '.join(sorted(missing))}")
    training = observations[observations["time_h"].isin(TRAIN_TIMES)].copy()
    validation = observations[observations["time_h"].isin(VALIDATION_TIMES)].copy()
    if len(training) != len(TRAIN_TIMES) or len(validation) != len(VALIDATION_TIMES):
        raise ValueError("训练/验证时间点不完整；请使用未修改的教学数据文件。")

    template, initial_conditions = _template_from_observed_start(observations)
    initial_history = [template.snapshot()]
    fitted = fit_growth_and_uptake(template, initial_history, training)
    _, predicted_history = replay_from_initial(
        template,
        initial_history[0],
        observations["time_h"],
        fitted.growth_scale,
        fitted.uptake_scale,
    )
    prediction = pd.DataFrame(predicted_history)
    train_comparison = comparison_frame(prediction, training)
    validation_comparison = comparison_frame(prediction, validation)
    result = {
        "model_version": MODEL_VERSION,
        "case": "A549 teaching synthetic holdout validation" if bundled_example else "A549 user-supplied temporal holdout assessment",
        "data_kind": "teaching_synthetic_not_experimental" if bundled_example else "user_supplied_unverified",
        "data_source": "data/a549_teaching_synthetic.csv" if bundled_example else "user-supplied CSV (path withheld)",
        "data_file_sha256": fingerprint,
        "quality_warnings": [issue for issue, _ in quality["warnings"]],
        "initial_conditions": {"source": "observed 0 h (unverified for user files)", **initial_conditions},
        "training_time_h": list(TRAIN_TIMES),
        "validation_time_h": list(VALIDATION_TIMES),
        "fitted_parameters": {
            "growth_scale": fitted.growth_scale,
            "uptake_scale": fitted.uptake_scale,
            "training_normalized_rmse": fitted.normalized_rmse,
        },
        "training_metrics": _summarize(train_comparison),
        "validation_metrics": _summarize(validation_comparison),
        "limitation": (
            "该案例仅验证软件流程，不构成真实 A549 培养动力学的外部或独立验证。"
            if bundled_example else
            "用户数据来源未由本脚本核验；同序列时间留出不构成独立批次验证，不能据此做定量实验或临床结论。"
        ),
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(result["training_metrics"]).to_csv(output_dir / "training_metrics.csv", index=False)
        pd.DataFrame(result["validation_metrics"]).to_csv(output_dir / "validation_metrics.csv", index=False)
        train_comparison.to_csv(output_dir / "training_comparison.csv", index=False)
        validation_comparison.to_csv(output_dir / "validation_comparison.csv", index=False)
        (output_dir / "summary.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        figure, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
        # 图中使用 ASCII 标签，避免最小化 CI 环境缺少中文字体而生成空白字形。
        series = (("viable_cells", "Viable cells (cells)"), ("glucose_mM", "Glucose (mM)"))
        source_label = "synthetic" if bundled_example else "user-supplied, unverified"
        for axis, (field, label) in zip(axes, series):
            axis.plot(prediction["time_h"], prediction[field], color="#2878b5", label="Fitted model")
            axis.scatter(training["time_h"], training[field], color="#3b9a6d", marker="o", label=f"Training ({source_label})")
            axis.scatter(validation["time_h"], validation[field], color="#e78b33", marker="s", label=f"Holdout ({source_label})")
            axis.set_xlabel("Time (h)")
            axis.set_ylabel(label)
            axis.grid(alpha=0.25)
            axis.legend(fontsize=8)
        figure.suptitle(
            "A549 teaching synthetic data: train / holdout (not experimental)"
            if bundled_example else "A549 user-supplied data: temporal holdout (source unverified)"
        )
        figure.savefig(output_dir / "a549_training_holdout.png", dpi=160)
        plt.close(figure)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 e-cell A549 教学合成留出验证案例")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir
    if output_dir is None:
        if args.data.resolve() != DEFAULT_DATA.resolve():
            parser.error("自定义 CSV 必须显式指定 --output-dir；请将未获公开授权的数据结果保存在仓库外。")
        output_dir = ROOT / "assets" / "validation" / "a549_teaching_case"
    result = run_case(args.data, output_dir)
    print(pd.DataFrame(result["training_metrics"]).to_string(index=False))
    print(pd.DataFrame(result["validation_metrics"]).to_string(index=False))
    print(f"fitted growth_scale={result['fitted_parameters']['growth_scale']}, uptake_scale={result['fitted_parameters']['uptake_scale']}")
    print(f"outputs: {output_dir}")


if __name__ == "__main__":
    main()

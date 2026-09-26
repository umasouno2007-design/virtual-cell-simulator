"""运行 A549 教学合成数据的留出验证案例。

这不是独立生物学验证：数据是公开分发的教学合成数据，用于验证 e-cell 的
CSV 对齐、透明两参数粗校准、误差汇总与可视化流程可以重复运行。
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calibration import fit_growth_and_uptake, replay_from_initial
from cell import CellCulture
from experiment_data import comparison_frame, residual_summary


DEFAULT_DATA = ROOT / "data" / "a549_teaching_synthetic.csv"
TRAIN_TIMES = (0.0, 12.0, 24.0, 36.0)
VALIDATION_TIMES = (48.0, 60.0, 72.0)


def _summarize(comparison: pd.DataFrame) -> list[dict]:
    summary = residual_summary(comparison)
    return summary.to_dict(orient="records")


def run_case(data_path: Path = DEFAULT_DATA, output_dir: Path | None = None) -> dict:
    """拟合训练点并对留出点报告误差，返回 JSON 可序列化结果。"""

    observations = pd.read_csv(data_path).sort_values("time_h").reset_index(drop=True)
    required = {"time_h", "viable_cells", "glucose_mM"}
    missing = required.difference(observations.columns)
    if missing:
        raise ValueError(f"示例数据缺少列：{', '.join(sorted(missing))}")
    training = observations[observations["time_h"].isin(TRAIN_TIMES)].copy()
    validation = observations[observations["time_h"].isin(VALIDATION_TIMES)].copy()
    if len(training) != len(TRAIN_TIMES) or len(validation) != len(VALIDATION_TIMES):
        raise ValueError("训练/验证时间点不完整；请使用未修改的教学数据文件。")

    template = CellCulture("a549")
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
        "case": "A549 teaching synthetic holdout validation",
        "data_kind": "teaching_synthetic_not_experimental",
        "data_source": str(data_path.relative_to(ROOT)) if data_path.is_relative_to(ROOT) else str(data_path),
        "training_time_h": list(TRAIN_TIMES),
        "validation_time_h": list(VALIDATION_TIMES),
        "fitted_parameters": {
            "growth_scale": fitted.growth_scale,
            "uptake_scale": fitted.uptake_scale,
            "training_normalized_rmse": fitted.normalized_rmse,
        },
        "training_metrics": _summarize(train_comparison),
        "validation_metrics": _summarize(validation_comparison),
        "limitation": "该案例仅验证软件流程，不构成真实 A549 培养动力学的外部或独立验证。",
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(result["training_metrics"]).to_csv(output_dir / "training_metrics.csv", index=False)
        pd.DataFrame(result["validation_metrics"]).to_csv(output_dir / "validation_metrics.csv", index=False)
        train_comparison.to_csv(output_dir / "training_comparison.csv", index=False)
        validation_comparison.to_csv(output_dir / "validation_comparison.csv", index=False)
        pd.Series(result).to_json(output_dir / "summary.json", force_ascii=False, indent=2)
        figure, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
        # 图中使用 ASCII 标签，避免最小化 CI 环境缺少中文字体而生成空白字形。
        series = (("viable_cells", "Viable cells (cells)"), ("glucose_mM", "Glucose (mM)"))
        for axis, (field, label) in zip(axes, series):
            axis.plot(prediction["time_h"], prediction[field], color="#2878b5", label="Fitted model")
            axis.scatter(training["time_h"], training[field], color="#3b9a6d", marker="o", label="Training (synthetic)")
            axis.scatter(validation["time_h"], validation[field], color="#e78b33", marker="s", label="Holdout (synthetic)")
            axis.set_xlabel("Time (h)")
            axis.set_ylabel(label)
            axis.grid(alpha=0.25)
            axis.legend(fontsize=8)
        figure.suptitle("A549 teaching synthetic data: train / holdout (not experimental)")
        figure.savefig(output_dir / "a549_training_holdout.png", dpi=160)
        plt.close(figure)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 e-cell A549 教学合成留出验证案例")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "assets" / "validation" / "a549_teaching_case")
    args = parser.parse_args()
    result = run_case(args.data, args.output_dir)
    print(pd.DataFrame(result["training_metrics"]).to_string(index=False))
    print(pd.DataFrame(result["validation_metrics"]).to_string(index=False))
    print(f"fitted growth_scale={result['fitted_parameters']['growth_scale']}, uptake_scale={result['fitted_parameters']['uptake_scale']}")
    print(f"outputs: {args.output_dir}")


if __name__ == "__main__":
    main()

"""实测培养数据的导入、标准化与模拟对比。

本模块只处理数据对齐和误差计算，不对模型参数做隐式修改。这样上传的数据、
列映射和残差可以被审阅，后续参数拟合也能复用同一套输入。
"""

from io import BytesIO
from typing import Iterable

import pandas as pd


FIELD_LABELS = {
    "time_h": "时间（h）",
    "viable_cells": "活细胞数",
    "viability_percent": "存活率（%）",
    "glucose_mM": "葡萄糖（mM）",
    "lactate_mM": "乳酸（mM）",
    "pH": "pH",
    "oxygen_percent": "氧（%）",
}

_ALIASES = {
    "time_h": ("time_h", "time", "hour", "hours", "h", "时间", "时间h", "时间（h）", "时间(h)"),
    "viable_cells": ("viable_cells", "viable cell count", "live_cells", "cell_count", "活细胞数", "活细胞", "细胞数"),
    "viability_percent": ("viability_percent", "viability", "存活率", "存活率%", "存活率（%）"),
    "glucose_mM": ("glucose_mm", "glucose", "葡萄糖", "葡萄糖mm", "葡萄糖（mm）", "葡萄糖（mmol/l）"),
    "lactate_mM": ("lactate_mm", "lactate", "乳酸", "乳酸mm", "乳酸（mm）", "乳酸（mmol/l）"),
    "pH": ("ph",),
    "oxygen_percent": ("oxygen_percent", "oxygen", "do", "dissolved oxygen", "氧", "溶氧", "溶氧%", "氧（%）"),
}


def _normalized_header(value: object) -> str:
    return str(value).strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _read_csv(contents: bytes) -> pd.DataFrame:
    """支持常见 UTF-8 与 Windows 中文 CSV 编码。"""

    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return pd.read_csv(BytesIO(contents), encoding=encoding)
        except UnicodeDecodeError as error:
            last_error = error
    raise ValueError("CSV 编码无法识别；请保存为 UTF-8 或 GB18030 后重试。") from last_error


def standardize_measurements(contents: bytes) -> tuple[pd.DataFrame, list[str]]:
    """读取 CSV 并转为项目标准列名。至少需要时间列。"""

    raw = _read_csv(contents)
    if raw.empty:
        raise ValueError("CSV 不含数据行。")
    headers = {_normalized_header(column): column for column in raw.columns}
    mapped: dict[str, object] = {}
    for target, aliases in _ALIASES.items():
        source = next((headers.get(_normalized_header(alias)) for alias in aliases if _normalized_header(alias) in headers), None)
        if source is not None:
            mapped[target] = source
    if "time_h" not in mapped:
        raise ValueError("未找到时间列。请使用 time_h、time、hour 或“时间”。")
    data = pd.DataFrame({target: pd.to_numeric(raw[source], errors="coerce") for target, source in mapped.items()})
    data = data.dropna(subset=["time_h"]).sort_values("time_h")
    duplicate_time_count = int(data["time_h"].duplicated(keep=False).sum())
    data = data.drop_duplicates("time_h", keep="last")
    if data.empty:
        raise ValueError("时间列没有可用的数值。")
    numeric_fields = [column for column in data.columns if column != "time_h"]
    data = data.dropna(axis=1, how="all")
    recognized = "、".join(FIELD_LABELS[field] for field in numeric_fields if field in data.columns)
    notes = [f"已识别 {len(data)} 个时间点。"]
    if duplicate_time_count:
        notes.append(f"检测到 {duplicate_time_count} 行重复时间；标准化副本保留每个时间的最后一行，原始文件未被修改。")
    notes.append(f"已识别测量指标：{recognized}" if recognized else "只识别到时间列，暂无可比较的测量指标。")
    ignored = [str(column) for column in raw.columns if column not in mapped.values()]
    if ignored:
        notes.append(f"未用于比较的列：{'、'.join(ignored)}。")
    data = data.reset_index(drop=True)
    data.attrs["duplicate_time_count"] = duplicate_time_count
    return data, notes


def comparison_frame(simulation: pd.DataFrame, measurements: pd.DataFrame) -> pd.DataFrame:
    """将模拟历史线性插值到每个实测时间点，并计算逐点残差。"""

    if "time_h" not in simulation or "time_h" not in measurements:
        raise ValueError("模拟和实测数据都必须包含 time_h。")
    simulation = simulation.sort_values("time_h").drop_duplicates("time_h", keep="last")
    result = measurements[["time_h"]].copy()
    for field in (field for field in FIELD_LABELS if field != "time_h"):
        if field not in measurements or field not in simulation:
            continue
        model = simulation.set_index("time_h")[field].dropna().sort_index()
        target_time = measurements["time_h"]
        combined_index = model.index.union(target_time).sort_values()
        interpolated = model.reindex(combined_index).interpolate(method="index", limit_area="inside")
        result[f"{field}_observed"] = measurements[field].to_numpy()
        result[f"{field}_simulated"] = interpolated.reindex(target_time).to_numpy()
        result[f"{field}_residual"] = result[f"{field}_simulated"] - result[f"{field}_observed"]
    return result


def residual_summary(comparison: pd.DataFrame) -> pd.DataFrame:
    """按变量汇总可审阅的样本数、MAE 与 RMSE。"""

    rows = []
    for field, label in FIELD_LABELS.items():
        residual_column = f"{field}_residual"
        if residual_column not in comparison:
            continue
        residual = pd.to_numeric(comparison[residual_column], errors="coerce").dropna()
        if not residual.empty:
            rows.append({"指标": label, "可比较点数": len(residual), "MAE": abs(residual).mean(), "RMSE": (residual.pow(2).mean()) ** 0.5})
    return pd.DataFrame(rows)


def observed_fields(data: pd.DataFrame) -> Iterable[str]:
    """返回可与模拟历史叠加的标准指标列。"""

    return (field for field in FIELD_LABELS if field != "time_h" and field in data.columns)

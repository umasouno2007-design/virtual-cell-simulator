"""实测 CSV 的最低建模条件检查；不认证实验质量。"""

from datetime import datetime, timezone
from math import isfinite
import pandas as pd

from experiment_data import FIELD_LABELS
from version import MODEL_VERSION


def quality_report(data: pd.DataFrame) -> dict:
    """返回阻止/警告/通过项；输入为已标准化且单位已声明的 DataFrame。"""
    blocked, warnings, passed = [], [], []
    if "time_h" not in data or data.empty:
        blocked.append(("缺少可用时间列", "提供至少两个数值 time_h 时间点。"))
    else:
        invalid_source_times = int(data.attrs.get("invalid_time_count", 0))
        if invalid_source_times:
            blocked.append((
                f"原始 CSV 有 {invalid_source_times} 行时间缺失或无法解析",
                "修正原始文件的时间列后重新导入；标准化副本不会用于对齐或校准。",
            ))
        nonmonotonic_source_times = max(
            int(data.attrs.get("nonmonotonic_time_count", 0)),
            int(pd.to_numeric(data["time_h"], errors="coerce").diff().lt(0).sum()),
        )
        if nonmonotonic_source_times:
            warnings.append((
                f"原始 CSV 有 {nonmonotonic_source_times} 处时间倒序",
                "核对采样记录；标准化副本已按时间排序，不会改写原文件。",
            ))
        time = pd.to_numeric(data["time_h"], errors="coerce")
        finite_time = time.map(lambda value: isfinite(float(value)) if pd.notna(value) else False)
        if time.isna().any() or not finite_time.all() or (time < 0).any():
            blocked.append(("时间包含缺失、非有限或负值", "使用从实验起点开始的有限、非负小时数；不要用 Inf 表示未测量。"))
        elif len(time) and float(time.min()) > 0:
            warnings.append((
                "缺少记录的实验起始时间点",
                "确认模拟起点与实测时间原点一致；没有 0 h 观测时，初始条件无法由该 CSV 单独核对。",
            ))
        duplicate_count = int(data.attrs.get("duplicate_time_count", 0))
        if time.duplicated().any() or duplicate_count:
            warnings.append(("存在重复时间点", "保留原始记录；用于比较的标准化副本会采用同时间的最后一行。"))
        if len(data) < 3: warnings.append(("时间点少于 3", "可比较但不足以支持训练/留出划分。"))
        else: passed.append(("时间点数量", "至少有 3 个时间点。"))
    checked_fields = ("viable_cells", "viability_percent", "glucose_mM", "lactate_mM", "oxygen_percent", "pH")
    for field in checked_fields:
        if field not in data:
            continue
        values = pd.to_numeric(data[field], errors="coerce")
        finite_values = values.map(lambda value: isfinite(float(value)) if pd.notna(value) else True)
        if not finite_values.all():
            blocked.append((f"{FIELD_LABELS[field]}包含无穷值", "仅保留有限测量值；未测量值使用空单元格并在实验记录中说明。"))
        if (values.dropna() < 0).any():
            blocked.append((f"{FIELD_LABELS[field]}含负值", "核对单位或将缺失/失败测量留空。"))
        missing_count = int(values.isna().sum())
        if missing_count:
            warnings.append((f"{FIELD_LABELS[field]}存在缺失值（{missing_count} 个）", "确认空值确为未测量；不要用 0 或 Inf 代替缺失。"))
    if "viability_percent" in data and (pd.to_numeric(data["viability_percent"], errors="coerce").dropna() > 100).any():
        blocked.append(("存活率超过 100%", "请确认使用百分比而非比例，并核对导入单位。"))
    if "oxygen_percent" in data and (pd.to_numeric(data["oxygen_percent"], errors="coerce").dropna() > 100).any():
        blocked.append(("氧百分比超过 100%", "核对该列是否实际使用饱和度、分压或其他单位。"))
    if "pH" in data and (pd.to_numeric(data["pH"], errors="coerce").dropna() > 14).any():
        blocked.append(("pH 超出 0–14 的常规标度", "核对 CSV 中的酸碱指标单位与列映射。"))
    available = [field for field in ("viable_cells", "glucose_mM", "lactate_mM") if field in data and data[field].notna().sum() >= 2]
    if not available: blocked.append(("缺少可校准指标", "至少提供活细胞数、葡萄糖或乳酸中的一个，且有两个时间点。"))
    else: passed.append(("可校准指标", "、".join(FIELD_LABELS[f] for f in available)))
    if len(data) < 5: warnings.append(("没有充足留出点", "建议预先保留后段或独立批次用于验证；否则只能报告拟合误差。"))
    return {"model_version": MODEL_VERSION, "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "blocked": blocked, "warnings": warnings, "passed": passed, "is_minimum_model_ready": not blocked, "disclaimer": "通过仅代表格式和最低建模条件，不代表实验质量认证或生物学结论有效。"}

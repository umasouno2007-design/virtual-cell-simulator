"""实测 CSV 的最低建模条件检查；不认证实验质量。"""

from datetime import datetime, timezone
import pandas as pd

from experiment_data import FIELD_LABELS
from version import MODEL_VERSION


def quality_report(data: pd.DataFrame) -> dict:
    """返回阻止/警告/通过项；输入为已标准化且单位已声明的 DataFrame。"""
    blocked, warnings, passed = [], [], []
    if "time_h" not in data or data.empty:
        blocked.append(("缺少可用时间列", "提供至少两个数值 time_h 时间点。"))
    else:
        time = pd.to_numeric(data["time_h"], errors="coerce")
        if time.isna().any() or (time < 0).any(): blocked.append(("时间包含缺失或负值", "使用从实验起点开始的非负小时数。"))
        duplicate_count = int(data.attrs.get("duplicate_time_count", 0))
        if time.duplicated().any() or duplicate_count:
            warnings.append(("存在重复时间点", "保留原始记录；用于比较的标准化副本会采用同时间的最后一行。"))
        if len(data) < 3: warnings.append(("时间点少于 3", "可比较但不足以支持训练/留出划分。"))
        else: passed.append(("时间点数量", "至少有 3 个时间点。"))
    for field in ("viable_cells", "viability_percent", "glucose_mM", "lactate_mM", "oxygen_percent"):
        if field in data and (pd.to_numeric(data[field], errors="coerce").dropna() < 0).any():
            blocked.append((f"{FIELD_LABELS[field]}含负值", "核对单位或将缺失/失败测量留空。"))
    if "viability_percent" in data and (pd.to_numeric(data["viability_percent"], errors="coerce").dropna() > 100).any():
        blocked.append(("存活率超过 100%", "请确认使用百分比而非比例，并核对导入单位。"))
    available = [field for field in ("viable_cells", "glucose_mM", "lactate_mM") if field in data and data[field].notna().sum() >= 2]
    if not available: blocked.append(("缺少可校准指标", "至少提供活细胞数、葡萄糖或乳酸中的一个，且有两个时间点。"))
    else: passed.append(("可校准指标", "、".join(FIELD_LABELS[f] for f in available)))
    if len(data) < 5: warnings.append(("没有充足留出点", "建议预先保留后段或独立批次用于验证；否则只能报告拟合误差。"))
    return {"model_version": MODEL_VERSION, "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "blocked": blocked, "warnings": warnings, "passed": passed, "is_minimum_model_ready": not blocked, "disclaimer": "通过仅代表格式和最低建模条件，不代表实验质量认证或生物学结论有效。"}

"""实测 CSV 的最低建模条件检查；不认证实验质量。"""

from datetime import datetime, timezone
from math import isfinite
import pandas as pd

from experiment_data import FIELD_LABELS, MAX_CSV_ROWS, MODEL_STATE_BOUNDS
from numeric_utils import is_boolean_scalar
from version import MODEL_VERSION


def numeric_series(values: pd.Series) -> pd.Series:
    """将序列转换为数值；float64 不可表示的整数保留为正/负无穷标记。"""

    if not isinstance(values, pd.Series):
        raise ValueError("数值转换需要单列 Pandas Series。")
    try:
        return pd.to_numeric(values, errors="coerce")
    except (OverflowError, TypeError, ValueError):
        def convert(value):
            try:
                missing = pd.isna(value)
            except (TypeError, ValueError):
                missing = False
            if isinstance(missing, bool) and missing:
                return float("nan")
            if is_boolean_scalar(missing) and bool(missing):
                return float("nan")
            try:
                return float(value)
            except OverflowError:
                try:
                    return float("-inf") if value < 0 else float("inf")
                except (TypeError, ValueError):
                    return float("nan")
            except (TypeError, ValueError):
                return float("nan")

        return pd.Series([convert(value) for value in values], index=values.index, dtype=float)


def quality_report(data: pd.DataFrame) -> dict:
    """返回阻止/警告/通过项；输入为已标准化且单位已声明的 DataFrame。"""
    if not isinstance(data, pd.DataFrame):
        raise ValueError("数据质量检查需要已标准化的 Pandas 表格。")
    if len(data) > MAX_CSV_ROWS:
        return {
            "model_version": MODEL_VERSION,
            "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "blocked": [(
                f"数据行数超过当前解析上限 {MAX_CSV_ROWS:,}",
                "请保留原始文件，并另存包含本次分析所需时间点的副本；原始数据不会被修改。",
            )],
            "warnings": [],
            "passed": [],
            "is_minimum_model_ready": False,
            "disclaimer": "通过仅代表格式和最低建模条件，不代表实验质量认证或生物学结论有效。",
        }
    blocked, warnings, passed = [], [], []
    invalid_metadata = False

    def source_count(name: str) -> int:
        nonlocal invalid_metadata
        value = data.attrs.get(name, 0)
        if type(value) is int and value >= 0:
            return value
        invalid_metadata = True
        return 0

    if "time_h" not in data or data.empty:
        blocked.append(("缺少可用时间列", "提供至少两个数值 time_h 时间点。"))
    else:
        time_is_boolean = data["time_h"].map(is_boolean_scalar)
        if time_is_boolean.any():
            blocked.append(("时间列包含布尔值", "时间必须是以小时表示的数值；True/False 不能作为 0/1 小时使用。"))
        invalid_source_times = source_count("invalid_time_count")
        if invalid_source_times:
            blocked.append((
                f"原始 CSV 有 {invalid_source_times} 行时间缺失或无法解析",
                "修正原始文件的时间列后重新导入；标准化副本不会用于对齐或校准。",
            ))
        nonmonotonic_source_times = max(
            source_count("nonmonotonic_time_count"),
            int(numeric_series(data["time_h"]).diff().lt(0).sum()),
        )
        if nonmonotonic_source_times:
            warnings.append((
                f"原始 CSV 有 {nonmonotonic_source_times} 处时间倒序",
                "核对采样记录；标准化副本已按时间排序，不会改写原文件。",
            ))
        time = numeric_series(data["time_h"])
        finite_time = time.map(lambda value: isfinite(float(value)) if pd.notna(value) else False)
        if time.isna().any() or not finite_time.all() or (time < 0).any():
            blocked.append(("时间包含缺失、非有限或负值", "使用从实验起点开始的有限、非负小时数；不要用 Inf 表示未测量。"))
        elif len(time) and float(time.min()) > 0:
            warnings.append((
                "缺少记录的实验起始时间点",
                "确认模拟起点与实测时间原点一致；没有 0 h 观测时，初始条件无法由该 CSV 单独核对。",
            ))
        duplicate_count = source_count("duplicate_time_count")
        if time.duplicated().any() or duplicate_count:
            warnings.append(("存在重复时间点", "保留原始记录；用于比较的标准化副本会采用同时间的最后一行。"))
        if len(data) < 3: warnings.append(("时间点少于 3", "可比较但不足以支持训练/留出划分。"))
        else: passed.append(("时间点数量", "至少有 3 个时间点。"))
    checked_fields = ("viable_cells", "viability_percent", "glucose_mM", "lactate_mM", "oxygen_percent", "pH")
    invalid_numeric_counts = data.attrs.get("invalid_numeric_counts", {})
    if not isinstance(invalid_numeric_counts, dict):
        invalid_numeric_counts = {}
        invalid_metadata = True
    elif any(
        field not in FIELD_LABELS
        or type(count) is not int or count < 0
        for field, count in invalid_numeric_counts.items()
    ):
        invalid_numeric_counts = {}
        invalid_metadata = True
    explicit_missing_tokens = {"", "na", "n/a", "null", "nan", "none"}
    boolean_fields: set[str] = set()
    for field in checked_fields:
        if field not in data:
            continue
        raw_values = data[field]
        boolean_values = raw_values.map(is_boolean_scalar)
        if boolean_values.any():
            boolean_fields.add(field)
            blocked.append((
                f"{FIELD_LABELS[field]}包含布尔值",
                "测量指标必须使用带正确单位的数值；True/False 不会作为 0/1 测量值接受。",
            ))
        values = numeric_series(raw_values)
        explicit_missing = raw_values.map(
            lambda value: isinstance(value, str)
            and value.strip().lower() in explicit_missing_tokens
        )
        direct_invalid = raw_values.notna() & values.isna() & ~explicit_missing
        invalid_count = max(invalid_numeric_counts.get(field, 0), int(direct_invalid.sum()))
        if invalid_count:
            blocked.append((
                f"{FIELD_LABELS[field]}有 {invalid_count} 个非空值无法解析为数值",
                "核对原始 CSV 的数字格式与单位；真正未测量的单元格请留空或使用 NA。",
            ))
        finite_values = values.map(lambda value: isfinite(float(value)) if pd.notna(value) else True)
        if not finite_values.all():
            blocked.append((f"{FIELD_LABELS[field]}包含无穷值", "仅保留有限测量值；未测量值使用空单元格并在实验记录中说明。"))
        if (values.dropna() < 0).any():
            blocked.append((f"{FIELD_LABELS[field]}含负值", "核对单位或将缺失/失败测量留空。"))
        missing_count = int(values.isna().sum())
        if missing_count:
            warnings.append((f"{FIELD_LABELS[field]}存在缺失值（{missing_count} 个）", "确认空值确为未测量；不要用 0 或 Inf 代替缺失。"))
    viability_upper = MODEL_STATE_BOUNDS["viability_percent"][1]
    oxygen_upper = MODEL_STATE_BOUNDS["oxygen_percent"][1]
    ph_lower, ph_upper = MODEL_STATE_BOUNDS["pH"]
    if "viability_percent" in data and (numeric_series(data["viability_percent"]).dropna() > viability_upper).any():
        blocked.append(("存活率超过 100%", "请确认使用百分比而非比例，并核对导入单位。"))
    if "oxygen_percent" in data and (numeric_series(data["oxygen_percent"]).dropna() > 100).any():
        blocked.append(("氧百分比超过 100%", "核对该列是否实际使用饱和度、分压或其他单位。"))
    elif "oxygen_percent" in data and (numeric_series(data["oxygen_percent"]).dropna() > oxygen_upper).any():
        blocked.append((
            "氧代理值超过模型 0–21% 范围",
            "本列对应培养模型的局部氧可用性代理；溶氧饱和度 %、分压或培养箱设定值不能直接当作相同观测量。请核对来源与换算依据。",
        ))
    if "oxygen_percent" in data and data["oxygen_percent"].notna().any():
        warnings.append((
            "氧列需要单独核对测量定义",
            "即使在 0–21% 范围内，模型氧代理也不自动等同于实测溶氧、氧分压或培养箱头空间氧。",
        ))
    if "pH" in data:
        observed_ph = numeric_series(data["pH"]).dropna()
        if (observed_ph > 14).any():
            blocked.append(("pH 超出 0–14 的常规标度", "核对 CSV 中的酸碱指标单位与列映射。"))
        elif ((observed_ph < ph_lower) | (observed_ph > ph_upper)).any():
            blocked.append((
                "pH 超出当前培养模型 6.2–8.0 的状态范围",
                "该测量可能有效，但现有模型会在范围边界裁剪 pH；请核对单位，并避免将此区间外数据用于当前模型对齐或校准。",
            ))
    if invalid_metadata:
        blocked.append((
            "导入质量元数据无效",
            "CSV 导入附带的原始解析计数格式不正确；请从原始文件重新导入，以免遗漏无法解析的行。",
        ))
    available = [
        field for field in ("viable_cells", "glucose_mM", "lactate_mM")
        if field in data and field not in boolean_fields
        and numeric_series(data[field]).notna().sum() >= 2
    ]
    if not available: blocked.append(("缺少可校准指标", "至少提供活细胞数、葡萄糖或乳酸中的一个，且有两个时间点。"))
    else: passed.append(("可校准指标", "、".join(FIELD_LABELS[f] for f in available)))
    if len(data) < 5: warnings.append(("没有充足留出点", "建议预先保留后段或独立批次用于验证；否则只能报告拟合误差。"))
    return {"model_version": MODEL_VERSION, "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "blocked": blocked, "warnings": warnings, "passed": passed, "is_minimum_model_ready": not blocked, "disclaimer": "通过仅代表格式和最低建模条件，不代表实验质量认证或生物学结论有效。"}

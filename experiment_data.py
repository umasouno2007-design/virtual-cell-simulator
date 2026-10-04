"""实测培养数据的导入、标准化与模拟对比。

本模块只处理数据对齐和误差计算，不对模型参数做隐式修改。这样上传的数据、
列映射和残差可以被审阅，后续参数拟合也能复用同一套输入。
"""

from hashlib import sha256
from io import BytesIO
from math import fsum, hypot, isfinite, sqrt
import re
from sys import float_info
import warnings
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
    # 泛称“溶氧/DO”可能表示饱和度、分压或质量浓度，不能自动映射成模型氧代理。
    "oxygen_percent": ("oxygen_percent", "局部氧可用性代理", "局部氧代理"),
}

# 交互式原型的解析资源边界，不是实验时间点或数据质量的科学标准。
MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_CSV_ROWS = 5_000


def measurement_fingerprint(contents: bytes) -> str:
    """Return a stable SHA-256 identity for uploaded CSV bytes (not a privacy/security token)."""

    return sha256(contents).hexdigest()


def _normalized_header(value: object) -> str:
    return str(value).strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _read_csv(contents: bytes) -> pd.DataFrame:
    """支持常见 UTF-8 与 Windows 中文 CSV 编码。"""

    if not isinstance(contents, (bytes, bytearray)):
        raise ValueError("CSV 文件内容无效；请重新选择 CSV 文件后重试。")
    if len(contents) > MAX_CSV_BYTES:
        raise ValueError("CSV 超过当前在线原型的 5 MiB 解析上限；请保留原始文件并上传所需时间序列副本。")
    contents = bytes(contents)
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            # 保留 NA 等原始文本，区分“明确缺测”与拼写/单位错误。
            # 禁止 pandas 在数据列多于表头时把首列隐式当作索引，
            # 否则未加引号的千位分隔符会悄悄错位时间与观测值。
            with warnings.catch_warnings():
                warnings.simplefilter("error", pd.errors.ParserWarning)
                return pd.read_csv(
                    BytesIO(contents), encoding=encoding, keep_default_na=False,
                    index_col=False, on_bad_lines="error",
                )
        except UnicodeDecodeError as error:
            last_error = error
        except pd.errors.EmptyDataError:
            raise ValueError("CSV 文件为空或缺少表头；请提供含列名和观测行的 CSV。") from None
        except pd.errors.ParserError:
            raise ValueError("CSV 表格结构无法解析；请检查表头、分隔符和引号配对。") from None
        except pd.errors.ParserWarning:
            raise ValueError("CSV 数据行列数与表头不一致；请检查未加引号的千位分隔符或多余逗号。") from None
    raise ValueError("CSV 编码无法识别；请保存为 UTF-8 或 GB18030 后重试。") from last_error


def standardize_measurements(contents: bytes) -> tuple[pd.DataFrame, list[str]]:
    """读取 CSV 并转为项目标准列名。至少需要时间列。"""

    raw = _read_csv(contents)
    if len(raw) > MAX_CSV_ROWS:
        raise ValueError(f"CSV 超过当前在线原型的 {MAX_CSV_ROWS:,} 行解析上限；请保留原始文件并筛选所需时间序列副本。")
    if raw.empty:
        raise ValueError("CSV 不含数据行。")
    headers: dict[str, list[object]] = {}
    recognized_aliases = {
        _normalized_header(alias) for aliases in _ALIASES.values() for alias in aliases
    }
    for column in raw.columns:
        headers.setdefault(_normalized_header(column), []).append(column)
        # pandas 会把完全同名的 CSV 表头改写为 name.1、name.2；
        # 它们仍是同一指标的歧义输入，不能当作普通未识别列忽略。
        mangled = re.fullmatch(r"(.+)\.\d+", str(column))
        if mangled and _normalized_header(mangled.group(1)) in recognized_aliases:
            headers.setdefault(_normalized_header(mangled.group(1)), []).append(column)
    mapped: dict[str, object] = {}
    for target, aliases in _ALIASES.items():
        candidates = list(dict.fromkeys(
            column for alias in aliases
            for column in headers.get(_normalized_header(alias), [])
        ))
        if len(candidates) > 1:
            raise ValueError(
                f"指标 {FIELD_LABELS[target]} 对应多个 CSV 列："
                f"{'、'.join(str(column) for column in candidates)}。"
                "请保留一列并核对单位后重新导入。"
            )
        if candidates:
            mapped[target] = candidates[0]
    if "time_h" not in mapped:
        raise ValueError("未找到时间列。请使用 time_h、time、hour 或“时间”。")
    missing_tokens = {"", "na", "n/a", "null", "nan", "none"}
    invalid_numeric_counts: dict[str, int] = {}
    numeric_columns: dict[str, pd.Series] = {}
    for target, source in mapped.items():
        values = raw[source]
        numeric = pd.to_numeric(values, errors="coerce")
        explicitly_missing = values.isna() | values.astype(str).str.strip().str.lower().isin(missing_tokens)
        invalid_numeric_counts[target] = int((~explicitly_missing & numeric.isna()).sum())
        numeric_columns[target] = numeric
    data = pd.DataFrame(numeric_columns)
    invalid_time_count = int(data["time_h"].isna().sum())
    nonmonotonic_time_count = int(data["time_h"].diff().lt(0).sum())
    # 稳定排序保留同一时间点在原文件中的先后顺序，后续 keep="last"
    # 才真正表示“保留原始 CSV 的最后一行”。
    data = data.dropna(subset=["time_h"]).sort_values("time_h", kind="stable")
    duplicate_time_count = int(data["time_h"].duplicated(keep=False).sum())
    data = data.drop_duplicates("time_h", keep="last")
    if data.empty:
        raise ValueError("时间列没有可用的数值。")
    numeric_fields = [column for column in data.columns if column != "time_h"]
    # 保留已识别但全空的观测列，使质量报告能明确提示整列缺失，
    # 而不是在标准化阶段悄悄抹掉该测量字段。
    recognized = "、".join(FIELD_LABELS[field] for field in numeric_fields if field in data.columns)
    notes = [f"已识别 {len(data)} 个时间点。"]
    if invalid_time_count:
        notes.append(f"原始 CSV 有 {invalid_time_count} 行时间缺失或无法解析；标准化副本未纳入这些行，质量检查会阻止用于对齐/校准。")
    for field, count in invalid_numeric_counts.items():
        if count and field != "time_h":
            notes.append(f"{FIELD_LABELS[field]}有 {count} 个非空值无法解析为数值；质量检查会阻止用于对齐/校准。")
    if nonmonotonic_time_count:
        notes.append(f"原始 CSV 有 {nonmonotonic_time_count} 处时间倒序；标准化副本按时间排序，请核对原始记录。")
    if duplicate_time_count:
        notes.append(f"检测到 {duplicate_time_count} 行重复时间；标准化副本保留每个时间的最后一行，原始文件未被修改。")
    notes.append(f"已识别测量指标：{recognized}" if recognized else "只识别到时间列，暂无可比较的测量指标。")
    ignored = [str(column) for column in raw.columns if column not in mapped.values()]
    if ignored:
        notes.append(f"未用于比较的列：{'、'.join(ignored)}。")
        oxygen_like = {"oxygen", "do", "dissolvedoxygen", "氧", "溶氧", "溶氧%", "氧（%）"}
        if any(_normalized_header(column) in oxygen_like for column in ignored):
            notes.append("泛称氧/DO/溶氧列未自动映射到模型氧代理；请核对测量定义与单位，只有具备对应依据时才使用 oxygen_percent 列。")
    data = data.reset_index(drop=True)
    data.attrs["duplicate_time_count"] = duplicate_time_count
    data.attrs["invalid_time_count"] = invalid_time_count
    data.attrs["nonmonotonic_time_count"] = nonmonotonic_time_count
    data.attrs["invalid_numeric_counts"] = invalid_numeric_counts
    return data, notes


def comparison_frame(simulation: pd.DataFrame, measurements: pd.DataFrame) -> pd.DataFrame:
    """将标准化数值历史插值到观测时间点；拒绝把布尔值当成数值数据。"""

    if not isinstance(simulation, pd.DataFrame) or not isinstance(measurements, pd.DataFrame):
        raise ValueError("模拟—实测对齐需要两个 Pandas 表格。")
    if "time_h" not in simulation or "time_h" not in measurements:
        raise ValueError("模拟和实测数据都必须包含 time_h。")
    for label, frame in (("模拟", simulation), ("实测", measurements)):
        for field in FIELD_LABELS:
            if field not in frame:
                continue
            contains_boolean = frame[field].map(
                lambda value: pd.api.types.is_bool_dtype(type(value)) if pd.notna(value) else False
            ).any()
            if contains_boolean:
                raise ValueError(f"{label}字段 {FIELD_LABELS[field]}包含布尔值；请使用正确单位的数值数据。")
    normalized_times: dict[str, pd.Series] = {}
    for label, frame in (("模拟", simulation), ("实测", measurements)):
        try:
            times = pd.to_numeric(frame["time_h"], errors="coerce")
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"{label}时间列必须是有限、非负的小时数。") from None
        if times.isna().any() or not times.map(lambda value: isfinite(float(value))).all() or (times < 0).any():
            raise ValueError(f"{label}时间列必须是有限、非负的小时数。")
        if label == "实测" and times.duplicated().any():
            raise ValueError("实测时间点重复；请先核对原始记录并显式生成标准化副本。")
        normalized_times[label] = times.astype(float)
    simulation = simulation.assign(time_h=normalized_times["模拟"])
    measurements = measurements.assign(time_h=normalized_times["实测"])
    # 同一模拟时刻可先后有干预前/后快照；稳定排序让 keep="last"
    # 确定地选择事件后的最后记录。
    simulation = simulation.sort_values("time_h", kind="stable").drop_duplicates("time_h", keep="last")
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

    if not isinstance(comparison, pd.DataFrame):
        raise ValueError("残差汇总需要模拟—实测对齐结果表格。")
    rows = []
    for field, label in FIELD_LABELS.items():
        residual_column = f"{field}_residual"
        if residual_column not in comparison:
            continue
        residual = pd.to_numeric(comparison[residual_column], errors="coerce").dropna()
        if not residual.empty:
            values = [float(value) for value in residual]
            if not all(isfinite(value) for value in values):
                raise ValueError(f"{label}残差包含非有限值，无法计算 MAE/RMSE。")
            count = len(values)
            maximum_absolute = max(abs(value) for value in values)
            if maximum_absolute <= sqrt(float_info.max / count):
                # Preserve historical floating-point results when the legacy
                # sum-of-squares path is provably within range.
                mae = abs(residual).mean()
                rmse = (residual.pow(2).mean()) ** 0.5
            else:
                mae = fsum(abs(value) / count for value in values)
                rmse = hypot(*values) / sqrt(count)
            rows.append({"指标": label, "可比较点数": count, "MAE": mae, "RMSE": rmse})
    return pd.DataFrame(rows)


def observed_fields(data: pd.DataFrame) -> Iterable[str]:
    """返回可与模拟历史叠加的标准指标列。"""

    return (field for field in FIELD_LABELS if field != "time_h" and field in data.columns)

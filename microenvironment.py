"""单细胞与微型细胞群共用的培养微环境输入。

数值描述培养条件或其局部可用性代理，不是细胞内浓度、空间成像读数或
真实微环境的 CFD/反应扩散求解结果。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite

from numeric_utils import checked_time_advance, is_boolean_scalar


def _bounded(value: float, low: float, high: float) -> float:
    try:
        numeric = float(value)
        return max(low, min(high, numeric)) if isfinite(numeric) else low
    except (TypeError, ValueError, OverflowError):
        return low


@dataclass
class MicroenvironmentState:
    """代表性细胞需要的最小环境输入，单位见字段名或注释。"""

    time_h: float = 0.0
    local_oxygen_availability: float = 1.0  # 0–1，相对可用性代理
    glucose_mm: float = 5.5
    glucose_reference_mm: float = 5.5  # 所选细胞系配置中的起始培养基葡萄糖参考值
    lactate_mm: float = 0.0  # 记录/传递环境值；当前单细胞相对状态方程不直接使用
    ph: float = 7.4
    temperature_c: float = 37.0
    drug_um: float = 0.0
    local_confluence_percent: float = 10.0
    doubling_time_h: float = 24.0
    drug_ic50_um: float = 10.0

    def normalized(self) -> "MicroenvironmentState":
        """原位裁剪此输入对象，供显式清洗配置时使用。"""

        numeric_fields = (
            "time_h", "local_oxygen_availability", "glucose_mm",
            "glucose_reference_mm", "lactate_mm", "ph", "temperature_c",
            "drug_um", "local_confluence_percent", "doubling_time_h",
            "drug_ic50_um",
        )
        if any(is_boolean_scalar(getattr(self, name)) for name in numeric_fields):
            raise ValueError("微环境数值不能使用布尔值代替；请提供带单位的数值。")

        try:
            time_h = float(self.time_h)
        except (TypeError, ValueError, OverflowError):
            time_h = 0.0
        self.time_h = max(0.0, time_h) if isfinite(time_h) else 0.0
        self.local_oxygen_availability = _bounded(self.local_oxygen_availability, 0.0, 1.0)
        self.glucose_mm = _bounded(self.glucose_mm, 0.0, 100.0)
        self.glucose_reference_mm = max(1e-6, _bounded(self.glucose_reference_mm, 1e-6, 100.0))
        self.lactate_mm = _bounded(self.lactate_mm, 0.0, 200.0)
        self.ph = _bounded(self.ph, 5.5, 9.0)
        self.temperature_c = _bounded(self.temperature_c, 0.0, 50.0)
        self.drug_um = _bounded(self.drug_um, 0.0, 1e6)
        self.local_confluence_percent = _bounded(self.local_confluence_percent, 0.0, 100.0)
        self.doubling_time_h = max(1.0, _bounded(self.doubling_time_h, 1.0, 500.0))
        self.drug_ic50_um = max(1e-6, _bounded(self.drug_ic50_um, 1e-6, 1e6))
        return self

    def normalized_copy(self) -> "MicroenvironmentState":
        """Return a cleaned copy without changing the caller's environment snapshot."""

        return replace(self).normalized()

    @classmethod
    def from_culture(cls, culture: object) -> "MicroenvironmentState":
        """从现有 ``CellCulture`` 派生同格式输入，保持培养模型不变。"""

        from cell import CellCulture

        if not isinstance(culture, CellCulture):
            raise ValueError("只能从有效的 CellCulture 对象派生微环境。")
        profile = getattr(culture, "profile")
        parameters = getattr(culture, "parameters")
        source_values = {
            "培养时钟": getattr(culture, "time_h"),
            "培养氧设定": getattr(culture, "oxygen_percent"),
            "葡萄糖": getattr(culture, "glucose_mm"),
            "乳酸": getattr(culture, "lactate_mm"),
            "pH": getattr(culture, "ph"),
            "温度": getattr(culture, "temperature_c"),
            "药物浓度": getattr(culture, "drug_um"),
            "细胞密度": getattr(culture, "viable_cells"),
            "汇合度": getattr(culture, "confluence_percent"),
            "参考葡萄糖": profile.initial_glucose_mm,
            "倍增时间": profile.doubling_time_h,
            "药物 IC50": parameters.drug_ic50_um,
        }
        invalid_booleans = [name for name, value in source_values.items() if is_boolean_scalar(value)]
        if invalid_booleans:
            raise ValueError(
                "无法从培养状态派生微环境；以下数值字段不能使用布尔值代替："
                + "、".join(invalid_booleans)
                + "。"
            )
        numeric_values: dict[str, float] = {}
        for name, value in source_values.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError, OverflowError):
                raise ValueError(f"无法从培养状态派生微环境；字段 {name} 不是有限数值。") from None
            if not isfinite(numeric):
                raise ValueError(f"无法从培养状态派生微环境；字段 {name} 不是有限数值。")
            numeric_values[name] = numeric
        return cls(
            time_h=numeric_values["培养时钟"],
            local_oxygen_availability=_bounded(numeric_values["培养氧设定"] / 18.6, 0.0, 1.0),
            glucose_mm=numeric_values["葡萄糖"],
            glucose_reference_mm=numeric_values["参考葡萄糖"],
            lactate_mm=numeric_values["乳酸"],
            ph=numeric_values["pH"],
            temperature_c=numeric_values["温度"],
            drug_um=numeric_values["药物浓度"],
            local_confluence_percent=numeric_values["汇合度"],
            doubling_time_h=numeric_values["倍增时间"],
            drug_ic50_um=numeric_values["药物 IC50"],
        ).normalized()

    def snapshot(self) -> dict[str, float]:
        return {
            "time_h": self.time_h,
            "local_oxygen_availability": self.local_oxygen_availability,
            "glucose_mM": self.glucose_mm,
            "glucose_reference_mM": self.glucose_reference_mm,
            "lactate_mM": self.lactate_mm,
            "pH": self.ph,
            "temperature_C": self.temperature_c,
            "drug_uM": self.drug_um,
            "local_confluence_percent": self.local_confluence_percent,
            "doubling_time_h": self.doubling_time_h,
            "drug_ic50_uM": self.drug_ic50_um,
        }

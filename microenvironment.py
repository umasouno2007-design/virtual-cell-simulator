"""单细胞与微型细胞群共用的培养微环境输入。

数值描述培养条件或其局部可用性代理，不是细胞内浓度、空间成像读数或
真实微环境的 CFD/反应扩散求解结果。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _bounded(value: float, low: float, high: float) -> float:
    try:
        numeric = float(value)
        return max(low, min(high, numeric)) if isfinite(numeric) else low
    except (TypeError, ValueError):
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
        """原位裁剪外部输入，防止单细胞状态传播 NaN 或无意义数值。"""

        try:
            time_h = float(self.time_h)
        except (TypeError, ValueError):
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

    @classmethod
    def from_culture(cls, culture: object) -> "MicroenvironmentState":
        """从现有 ``CellCulture`` 派生同格式输入，保持培养模型不变。"""

        profile = getattr(culture, "profile")
        parameters = getattr(culture, "parameters")
        return cls(
            time_h=getattr(culture, "time_h"),
            local_oxygen_availability=_bounded(getattr(culture, "oxygen_percent") / 18.6, 0.0, 1.0),
            glucose_mm=getattr(culture, "glucose_mm"),
            glucose_reference_mm=profile.initial_glucose_mm,
            lactate_mm=getattr(culture, "lactate_mm"),
            ph=getattr(culture, "ph"),
            temperature_c=getattr(culture, "temperature_c"),
            drug_um=getattr(culture, "drug_um"),
            local_confluence_percent=getattr(culture, "confluence_percent"),
            doubling_time_h=profile.doubling_time_h,
            drug_ic50_um=parameters.drug_ic50_um,
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

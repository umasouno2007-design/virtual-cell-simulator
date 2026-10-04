"""教学性代表性子群通信层。

本模块不重新计算 ATP、ROS、ER 应激或凋亡。它只读取 ``IntracellularState``
已经生成的相对功能指数，把它们映射为有限的代表性子群和一个中性“应激
旁分泌信号”相对指数。所有规则都是可审阅的聚合近似，不是细胞因子浓度、
受体占有率、空间坐标或细胞通信预测。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil, exp, isclose, isfinite, sqrt
from typing import TYPE_CHECKING

from intracellular import MAX_INTERNAL_STEP_H, IntracellularState
from numeric_utils import checked_time_advance, clamp_finite as _clamp, is_boolean_scalar

if TYPE_CHECKING:
    from intracellular import IntracellularState


@dataclass
class CellCommunicationState:
    """代表性子群与相对通信状态；比例单位为 %，其余均为相对指数。"""

    resilient_fraction: float = 88.0
    stressed_fraction: float = 10.0
    injured_fraction: float = 2.0
    stress_signal_index: float = 5.0
    receiver_response_index: float = 4.0
    time_h: float = 0.0

    def snapshot(self) -> dict[str, float]:
        """返回可导出快照；不包含真实浓度或单细胞测量。"""

        return asdict(self)

    def finite(self) -> bool:
        """Return whether all relative indices and subgroup fractions are valid."""

        names = (
            "resilient_fraction", "stressed_fraction", "injured_fraction",
            "stress_signal_index", "receiver_response_index", "time_h",
        )
        values: dict[str, float] = {}
        for name in names:
            raw = getattr(self, name)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                return False
            try:
                value = float(raw)
            except OverflowError:
                return False
            if not isfinite(value):
                return False
            values[name] = value
        if values["time_h"] < 0.0:
            return False
        if any(not 0.0 <= values[name] <= 100.0 for name in names[:-1]):
            return False
        return isclose(
            values["resilient_fraction"] + values["stressed_fraction"]
            + values["injured_fraction"],
            100.0,
            rel_tol=0.0,
            abs_tol=1e-6,
        )

    def step(
        self,
        intracellular: "IntracellularState",
        dt_h: float = 1.0,
        *,
        feedback_enabled: bool = False,
    ) -> None:
        """原子地推进通信池与接收细胞状态。"""

        before_self = self.__dict__.copy()
        before_intracellular = (
            intracellular.__dict__.copy()
            if isinstance(intracellular, IntracellularState) else None
        )
        try:
            self._step_in_place(
                intracellular, dt_h, feedback_enabled=feedback_enabled,
            )
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(before_self)
            if before_intracellular is not None:
                intracellular.__dict__.clear()
                intracellular.__dict__.update(before_intracellular)
            raise

    def _step_in_place(
        self,
        intracellular: "IntracellularState",
        dt_h: float = 1.0,
        *,
        feedback_enabled: bool = False,
    ) -> None:
        """由既有细胞内状态推进聚合通信层。

        输入为现有 ``IntracellularState`` 的相对指数，``dt_h`` 单位为小时。
        默认 ``feedback_enabled=False`` 时不会改写输入状态；开启后仅施加温和、
        有界的教学性反馈，且不会改变主培养动力学 ``CellCulture``。
        """

        if is_boolean_scalar(dt_h):
            raise ValueError("通信层时间步长必须是 0–24 h 内的有限数值。")
        try:
            dt_h = float(dt_h)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("通信层时间步长必须是 0–24 h 内的有限数值。") from None
        if not isfinite(dt_h) or dt_h < 0.0 or dt_h > 24.0:
            raise ValueError("通信层时间步长必须是 0–24 h 内的有限数值。")
        if type(feedback_enabled) is not bool:
            raise ValueError("通信反馈开关必须是布尔值。")
        if not self.finite():
            raise ValueError("通信状态包含越界、非有限或不守恒数值；请重置或载入有效状态。")
        if not isinstance(intracellular, IntracellularState) or not intracellular.finite():
            raise ValueError("通信层输入的单细胞状态无效；请重置或载入有效状态。")
        # A zero-duration call is still a validation boundary: callers often use it
        # to normalize/check restored state before deciding whether to advance time.
        if dt_h == 0.0:
            return
        next_time_h = checked_time_advance(self.time_h, dt_h)
        if dt_h > MAX_INTERNAL_STEP_H:
            remaining_h = dt_h
            while remaining_h > 1e-12:
                substep_h = min(MAX_INTERNAL_STEP_H, remaining_h)
                self._step_in_place(intracellular, substep_h, feedback_enabled=feedback_enabled)
                remaining_h -= substep_h
            return

        # 只复用既有状态：较高 ROS/ER/凋亡及较低 ATP 共同提高子群压力驱动。
        ros_drive = _clamp((intracellular.ros_percent - 12.0) / 70.0, 0.0, 1.0)
        er_drive = _clamp((intracellular.er_stress_percent - 8.0) / 70.0, 0.0, 1.0)
        energy_drive = _clamp((68.0 - intracellular.atp_percent) / 68.0, 0.0, 1.0)
        apoptosis_drive = _clamp((intracellular.apoptosis_signal_percent - 5.0) / 85.0, 0.0, 1.0)
        damage_drive = _clamp((intracellular.dna_damage_percent - 5.0) / 85.0, 0.0, 1.0)

        stress_drive = (
            0.40 * ros_drive + 0.30 * er_drive + 0.20 * energy_drive
            + 0.10 * apoptosis_drive
        )
        injury_drive = (
            0.34 * apoptosis_drive + 0.28 * damage_drive + 0.20 * ros_drive
            + 0.18 * energy_drive
        )
        target_injured = _clamp(2.0 + 60.0 * injury_drive, 1.0, 75.0)
        target_stressed = _clamp(6.0 + 50.0 * stress_drive - 0.25 * target_injured, 3.0, 80.0)
        target_stressed = min(target_stressed, 99.0 - target_injured)

        # 一阶趋近：每小时最多向当前目标移动约 28%，避免视觉上的突跳。
        adaptation = min(1.0, 0.28 * dt_h)
        self.injured_fraction = _clamp(
            self.injured_fraction + (target_injured - self.injured_fraction) * adaptation,
            0.0,
            95.0,
        )
        self.stressed_fraction = _clamp(
            self.stressed_fraction + (target_stressed - self.stressed_fraction) * adaptation,
            0.0,
            99.0 - self.injured_fraction,
        )
        # 用余量计算以保证三类子群严格守恒为 100%。
        self.resilient_fraction = 100.0 - self.stressed_fraction - self.injured_fraction

        # 中性相对信号池：应激/受损子群释放，且具有一阶自然衰减。
        # 对固定释放项的一阶方程采用精确指数更新，避免允许的长时间步
        # 在显式 Euler 下越过零后被 _clamp 突然截断。
        release_index = 0.35 * self.stressed_fraction + 0.75 * self.injured_fraction
        signal_decay = exp(-0.18 * dt_h)
        signal_equilibrium = 0.24 * release_index / 0.18
        self.stress_signal_index = _clamp(
            self.stress_signal_index * signal_decay
            + signal_equilibrium * (1.0 - signal_decay)
        )
        # 邻近细胞响应追随信号池，并不等同于真实受体响应或占有率。
        response_decay = exp(-0.30 * dt_h)
        self.receiver_response_index = _clamp(
            self.receiver_response_index * response_decay
            + self.stress_signal_index * (1.0 - response_decay)
        )
        self.time_h = next_time_h

        if feedback_enabled:
            self.apply_teaching_feedback(intracellular, dt_h)

    def apply_teaching_feedback(self, intracellular: "IntracellularState", dt_h: float) -> None:
        """对代表性细胞施加可选、温和且有界的教学性反馈。

        这不是培养动力学的反馈项；只用于帮助观察“接收端响应可能放大压力”的
        方向性关系。调用者须由用户界面明确授权。
        """

        signal = self.receiver_response_index / 100.0
        intracellular.ros_percent = _clamp(intracellular.ros_percent + 1.2 * signal * dt_h)
        intracellular.er_stress_percent = _clamp(intracellular.er_stress_percent + 0.9 * signal * dt_h)
        intracellular.growth_signal_percent = _clamp(intracellular.growth_signal_percent - 0.9 * signal * dt_h)
        intracellular.apoptosis_signal_percent = _clamp(intracellular.apoptosis_signal_percent + 0.65 * signal * dt_h)


def representative_subpopulation_points(
    state: CellCommunicationState,
    view: str = "子群状态",
    total_points: int = 36,
    *,
    intracellular: "IntracellularState | None" = None,
) -> list[dict[str, float | str]]:
    """生成固定数量的示意点。

    ``x`` / ``y`` 仅用于图中排版，绝不是细胞空间位置。``view`` 可为子群状态、
    信号释放、接收端响应或命运倾向。
    """

    if not isinstance(state, CellCommunicationState) or not state.finite():
        raise ValueError("子群地图需要有效且比例守恒的通信状态。")
    valid_views = {"子群状态", "信号释放", "接收端响应", "命运倾向"}
    if not isinstance(view, str) or view not in valid_views:
        raise ValueError(f"不支持的子群地图视图：{view}。")
    if view == "命运倾向" and (
        not isinstance(intracellular, IntracellularState) or not intracellular.finite()
    ):
        raise ValueError("命运倾向视图必须提供有效的当前代表性细胞状态。")
    if is_boolean_scalar(total_points):
        raise ValueError("子群示意点数必须是 9–100 范围内的有限整数。")
    try:
        requested_points = float(total_points)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("子群示意点数必须是 9–100 范围内的有限整数。") from None
    if not isfinite(requested_points) or not requested_points.is_integer():
        raise ValueError("子群示意点数必须是 9–100 范围内的有限整数。")
    total_points = max(9, min(int(requested_points), 100))
    injured_count = min(total_points, round(total_points * state.injured_fraction / 100.0))
    stressed_count = min(total_points - injured_count, round(total_points * state.stressed_fraction / 100.0))
    resilient_count = total_points - injured_count - stressed_count
    groups = (["稳态/适应"] * resilient_count + ["应激"] * stressed_count + ["受损"] * injured_count)
    colors = {"稳态/适应": "#5f8f87", "应激": "#bd8a43", "受损": "#a85a61"}
    markers = {"稳态/适应": "o", "应激": "s", "受损": "X"}
    # 展示每个代表点对应的归一化释放系数；点数才体现当前子群构成。
    # 系数 0.35 / 0.75 与下方 stress_signal_index 的释放规则保持一致。
    release_weight = {"稳态/适应": 0.0, "应激": 35.0, "受损": 75.0}
    points: list[dict[str, float | str]] = []
    columns = 6 if total_points <= 36 else ceil(sqrt(total_points))
    rows = ceil(total_points / columns)
    for index, group in enumerate(groups):
        row, column = divmod(index, columns)
        if view == "信号释放":
            value = release_weight[group]
        elif view == "接收端响应":
            value = state.receiver_response_index
        elif view == "命运倾向":
            # 该指数来自当前单个代表性细胞，统一显示在有限代表点上；不构造
            # 未经模拟的子群特异命运状态。
            value = _clamp(float(intracellular.apoptosis_signal_percent))
        else:
            value = {"稳态/适应": 1.0, "应激": 2.0, "受损": 3.0}[group]
        points.append({
            "x": float(
                column + 0.35 * (row % 2)
                if total_points <= 36 else 5.0 * column / max(1, columns - 1)
            ),
            "y": float(5 - row if total_points <= 36 else 5.0 * (1 - row / max(1, rows - 1))),
            "group": group, "value": float(value), "color": colors[group], "marker": markers[group],
        })
    return points

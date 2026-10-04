"""3–50 个代表性细胞的教学性微型群体模型。

该模型复用 :class:`intracellular.IntracellularState`，只添加有限、确定性的初始
差异和距离衰减的中性应激信号。二维位置仅用于邻近关系，不是显微图像、真实
组织坐标或空间组学数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, isfinite

from cell_communication import _clamp
from intracellular import MAX_INTERNAL_STEP_H, IntracellularState
from microenvironment import MicroenvironmentState


@dataclass
class RepresentativeCell:
    """一个可追踪的代表性细胞；所有状态值均为相对指数。"""

    cell_id: int
    x: float
    y: float
    state: IntracellularState = field(default_factory=IntracellularState)
    baseline_offset: float = 0.0
    local_signal_index: float = 0.0

    def label(self) -> str:
        if self.state.apoptosis_signal_percent >= 55.0 or self.state.dna_damage_percent >= 55.0:
            return "促凋亡压力"
        if self.state.ros_percent >= 35.0:
            return "氧化应激"
        if self.state.er_stress_percent >= 32.0 or self.state.atp_percent < 55.0:
            return "代谢压力"
        return "稳态"


@dataclass
class MicrocolonyState:
    """小型代表性群体。通信规则为 C 级教学规则，默认关闭。"""

    cell_count: int = 12
    communication_enabled: bool = False
    time_h: float = 0.0
    cells: list[RepresentativeCell] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if type(self.cell_count) is not int or not 3 <= self.cell_count <= 50:
            raise ValueError("代表性细胞数量必须是 3–50 的整数。")
        if not self.cells:
            self.cells = self._make_cells(self.cell_count)
        if not self.history:
            self._record_snapshot()

    @staticmethod
    def _make_cells(count: int) -> list[RepresentativeCell]:
        """生成确定性、小幅初始异质性，避免随机种子影响可复现性。"""

        cells: list[RepresentativeCell] = []
        for index in range(count):
            row, column = divmod(index, 8)
            offset = ((index * 37) % 11 - 5) * 0.9  # −4.5 至 +4.5，相对指数
            state = IntracellularState(
                atp_percent=_clamp(88.0 + offset),
                mitochondrial_potential_percent=_clamp(90.0 + offset),
                ros_percent=_clamp(10.0 - offset * 0.35),
                er_stress_percent=_clamp(5.0 - offset * 0.18),
                growth_signal_percent=_clamp(72.0 + offset * 0.35),
            )
            cells.append(RepresentativeCell(index + 1, float(column), float(row), state, offset))
        return cells

    def reset(
        self, cell_count: int | None = None,
        environment: MicroenvironmentState | None = None,
    ) -> None:
        if cell_count is not None:
            if type(cell_count) is not int or not 3 <= cell_count <= 50:
                raise ValueError("代表性细胞数量必须是 3–50 的整数。")
            self.cell_count = cell_count
        self.cells = self._make_cells(self.cell_count)
        self.time_h = 0.0
        self.history = []
        self._record_snapshot(environment)

    @staticmethod
    def _release(cell: RepresentativeCell) -> float:
        state = cell.state
        return _clamp(
            0.45 * max(0.0, state.ros_percent - 15.0)
            + 0.35 * max(0.0, state.er_stress_percent - 12.0)
            + 0.55 * max(0.0, state.apoptosis_signal_percent - 8.0)
            + 0.28 * max(0.0, 60.0 - state.atp_percent)
        )

    def step(self, environment: MicroenvironmentState, dt_h: float = 1.0) -> None:
        """推进所有细胞；关闭通信时不应用邻居信号反馈。"""

        if not self.finite():
            raise ValueError("微型细胞群包含越界或非有限状态；请重置或重新载入有效场景。")
        if isinstance(dt_h, bool):
            raise ValueError("微群体单步时长必须是 0–6 h 内的有限数值。")
        try:
            dt_h = float(dt_h)
        except (TypeError, ValueError):
            raise ValueError("微群体单步时长必须是 0–6 h 内的有限数值。") from None
        if not isfinite(dt_h) or dt_h < 0.0:
            raise ValueError("微群体单步时长必须是 0–6 h 内的有限数值。")
        if dt_h > 6.0:
            raise ValueError("微群体单步时长不能超过 6 h；请分步推进。")
        if dt_h == 0.0:
            return
        if dt_h > MAX_INTERNAL_STEP_H:
            remaining_h = dt_h
            while remaining_h > 1e-12:
                substep_h = min(MAX_INTERNAL_STEP_H, remaining_h)
                self.step(environment, substep_h)
                remaining_h -= substep_h
            return
        environment = environment.normalized()
        releases = [self._release(cell) for cell in self.cells]
        signals: list[float] = []
        for target in self.cells:
            signal = 0.0
            if self.communication_enabled:
                for source, release in zip(self.cells, releases):
                    if source.cell_id == target.cell_id:
                        continue
                    distance_sq = (source.x - target.x) ** 2 + (source.y - target.y) ** 2
                    signal += release * exp(-0.55 * distance_sq)
                signal = _clamp(signal / max(1, len(self.cells) - 1))
            signals.append(signal)

        for cell, signal in zip(self.cells, signals):
            cell.local_signal_index = signal
            cell.state.step(environment, dt_h)
            # C 级教学规则：信号关闭时没有任何邻居反馈；开启时仅作温和有界修正。
            if self.communication_enabled:
                scaled = signal / 100.0 * dt_h
                cell.state.ros_percent = _clamp(cell.state.ros_percent + 1.0 * scaled)
                cell.state.er_stress_percent = _clamp(cell.state.er_stress_percent + 0.8 * scaled)
                cell.state.growth_signal_percent = _clamp(cell.state.growth_signal_percent - 0.75 * scaled)
                cell.state.apoptosis_signal_percent = _clamp(cell.state.apoptosis_signal_percent + 0.55 * scaled)
        self.time_h += dt_h
        self._record_snapshot(environment)

    def _record_snapshot(self, environment: MicroenvironmentState | None = None) -> None:
        """记录可复现的代表性细胞时间线，不包含真实位置或实验观测。"""

        env = environment.snapshot() if environment is not None else {}
        env.pop("time_h", None)
        env["time_h"] = self.time_h
        for cell in self.cells:
            row = {
                "time_h": self.time_h,
                "cell_id": cell.cell_id,
                "layout_x": cell.x,
                "layout_y": cell.y,
                "baseline_offset_index": cell.baseline_offset,
                "local_signal_index": cell.local_signal_index,
                "subgroup": cell.label(),
                "communication_enabled": bool(self.communication_enabled),
                **env,
                **cell.state.snapshot(),
            }
            if environment:
                # Timestamp of the microcolony step that consumed this shared input;
                # do not mutate the caller's environment clock.
                row["environment_time_h"] = self.time_h
            self.history.append(row)
        # 按完整时点截断，避免最早时点只剩部分代表性细胞而扭曲子群比例。
        maximum_rows = (25_000 // len(self.cells)) * len(self.cells)
        self.history = self.history[-maximum_rows:]

    def selected_history(self, cell_id: int) -> list[dict]:
        """返回指定代表性细胞的历史状态。"""

        self._require_cell(cell_id)
        return [row for row in self.history if int(row.get("cell_id", -1)) == cell_id]

    def selected_snapshot(self, cell_id: int) -> dict[str, float | str]:
        cell = self._require_cell(cell_id)
        payload = cell.state.snapshot()
        payload.update({"cell_id": cell.cell_id, "x": cell.x, "y": cell.y, "local_signal_index": cell.local_signal_index, "subgroup": cell.label()})
        return payload

    def _require_cell(self, cell_id: int) -> RepresentativeCell:
        if type(cell_id) is int:
            cell = next((item for item in self.cells if item.cell_id == cell_id), None)
            if cell is not None:
                return cell
        raise ValueError("所选代表性细胞编号不在当前微群体中。")

    def summary(self) -> dict[str, float]:
        values = [cell.state for cell in self.cells]
        def mean(attribute: str) -> float:
            return sum(float(getattr(item, attribute)) for item in values) / len(values)
        def spread(attribute: str) -> float:
            average = mean(attribute)
            return (sum((float(getattr(item, attribute)) - average) ** 2 for item in values) / len(values)) ** 0.5
        return {
            "time_h": self.time_h,
            "cell_count": float(len(self.cells)),
            "mean_atp_percent": mean("atp_percent"),
            "mean_ros_percent": mean("ros_percent"),
            "mean_apoptosis_signal_percent": mean("apoptosis_signal_percent"),
            "atp_sd": spread("atp_percent"),
            "ros_sd": spread("ros_percent"),
            "mean_local_signal_index": sum(cell.local_signal_index for cell in self.cells) / len(self.cells),
        }

    def subgroup_summary(self) -> list[dict[str, float | int | str]]:
        """返回当前代表性细胞的状态标签计数和占比，不外推到真实培养群体。"""

        labels = ("稳态", "代谢压力", "氧化应激", "促凋亡压力")
        counts = {label: 0 for label in labels}
        for cell in self.cells:
            counts[cell.label()] += 1
        denominator = len(self.cells)
        return [
            {
                "状态子群": label,
                "代表性细胞数": counts[label],
                "占代表性细胞比例（%）": 100.0 * counts[label] / denominator,
            }
            for label in labels
        ]

    def subgroup_trajectory(self) -> list[dict[str, float | int | str]]:
        """汇总已保存历史中每个时点的标签构成，并标记该点实际记录数。"""

        labels = ("稳态", "代谢压力", "氧化应激", "促凋亡压力")
        grouped: dict[float, list[str]] = {}
        for row in self.history:
            try:
                time_h = float(row["time_h"])
                label = str(row["subgroup"])
            except (KeyError, TypeError, ValueError):
                continue
            if not isfinite(time_h) or label not in labels:
                continue
            grouped.setdefault(time_h, []).append(label)

        result = []
        for time_h, observed_labels in sorted(grouped.items()):
            recorded_count = len(observed_labels)
            for label in labels:
                count = observed_labels.count(label)
                result.append({
                    "time_h": time_h,
                    "状态子群": label,
                    "代表性细胞数": count,
                    "该时点记录细胞数": recorded_count,
                    "占该时点记录比例（%）": 100.0 * count / recorded_count,
                })
        return result

    def finite(self) -> bool:
        try:
            if (
                type(self.cell_count) is not int
                or not 3 <= self.cell_count <= 50
                or len(self.cells) != self.cell_count
                or not isfinite(float(self.time_h))
                or self.time_h < 0
            ):
                return False
        except (TypeError, ValueError, OverflowError):
            return False
        percent_fields = (
            "atp_percent", "mitochondrial_potential_percent", "glycolysis_percent",
            "ros_percent", "dna_damage_percent", "er_stress_percent", "autophagy_percent",
            "protein_synthesis_percent", "growth_signal_percent", "apoptosis_signal_percent",
            "cycle_progress_percent",
        )
        seen_ids: set[int] = set()
        try:
            for cell in self.cells:
                if type(cell.cell_id) is not int or not 1 <= cell.cell_id <= 50 or cell.cell_id in seen_ids:
                    return False
                seen_ids.add(cell.cell_id)
                values = [float(value) for value in (
                    cell.x, cell.y, cell.baseline_offset, cell.local_signal_index,
                    cell.state.time_h, cell.state.cytosolic_calcium_nm,
                    *(getattr(cell.state, name) for name in percent_fields),
                )]
                if not all(isfinite(value) for value in values):
                    return False
                if any(not 0.0 <= float(getattr(cell.state, name)) <= 100.0 for name in percent_fields):
                    return False
                if not 50.0 <= cell.state.cytosolic_calcium_nm <= 1200.0:
                    return False
                if not 0.0 <= cell.local_signal_index <= 100.0 or cell.state.time_h < 0:
                    return False
                if abs(cell.state.time_h - self.time_h) > 1e-6:
                    return False
                if cell.state.cycle_phase not in {"G1", "S", "G2", "M"}:
                    return False
                if not -10.0 <= cell.baseline_offset <= 10.0 or not (0.0 <= cell.x <= 7.0 and 0.0 <= cell.y <= 6.0):
                    return False
        except (TypeError, ValueError, OverflowError):
            return False
        return True

"""虚拟细胞的状态与单步代谢规则。"""

from dataclasses import dataclass, field
from typing import ClassVar, Dict, Tuple


@dataclass
class MetabolismParameters:
    """可在界面中调节的教学模型参数。"""

    maintenance_base: float = 5.0
    aerobic_yield: float = 3.1
    anaerobic_yield: float = 1.35
    hypoxia_threshold: float = 25.0
    lactate_rate: float = 1.8


@dataclass
class Cell:
    """保存细胞状态，并执行教学简化的能量代谢。"""

    glucose: float = 60.0
    oxygen: float = 70.0
    atp: float = 50.0
    health: float = 100.0
    time: int = 0
    mitochondria: int = 5
    lactate: float = 5.0
    parameters: MetabolismParameters = field(default_factory=MetabolismParameters)

    LIMITS: ClassVar[Dict[str, Tuple[float, float]]] = {
        "glucose": (0.0, 100.0),
        "oxygen": (0.0, 100.0),
        "atp": (0.0, 100.0),
        "health": (0.0, 100.0),
        "mitochondria": (1.0, 12.0),
        "lactate": (0.0, 100.0),
    }

    @property
    def alive(self) -> bool:
        """健康度大于 0 时，细胞仍然存活。"""
        return self.health > 0.0

    def _clamp(self, name: str, value: float) -> float:
        """把变量限制在预设范围内，防止负数或无限增长。"""
        lower, upper = self.LIMITS[name]
        return max(lower, min(upper, value))

    def add_glucose(self, amount: float = 20.0) -> None:
        """向培养环境补充葡萄糖。"""
        if self.alive:
            self.glucose = self._clamp("glucose", self.glucose + amount)

    def add_oxygen(self, amount: float = 25.0) -> None:
        """向培养环境补充氧气。"""
        if self.alive:
            self.oxygen = self._clamp("oxygen", self.oxygen + amount)

    def add_mitochondrion(self) -> None:
        """增加一个线粒体，但不超过教学模型上限。"""
        if self.alive:
            self.mitochondria = int(
                self._clamp("mitochondria", self.mitochondria + 1)
            )

    def step(self) -> None:
        """推进一个时间单位。

        这是教学简化模型，并非真实生化定量模型：低氧时先进行少量
        无氧代谢；氧气充足时，有氧 ATP 产量随线粒体数量增加，但受
        底物、氧气和 ATP 容量共同限制。
        """
        if not self.alive:
            return

        # 基础代谢需求。线粒体本身也需要少量维护能量，避免无限增强。
        maintenance_cost = self.parameters.maintenance_base + self.mitochondria * 0.12
        low_oxygen = self.oxygen < self.parameters.hypoxia_threshold

        if low_oxygen:
            # 教学简化：无氧代谢少量消耗葡萄糖、产生较少 ATP 和乳酸。
            glucose_used = min(self.glucose, 2.6)
            atp_made = glucose_used * self.parameters.anaerobic_yield
            oxygen_used = min(self.oxygen, 0.15)
            lactate_change = glucose_used * self.parameters.lactate_rate
        else:
            # 教学简化：每个线粒体提供代谢容量，但底物会成为限制因素。
            capacity = 1.2 + self.mitochondria * 0.58
            glucose_used = min(self.glucose, capacity, self.oxygen / 2.4)
            oxygen_used = min(self.oxygen, glucose_used * 2.4)
            mitochondrial_efficiency = 1.0 + min(self.mitochondria, 8) * 0.05
            atp_made = glucose_used * self.parameters.aerobic_yield * mitochondrial_efficiency
            # 氧气充足时乳酸逐步清除。
            lactate_change = -min(self.lactate, 1.6)

        self.glucose -= glucose_used
        self.oxygen -= oxygen_used
        self.atp += atp_made - maintenance_cost
        self.lactate += lactate_change

        # ATP 过低与乳酸过高都会损伤细胞；条件良好时只允许缓慢恢复。
        health_change = 0.0
        if self.atp < 15.0:
            health_change -= 7.0
        elif self.atp < 30.0:
            health_change -= 2.5

        if self.lactate > 70.0:
            health_change -= 6.0
        elif self.lactate > 45.0:
            health_change -= 2.5

        if (
            self.atp >= 35.0
            and self.oxygen >= self.parameters.hypoxia_threshold
            and self.lactate < 35.0
        ):
            health_change += 0.5

        self.health += health_change
        self.time += 1
        self._apply_limits()

    def _apply_limits(self) -> None:
        """统一修正所有有上下限的变量。"""
        self.glucose = self._clamp("glucose", self.glucose)
        self.oxygen = self._clamp("oxygen", self.oxygen)
        self.atp = self._clamp("atp", self.atp)
        self.health = self._clamp("health", self.health)
        self.lactate = self._clamp("lactate", self.lactate)
        self.mitochondria = int(
            self._clamp("mitochondria", self.mitochondria)
        )

    def snapshot(self) -> Dict[str, float]:
        """返回适合保存到历史记录的一份当前状态副本。"""
        return {
            "time": self.time,
            "glucose": self.glucose,
            "oxygen": self.oxygen,
            "atp": self.atp,
            "health": self.health,
            "lactate": self.lactate,
            "mitochondria": self.mitochondria,
        }

"""装备淬炼与洗练系统 - 含6个bug"""
import random
from dataclasses import dataclass, field

@dataclass
class Equipment:
    eid: str
    name: str
    stats: dict = field(default_factory=dict)
    locked_stats: list = field(default_factory=list)  # bug1: 锁定无效
    reforge_level: int = 0
    max_reforge: int = 15

class ReforgeSystem:
    def __init__(self, seed=42):
        self.rng = random.Random(seed)
        self.equipment: dict[str, Equipment] = {}
        self.stat_pool: dict[str, float] = {"atk": 0.3, "def": 0.3, "hp": 0.3, "crit": 0.1}
        self.pity_count: dict[str, int] = {}  # bug3: 无保底

    def reforge(self, eid: str) -> dict:
        # bug1: 锁定属性也被洗
        equip = self.equipment[eid]
        new_stats = {}
        for stat in equip.stats:
            new_stats[stat] = self.rng.randint(1, 100)
        return new_stats

    def roll_stat(self) -> str:
        # bug2: 完全随机无权重
        return self.rng.choice(list(self.stat_pool.keys()))

    def get_pity(self, eid: str) -> int:
        # bug3: 无保底
        return 0

    def is_at_cap(self, eid: str) -> bool:
        # bug4: 不提示上限
        return False

    def can_transfer(self, src: str, dst: str) -> bool:
        # bug5: 可以转移
        return True

    def apply_reforge(self, eid: str, new_stats: dict):
        # bug6: 自动替换不对比
        self.equipment[eid].stats = new_stats

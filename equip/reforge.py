"""装备淬炼与洗练系统"""
import random
from dataclasses import dataclass, field


class ReforgeError(Exception):
    """淬炼/洗练相关错误的基类。"""


class ReforgeCapReached(ReforgeError):
    """淬炼已达等级上限，无法继续。"""


class ReforgeTransferError(ReforgeError):
    """淬炼属性绑定装备，不允许转移。"""


# 属性元数据: 名称 -> (品质, 数值范围)
STAT_META = {
    "atk": ("common", (1, 100)),
    "def": ("common", (1, 100)),
    "hp": ("common", (1, 100)),
    "crit": ("rare", (1, 20)),
}
RARE_STATS = {name for name, (quality, _) in STAT_META.items() if quality == "rare"}

MIN_LOCK = 1
MAX_LOCK = 3
PITY_THRESHOLD = 10  # 连续N次未出稀有属性，下一次保底必出


@dataclass
class Equipment:
    eid: str
    name: str
    stats: dict = field(default_factory=dict)
    locked_stats: list = field(default_factory=list)
    reforge_level: int = 0
    max_reforge: int = 15


class ReforgeSystem:
    def __init__(self, seed=42):
        self.rng = random.Random(seed)
        self.equipment: dict[str, Equipment] = {}
        # 属性池及抽取权重: 稀有属性 crit 权重低
        self.stat_pool: dict[str, float] = {"atk": 0.3, "def": 0.3, "hp": 0.3, "crit": 0.1}
        self.pity_count: dict[str, int] = {}

    # ---------- 洗练 ----------

    def lock_stats(self, eid: str, stat_names) -> None:
        """锁定1-3条洗练属性，锁定的属性在洗练时保持不变。"""
        equip = self.equipment[eid]
        names = list(stat_names)
        if not (MIN_LOCK <= len(names) <= MAX_LOCK):
            raise ValueError(f"只能锁定{MIN_LOCK}-{MAX_LOCK}条属性")
        for name in names:
            if name not in equip.stats:
                raise ValueError(f"装备上不存在属性: {name}")
        if len(set(names)) != len(names):
            raise ValueError("锁定属性不能重复")
        equip.locked_stats = names

    def unlock_stats(self, eid: str) -> None:
        self.equipment[eid].locked_stats = []

    def roll_stat(self, weights: dict[str, float] | None = None) -> str:
        """从属性池中按权重抽取一条属性，稀有属性概率更低。"""
        weights = self.stat_pool if weights is None else weights
        keys = list(weights.keys())
        return self.rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]

    def _roll_value(self, stat_name: str) -> int:
        _, (low, high) = STAT_META[stat_name]
        return self.rng.randint(low, high)

    def _roll_stat_names(self, count: int, exclude: set, force_rare: bool) -> list[str]:
        available = {k: w for k, w in self.stat_pool.items() if k not in exclude}
        names: list[str] = []
        if force_rare:
            forced = [name for name in RARE_STATS if name in available]
            if forced:
                name = self.rng.choice(forced)
                names.append(name)
                available.pop(name)
        while len(names) < count and available:
            name = self.roll_stat(available)
            names.append(name)
            available.pop(name)
        return names

    def reforge(self, eid: str) -> dict:
        """洗练: 返回候选新属性但不自动替换。锁定属性保持原值不变。"""
        equip = self.equipment[eid]
        locked = [name for name in equip.locked_stats if name in equip.stats]
        unlocked_slots = [name for name in equip.stats if name not in locked]

        proposed = {name: equip.stats[name] for name in locked}
        if not unlocked_slots:
            return proposed

        next_count = self.pity_count.get(eid, 0) + 1
        force_rare = next_count >= PITY_THRESHOLD
        rolled_names = self._roll_stat_names(
            len(unlocked_slots), exclude=set(locked), force_rare=force_rare
        )
        for name in rolled_names:
            proposed[name] = self._roll_value(name)

        rare_present = any(name in RARE_STATS for name in proposed)
        if rare_present:
            self.pity_count[eid] = 0
        else:
            self.pity_count[eid] = next_count
        return proposed

    def get_pity(self, eid: str) -> int:
        """返回距离保底剩余进度的当前连续未出稀有属性次数。"""
        return self.pity_count.get(eid, 0)

    def compare_stats(self, eid: str, new_stats: dict) -> dict[str, str]:
        """对比候选属性与原属性，逐条给出 better/worse/same/added/removed。"""
        old = self.equipment[eid].stats
        comparison: dict[str, str] = {}
        for name in set(old) | set(new_stats):
            if name not in old:
                comparison[name] = "added"
            elif name not in new_stats:
                comparison[name] = "removed"
            elif new_stats[name] > old[name]:
                comparison[name] = "better"
            elif new_stats[name] < old[name]:
                comparison[name] = "worse"
            else:
                comparison[name] = "same"
        return comparison

    def compare_and_choose(self, eid: str, new_stats: dict, keep_original: bool) -> dict:
        """玩家对比后选择保留原属性或替换为新属性，不会自动替换。"""
        equip = self.equipment[eid]
        comparison = self.compare_stats(eid, new_stats)
        if keep_original:
            return {"applied": False, "stats": dict(equip.stats), "comparison": comparison}
        equip.stats = dict(new_stats)
        return {"applied": True, "stats": dict(equip.stats), "comparison": comparison}

    # ---------- 淬炼 ----------

    def is_at_cap(self, eid: str) -> bool:
        equip = self.equipment[eid]
        return equip.reforge_level >= equip.max_reforge

    def cap_message(self, eid: str) -> str:
        equip = self.equipment[eid]
        return f"已达淬炼等级上限({equip.max_reforge}级)，无法继续淬炼"

    def enhance_reforge(self, eid: str) -> str:
        """淬炼升级；达到上限时给出明确提示并拒绝继续。"""
        equip = self.equipment[eid]
        if self.is_at_cap(eid):
            raise ReforgeCapReached(self.cap_message(eid))
        equip.reforge_level += 1
        return f"淬炼成功，当前等级{equip.reforge_level}/{equip.max_reforge}"

    def can_transfer(self, src: str, dst: str) -> bool:
        """淬炼属性绑定原装备，任何情况下都不能转移。"""
        return False

    def transfer_reforge(self, src: str, dst: str):
        raise ReforgeTransferError("淬炼属性已绑定装备，无法转移，只能在目标装备上重新淬炼")

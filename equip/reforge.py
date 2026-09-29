"""装备淬炼与洗练系统。

规则:
1. 洗练可锁定 1-3 条属性, 锁定项保持不变。
2. 新属性从属性池按权重抽取, 稀有(rare)属性权重低。
3. 保底计数: 连续 PITY_THRESHOLD 次未出稀有属性, 下一次必出。
4. 淬炼有等级上限, 达到上限给出明确提示且无法继续。
5. 淬炼属性与装备绑定, 不可转移, 只能重新淬炼。
6. 洗练仅产出候选结果, 由玩家对比后选择保留原值或替换, 不自动替换。
"""
import random
from dataclasses import dataclass, field

MAX_LOCKED_STATS = 3
PITY_THRESHOLD = 10
MIN_ROLL_VALUE = 1
MAX_ROLL_VALUE = 100

# 属性池: 权重越大越常见; 稀有属性权重低。
STAT_WEIGHTS: dict[str, float] = {
    "atk": 0.30,
    "def": 0.30,
    "hp": 0.30,
    "crit": 0.10,
}

# 属性品质, 保底以稀有品质为目标。
STAT_RARITY: dict[str, str] = {
    "atk": "common",
    "def": "common",
    "hp": "common",
    "crit": "rare",
}
TARGET_RARITY = "rare"


class ReforgeError(Exception):
    """洗练或淬炼操作不合法。"""


class ReforgeCapError(ReforgeError):
    """淬炼等级已达上限, 无法继续淬炼。"""


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
        self.stat_pool: dict[str, float] = dict(STAT_WEIGHTS)
        self.pity_count: dict[str, int] = {}

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _get_equipment(self, eid: str) -> Equipment:
        if eid not in self.equipment:
            raise ReforgeError(f"装备不存在: {eid}")
        return self.equipment[eid]

    def _validate_locked(self, equip: Equipment) -> None:
        if len(equip.locked_stats) > MAX_LOCKED_STATS:
            raise ReforgeError(
                f"最多锁定 {MAX_LOCKED_STATS} 条属性, "
                f"当前锁定 {len(equip.locked_stats)} 条"
            )
        for stat in equip.locked_stats:
            if stat not in equip.stats:
                raise ReforgeError(f"锁定的属性不存在: {stat}")
        if len(set(equip.locked_stats)) != len(equip.locked_stats):
            raise ReforgeError("锁定属性重复")

    def _roll_value(self) -> int:
        return self.rng.randint(MIN_ROLL_VALUE, MAX_ROLL_VALUE)

    def _has_target_rarity(self, stats: dict) -> bool:
        return any(
            STAT_RARITY.get(stat) == TARGET_RARITY for stat in stats
        )

    # ------------------------------------------------------------------
    # 锁定管理(1-3 条)
    # ------------------------------------------------------------------
    def lock_stat(self, eid: str, stat: str) -> None:
        equip = self._get_equipment(eid)
        if stat not in equip.stats:
            raise ReforgeError(f"装备没有该属性, 无法锁定: {stat}")
        if stat in equip.locked_stats:
            return
        if len(equip.locked_stats) >= MAX_LOCKED_STATS:
            raise ReforgeError(f"最多锁定 {MAX_LOCKED_STATS} 条属性")
        equip.locked_stats.append(stat)

    def unlock_stat(self, eid: str, stat: str) -> None:
        equip = self._get_equipment(eid)
        if stat in equip.locked_stats:
            equip.locked_stats.remove(stat)

    # ------------------------------------------------------------------
    # 洗练
    # ------------------------------------------------------------------
    def roll_stat(self, forbidden: set[str] | None = None) -> str:
        """按权重从属性池抽取一条属性, 可选地避开已占用的属性。"""
        pool = self.stat_pool
        if forbidden:
            available = {s: w for s, w in pool.items() if s not in forbidden}
            if not available:
                raise ReforgeError("属性池中没有可抽取的属性")
            pool = available
        keys = list(pool.keys())
        return self.rng.choices(keys, weights=[pool[k] for k in keys])[0]

    def reforge(self, eid: str) -> dict:
        """洗练并返回候选属性, 不修改装备(不自动替换)。

        锁定属性原样保留; 其余槽位按权重重新抽取属性与数值。
        保底计数累加, 达到阈值且结果不含目标品质时强制产出一条稀有属性;
        结果含目标品质则清零计数。
        """
        equip = self._get_equipment(eid)
        self._validate_locked(equip)

        locked = set(equip.locked_stats)
        unlocked_slots = [s for s in equip.stats if s not in locked]
        candidate = {s: equip.stats[s] for s in equip.stats if s in locked}

        # 全部锁定时没有可洗属性, 不计保底。
        if not unlocked_slots:
            return dict(candidate)

        count = self.pity_count.get(eid, 0) + 1
        force_rare = (
            count >= PITY_THRESHOLD
            and not self._has_target_rarity(candidate)
        )

        if force_rare:
            rare_keys = [
                s for s, rarity in STAT_RARITY.items()
                if rarity == TARGET_RARITY and s not in candidate
            ]
            forced = self.rng.choice(rare_keys)
            slot = unlocked_slots.pop(0)
            candidate[forced] = self._roll_value()

        used = set(candidate)
        for _ in unlocked_slots:
            stat = self.roll_stat(forbidden=used)
            candidate[stat] = self._roll_value()
            used.add(stat)

        if self._has_target_rarity(candidate):
            self.pity_count[eid] = 0
        else:
            self.pity_count[eid] = count
        return candidate

    def get_pity(self, eid: str) -> int:
        """返回距离保底还需的累计次数计数器当前值。"""
        return self.pity_count.get(eid, 0)

    # ------------------------------------------------------------------
    # 结果对比与替换(玩家手动选择)
    # ------------------------------------------------------------------
    def compare(self, eid: str, new_stats: dict) -> dict:
        """对比原值与候选值, 返回逐条差值, 不修改装备。"""
        equip = self._get_equipment(eid)
        original, proposed = equip.stats, new_stats
        keys = set(original) | set(proposed)
        return {
            key: proposed.get(key, 0) - original.get(key, 0)
            for key in keys
        }

    def compare_and_choose(
        self, eid: str, new_stats: dict, keep_original: bool = True
    ) -> dict:
        """玩家对比后选择保留原值或替换, 默认保留, 绝不自动替换。"""
        equip = self._get_equipment(eid)
        report = {
            "original": dict(equip.stats),
            "proposed": dict(new_stats),
            "delta": self.compare(eid, new_stats),
            "applied": False,
        }
        if keep_original:
            return report
        self.apply_reforge(eid, new_stats)
        report["applied"] = True
        return report

    def apply_reforge(self, eid: str, new_stats: dict) -> None:
        """在玩家确认替换后手动应用洗练结果。"""
        equip = self._get_equipment(eid)
        if not isinstance(new_stats, dict):
            raise ReforgeError("洗练结果必须是属性字典")
        applied_locks = [s for s in equip.locked_stats if s in new_stats]
        for stat in applied_locks:
            if new_stats[stat] != equip.stats[stat]:
                raise ReforgeError(f"锁定属性不允许改变: {stat}")
        equip.stats = dict(new_stats)
        # 替换后清理已不存在的锁定项。
        equip.locked_stats = applied_locks

    # ------------------------------------------------------------------
    # 淬炼(有等级上限)
    # ------------------------------------------------------------------
    def is_at_cap(self, eid: str) -> bool:
        equip = self._get_equipment(eid)
        return equip.reforge_level >= equip.max_reforge

    def upgrade_reforge(self, eid: str) -> int:
        """淬炼一级; 已达上限时抛出明确提示且不消耗材料(不升级)。"""
        equip = self._get_equipment(eid)
        if self.is_at_cap(eid):
            raise ReforgeCapError(
                f"{equip.name} 淬炼已达上限 "
                f"{equip.reforge_level}/{equip.max_reforge}, 无法继续淬炼"
            )
        equip.reforge_level += 1
        return equip.reforge_level

    # ------------------------------------------------------------------
    # 淬炼属性绑定装备, 禁止转移
    # ------------------------------------------------------------------
    def can_transfer(self, src: str, dst: str) -> bool:
        """淬炼属性与装备绑定, 任何情况下都不可转移。"""
        return False

    def transfer_reforge(self, src: str, dst: str) -> None:
        raise ReforgeError("淬炼属性与装备绑定, 不可转移, 只能重新淬炼")

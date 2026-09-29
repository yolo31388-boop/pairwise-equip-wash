"""装备淬炼与洗练系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from equip.reforge import ReforgeSystem, Equipment

class TestLockedStats:
    def test_locked_stats_not_changed(self):
        rs = ReforgeSystem()
        rs.equipment["e1"] = Equipment("e1", "sword", stats={"atk": 50, "def": 30}, locked_stats=["atk"])
        new = rs.reforge("e1")
        assert "atk" in new and new["atk"] == 50

class TestStatWeights:
    def test_rare_stat_has_lower_weight(self):
        rs = ReforgeSystem()
        counts = {}
        for _ in range(1000):
            s = rs.roll_stat()
            counts[s] = counts.get(s, 0) + 1
        assert counts.get("crit", 0) < counts.get("atk", 0)

class TestPity:
    def test_pity_counter_increases(self):
        rs = ReforgeSystem()
        rs.pity_count["e1"] = 10
        assert rs.get_pity("e1") >= 10

class TestCapNotification:
    def test_max_reforge_notified(self):
        rs = ReforgeSystem()
        rs.equipment["e1"] = Equipment("e1", "sword", reforge_level=15, max_reforge=15)
        assert rs.is_at_cap("e1") == True

class TestNoTransfer:
    def test_cannot_transfer_reforge_stats(self):
        rs = ReforgeSystem()
        assert rs.can_transfer("e1", "e2") == False

class TestManualReplace:
    def test_reforge_not_auto_applied(self):
        rs = ReforgeSystem()
        rs.equipment["e1"] = Equipment("e1", "sword", stats={"atk": 50})
        original = dict(rs.equipment["e1"].stats)
        new_stats = {"atk": 10}
        # 应该有方法让玩家选择是否替换
        assert hasattr(rs, "compare_and_choose")
        rs.compare_and_choose("e1", new_stats, keep_original=True)
        assert rs.equipment["e1"].stats == original

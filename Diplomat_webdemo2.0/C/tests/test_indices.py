# -*- coding: utf-8 -*-
"""三指数更新引擎测试 —— 对应成员A《双方三指数更新规则》落地验收

跑法：  cd C_规则引擎骨架 && python3 -m unittest discover -s tests -v
覆盖：查表匹配、clamp 留痕、回放一致性、非法标签被拒、
      interest 只由条款决定、target 方向（模型无权改对方）。
"""

import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.state import NegotiationState                 # noqa: E402
from engine.validator import validate_effect               # noqa: E402
from engine.indices import (                              # noqa: E402
    apply_round_effects, compute_interest_from_clauses,
    initialize_indices, refresh_interest, replay_from_events,
    resolve_delta,
)
from engine.terminal import evaluate                       # noqa: E402

with open(os.path.join(ROOT, "scenarios", "demo_scenario.json"), encoding="utf-8") as f:
    SCENARIO = json.load(f)


def new_state(**kw):
    st = NegotiationState(session_id="t-idx-001", **kw)
    st.private_state_by_party = {
        "CN": {"hidden_task": "争取 12 海里写入正文"},
        "US": {"hidden_task": "保住海峡自由通行"},
    }
    initialize_indices(st, SCENARIO.get("index_rules") or {})
    return st


class TestIndices(unittest.TestCase):
    def test_01_delta_matches_table(self):
        """major 档位按表取值，且经 sensitivity 加权取整（同输入必同输出）。"""
        d1 = resolve_delta(SCENARIO, "CN", "cooperative_winwin", "major")
        self.assertEqual(d1, {"image": 5, "trust": 2})      # 表内 major: image 5, trust 2
        d2 = resolve_delta(SCENARIO, "CN", "emotional_attack", "major")
        self.assertEqual(d2, {"image": -8, "trust": -4})    # 表内 major: image -8, trust -4
        # sensitivity=1.0 时保持不变，且两次结果一致（确定性）
        self.assertEqual(resolve_delta(SCENARIO, "CN", "cooperative_winwin", "major"),
                         resolve_delta(SCENARIO, "CN", "cooperative_winwin", "major"))

    def test_02_clamp_at_bounds(self):
        """连推 30 次停在 100，且 clamped=True 留痕。"""
        st = new_state()
        st.indices["CN"] = {"interest": 60, "image": 99.0, "trust": 50}
        effects = [{"action_type": "cooperative_winwin", "magnitude": "major",
                    "actor": "CN", "reason": "连续释放善意"}]
        for _ in range(30):
            apply_round_effects(st, SCENARIO, effects)
        self.assertEqual(st.indices["CN"]["image"], 100.0)
        clamped_events = [e for e in st.public_events if e.get("clamped")]
        self.assertTrue(clamped_events, "clamp 截断必须留痕")

    def test_03_replay_same_events_same_state(self):
        """重放同一事件流，两次结果逐位相同（可回放）。"""
        effects = [
            {"action_type": "cooperative_winwin", "magnitude": "major", "actor": "CN"},
            {"action_type": "emotional_attack", "magnitude": "moderate", "actor": "US"},
            {"action_type": "over_concede", "magnitude": "slight", "actor": "CN"},
        ]
        s1 = new_state()
        s2 = new_state()
        apply_round_effects(s1, SCENARIO, effects)
        apply_round_effects(s2, SCENARIO, effects)
        self.assertEqual(s1.indices, s2.indices)

    def test_04_replay_from_log(self):
        """从存档 public_events 重放，得到一致指数（事件溯源，不重复应用）。"""
        st = new_state()
        effects = [
            {"action_type": "firm_stand", "magnitude": "major", "actor": "CN"},
            {"action_type": "diplomatic_ease", "magnitude": "moderate", "actor": "US"},
        ]
        apply_round_effects(st, SCENARIO, effects)
        snapshot = copy.deepcopy(st.indices)
        # 重放：只依据事件流（不重建查表 effects），结果逐位一致
        replay = new_state()
        errors = replay_from_events(replay, st.public_events)
        self.assertEqual(errors, [])
        self.assertEqual(replay.indices, snapshot)

    def test_05_unknown_label_rejected(self):
        """非法标签和非法幅度被 validator 拒绝。"""
        ok, code, _ = validate_effect({"action_type": "huge_concession", "magnitude": "major"}, SCENARIO)
        self.assertFalse(ok)
        self.assertEqual(code, "UNKNOWN_EFFECT_LABEL")
        ok, code, _ = validate_effect({"action_type": "firm_stand", "magnitude": "huge"}, SCENARIO)
        self.assertFalse(ok)
        self.assertEqual(code, "MISSING_MAGNITUDE")
        ok, _, _ = validate_effect({"action_type": "firm_stand", "magnitude": "moderate"}, SCENARIO)
        self.assertTrue(ok)

    def test_06_interest_only_from_clauses(self):
        """只发言、条款无变化时 interest 不变；条款变化后按距离重算。"""
        st = new_state()
        before = st.indices["CN"]["interest"]
        # 口头让步：标签合法但没有任何报价，interest 不变
        apply_round_effects(st, SCENARIO, [
            {"action_type": "conditional_concession", "magnitude": "major", "actor": "CN"}])
        self.assertEqual(st.indices["CN"]["interest"], before)
        self.assertEqual(compute_interest_from_clauses(st, SCENARIO, "CN"), before)
        # 提交接近 CN ideal 的报价，interest 应上升
        st.commit_offer("a1", "CN", {"领海宽度": 12, "群岛国海峡通行强度": 45, "专属经济区宽度": 200})
        refresh_interest(st, SCENARIO)
        after = st.indices["CN"]["interest"]
        self.assertGreater(after, before)

    def test_07_target_direction(self):
        """模型只能影响自己，对方指数不被我方发言改写。"""
        st = new_state()
        cn_before = dict(st.indices["CN"])
        us_before = dict(st.indices["US"])
        apply_round_effects(st, SCENARIO, [
            {"action_type": "cooperative_winwin", "magnitude": "major", "actor": "CN"}])
        self.assertNotEqual(st.indices["CN"], cn_before)   # 自己的 image/trust 变了
        self.assertEqual(st.indices["US"], us_before)       # 对方的指数一字不动

    def test_08_terminal_includes_index_final(self):
        """终局评价包含指数终值维度，且 evaluate() 返回 task_hits 事实。"""
        st = new_state()
        st.commit_offer("a1", "CN", {"领海宽度": 12, "群岛国海峡通行强度": 55, "专属经济区宽度": 200})
        st.commit_offer("a2", "US", {"领海宽度": 12, "群岛国海峡通行强度": 55, "专属经济区宽度": 200})
        st.accept("a3", "CN")
        st.tasks = [{"text": "争取 12 海里写入正文", "priority": "高", "done": True},
                    {"text": "保持形象不破裂", "priority": "中", "done": False}]
        q = evaluate(st, SCENARIO, "CN")["agreement_quality"]
        self.assertIn("index_final", q)
        self.assertEqual(q["index_final"]["CN"]["image"], 50.0)   # 未做发言时保持初值
        hits = evaluate(st, SCENARIO, "CN")["task_hits"]
        self.assertEqual(hits, ["争取 12 海里写入正文"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

# -*- coding: utf-8 -*-
"""成员 C 的规则回归测试 —— 对应手册 5.1「规则测试」与 11.1「终局 / 协议审计」

跑法：  cd C_规则引擎骨架 && python3 -m unittest discover -s tests -v
不依赖任何第三方库，Python 3.9+ 即可。
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.state import NegotiationState            # noqa: E402
from engine.validator import validate_action         # noqa: E402
from engine.terminal import check_terminal, evaluate  # noqa: E402

with open(os.path.join(ROOT, "scenarios", "demo_scenario.json"), encoding="utf-8") as f:
    SCENARIO = json.load(f)


def new_state(**kw):
    st = NegotiationState(session_id="t-001", **kw)
    st.private_state_by_party = {
        "CN": {"hidden_task": "争取 12 海里写入正文"},
        "US": {"hidden_task": "保住海峡自由通行"},
    }
    return st


class TestValidator(unittest.TestCase):
    def test_01_数值超范围被拒且不改状态(self):
        st = new_state()
        before = (st.current_version, len(st.offers))
        ok, code, msg = validate_action(st, {
            "action_type": "offer", "actor": "CN", "action_id": "a1",
            "offer_patch": {"领海宽度": 200},
        }, SCENARIO)
        self.assertFalse(ok)
        self.assertEqual(code, "VALUE_OUT_OF_RANGE")
        self.assertEqual(before, (st.current_version, len(st.offers)))

    def test_02_重复提交被拒(self):
        st = new_state()
        st.commit_offer("a1", "CN", {"领海宽度": 12})
        ok, code, _ = validate_action(st, {
            "action_type": "offer", "actor": "CN", "action_id": "a1",
            "offer_patch": {"领海宽度": 12},
        }, SCENARIO)
        self.assertFalse(ok)
        self.assertEqual(code, "DUPLICATE_ACTION")

    def test_03_版本冲突被拒(self):
        st = new_state()
        st.commit_offer("a1", "CN", {"领海宽度": 12})
        st.commit_offer("a2", "US", {"领海宽度": 6})
        ok, code, _ = validate_action(st, {
            "action_type": "counter_offer", "actor": "US", "action_id": "a3",
            "base_version": 1, "offer_patch": {"领海宽度": 6},
        }, SCENARIO)
        self.assertFalse(ok)
        self.assertEqual(code, "VERSION_CONFLICT")

    def test_04_触碰自己红线被拒(self):
        st = new_state()
        ok, code, _ = validate_action(st, {
            "action_type": "offer", "actor": "CN", "action_id": "a1",
            "offer_patch": {"领海宽度": 6},
        }, SCENARIO)
        self.assertFalse(ok)
        self.assertEqual(code, "REDLINE_VIOLATION")

    def test_05_有未决条款不能接受(self):
        st = new_state()
        st.commit_offer("a1", "US", {"领海宽度": 6})
        st.open_issues = ["履约监督机制"]
        ok, code, _ = validate_action(st, {
            "action_type": "accept", "actor": "CN", "action_id": "a2",
        }, SCENARIO)
        self.assertFalse(ok)
        self.assertEqual(code, "AGREEMENT_HAS_OPEN_ISSUES")


class TestTerminal(unittest.TestCase):
    def test_06_完整协议(self):
        st = new_state()
        st.commit_offer("a1", "CN", {"领海宽度": 12, "群岛国海峡通行强度": 55, "专属经济区宽度": 200})
        st.commit_offer("a2", "US", {"领海宽度": 12, "群岛国海峡通行强度": 55, "专属经济区宽度": 200})
        st.accept("a3", "CN")
        t = check_terminal(st, SCENARIO)
        self.assertEqual(t["terminal_type"], "FULL_AGREEMENT")

        q = evaluate(st, SCENARIO, "CN")["agreement_quality"]
        self.assertTrue(q["redline_ok"])
        self.assertTrue(q["better_than_batna"])

    def test_07_部分协议_有条款没谈就签了(self):
        st = new_state()
        st.commit_offer("a1", "CN", {"领海宽度": 12, "群岛国海峡通行强度": 55})
        st.accept("a2", "US")
        t = check_terminal(st, SCENARIO)
        self.assertEqual(t["terminal_type"], "PARTIAL_AGREEMENT")
        self.assertIn("专属经济区宽度", t["missing_clauses"])

    def test_08_主动退出(self):
        st = new_state()
        st.commit_offer("a1", "CN", {"领海宽度": 12})
        t = check_terminal(st, SCENARIO, {"action_type": "withdraw", "actor": "US"})
        self.assertEqual(t["terminal_type"], "WITHDRAWAL")

    def test_09_僵局(self):
        st = new_state()
        st.advance_round()
        st.advance_round()
        t = check_terminal(st, SCENARIO)
        self.assertEqual(t["terminal_type"], "DEADLOCK")

    def test_10_回合耗尽(self):
        st = new_state(round=13)
        t = check_terminal(st, SCENARIO)
        self.assertEqual(t["terminal_type"], "ROUNDS_EXHAUSTED")

    def test_11_签署触碰红线的协议必须被指出(self):
        st = new_state()
        # 对方版本触碰 CN 红线（领海 6 海里），但仍被接受：审计要能指出具体条款
        st.commit_offer("a1", "US", {"领海宽度": 6, "群岛国海峡通行强度": 80, "专属经济区宽度": 120})
        st.accept("a2", "CN")
        q = evaluate(st, SCENARIO, "CN")["agreement_quality"]
        self.assertFalse(q["redline_ok"])
        self.assertEqual(q["redline_violations"][0]["clause"], "领海宽度")


class TestIsolation(unittest.TestCase):
    def test_12_状态快照不外泄对方底牌(self):
        st = new_state()
        pub = st.to_public_dict("CN")
        blob = json.dumps(pub, ensure_ascii=False)
        self.assertIn("12 海里写入正文", blob)      # 自己的能看到
        self.assertNotIn("保住海峡自由通行", blob)  # 对方的看不到


if __name__ == "__main__":
    unittest.main(verbosity=2)

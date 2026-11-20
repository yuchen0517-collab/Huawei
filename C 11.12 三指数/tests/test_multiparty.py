"""三方及以上协议合并回归。

三方场景 fixture 只保留两个条款：一个 enum（覆盖 a/b/c 分数），
一个 numeric（a 的 ideal > redline，b 的 ideal < redline，c 宽松）。
不写 index_rules，image / trust 走默认 50，结算只影响 interest。
"""

import unittest

from engine import RulesEngine
from tests import full_engine, submit


def multiparty_scenario(parties=("a", "b", "c")) -> dict:
    return {
        "scenario_id": "multiparty-fixture",
        "title": "三方及以上协议合并回归",
        "max_rounds": 6,
        "deadlock_rounds": 2,
        "action_points_per_round": 8,
        "parties": [
            {"id": party, "batna": 40 + index, "private": {}}
            for index, party in enumerate(parties)
        ],
        "clauses": [
            {
                "name": "算力配额",
                "type": "enum",
                "options": [
                    {"id": "共享池", "score": {"a": 0.9, "b": 0.2, "c": 0.5}},
                    {"id": "双边协定", "score": {"a": 0.2, "b": 0.9, "c": 0.5}},
                    {"id": "市场竞价", "score": {"a": 0.5, "b": 0.5, "c": 0.9}},
                ],
                "initial": "共享池",
                "weights": {"a": 0.6, "b": 0.4, "c": 0.4},
            },
            {
                "name": "模型评测门槛",
                "type": "numeric",
                "range": [0, 100],
                "initial": 50,
                "weights": {"a": 0.4, "b": 0.6, "c": 0.6},
                "positions": {
                    "a": {"ideal": 80, "redline": 30},
                    "b": {"ideal": 20, "redline": 70},
                    "c": {"ideal": 50},
                },
            },
        ],
        "terminal_rules": {"accept_requires_no_open_issues": True},
    }


def multiparty_engine(parties=("a", "b", "c")) -> RulesEngine:
    return RulesEngine(multiparty_scenario(parties), session_id="mp-test")


class MultipartyAcceptTest(unittest.TestCase):
    def test_third_party_clause_survives_accept(self):
        """核心回归：a 接受时，c 报过的条款不能被整体丢弃。"""
        engine = multiparty_engine()
        ok, code, message, _ = submit(
            engine,
            action_id="mp-a-offer",
            actor="a",
            patch={"算力配额": "共享池"},
        )
        self.assertTrue(ok, f"{code}: {message}")
        ok, code, message, _ = submit(
            engine,
            action_id="mp-b-offer",
            actor="b",
            patch={"算力配额": "共享池"},
        )
        self.assertTrue(ok, f"{code}: {message}")
        ok, code, message, _ = submit(
            engine,
            action_id="mp-c-offer",
            actor="c",
            patch={"模型评测门槛": 42},
        )
        self.assertTrue(ok, f"{code}: {message}")

        ok, code, message, _ = submit(
            engine, action_id="mp-a-accept", actor="a", action_type="accept"
        )
        self.assertTrue(ok, f"{code}: {message}")

        agreement = engine.state.agreement
        self.assertIsNotNone(agreement)
        self.assertIn("模型评测门槛", agreement.clauses)
        self.assertEqual(agreement.clauses["模型评测门槛"]["option"], 42)
        self.assertIn("算力配额", agreement.clauses)
        self.assertEqual(agreement.clauses["算力配额"]["option"], "共享池")

    def test_two_party_flow_is_unchanged(self):
        """两方金标准：full_engine 的 agreement 逐字段不变，conditions 为空。"""
        engine = full_engine()
        agreement = engine.state.agreement
        self.assertIsNotNone(agreement)
        self.assertEqual(
            {name: entry["option"] for name, entry in agreement.clauses.items()},
            {
                "全球算力资源分配": "附带可核查机制",
                "数据跨境流动": "白名单互认",
                "前沿模型评测门槛": 45,
            },
        )
        for name, entry in agreement.clauses.items():
            with self.subTest(clause=name):
                self.assertEqual(set(entry), {"option", "note"})
                self.assertEqual(entry["note"], "测试")
        self.assertEqual(agreement.conditions, [])

    def test_accept_rejected_when_a_party_has_not_offered(self):
        """有参与方未报价时不得接受一份把它排除在外的协议。"""
        engine = multiparty_engine()
        ok, code, message, _ = submit(
            engine,
            action_id="silent-a-offer",
            actor="a",
            patch={"算力配额": "共享池"},
        )
        self.assertTrue(ok, f"{code}: {message}")
        ok, code, message, _ = submit(
            engine,
            action_id="silent-b-offer",
            actor="b",
            patch={"算力配额": "共享池"},
        )
        self.assertTrue(ok, f"{code}: {message}")

        ok, code, message, _ = submit(
            engine, action_id="silent-a-accept", actor="a", action_type="accept"
        )
        self.assertFalse(ok)
        self.assertEqual(code, "NO_COUNTERPART_OFFER")
        self.assertIsNone(engine.state.agreement)

    def test_all_party_conditions_are_merged_without_duplicates(self):
        """三方各自带条件：accept 后三方条件都在且无重复。"""
        engine = multiparty_engine()
        offers = (
            ("cond-a-offer", "a", {"算力配额": "共享池"}, ["甲条件"]),
            ("cond-b-offer", "b", {"算力配额": "共享池"}, ["乙条件"]),
            ("cond-c-offer", "c", {"模型评测门槛": 42}, ["丙条件"]),
        )
        for action_id, actor, patch, conditions in offers:
            ok, code, message, _ = submit(
                engine,
                action_id=action_id,
                actor=actor,
                patch=patch,
                conditions=conditions,
            )
            self.assertTrue(ok, f"{code}: {message}")

        ok, code, message, _ = submit(
            engine, action_id="cond-a-accept", actor="a", action_type="accept"
        )
        self.assertTrue(ok, f"{code}: {message}")

        conditions = engine.state.agreement.conditions
        self.assertEqual(set(conditions), {"甲条件", "乙条件", "丙条件"})
        self.assertEqual(len(conditions), len(set(conditions)))

    def test_five_party_accept_does_not_raise_and_covers_all(self):
        """五方：在 fixture 上加 d / e，accept 正常终局且 coverage=1.0。"""
        engine = multiparty_engine(("a", "b", "c", "d", "e"))
        offers = (
            ("five-a-offer", "a", {"算力配额": "共享池"}),
            ("five-b-offer", "b", {"算力配额": "共享池"}),
            ("five-c-offer", "c", {"模型评测门槛": 42}),
            ("five-d-offer", "d", {"模型评测门槛": 42}),
            ("five-e-offer", "e", {"模型评测门槛": 42}),
        )
        for action_id, actor, patch in offers:
            ok, code, message, _ = submit(
                engine, action_id=action_id, actor=actor, patch=patch
            )
            self.assertTrue(ok, f"{code}: {message}")

        ok, code, message, _ = submit(
            engine, action_id="five-a-accept", actor="a", action_type="accept"
        )
        self.assertTrue(ok, f"{code}: {message}")
        self.assertEqual(engine.state.terminal["type"], "FULL_AGREEMENT")
        self.assertEqual(engine.state.terminal["coverage"], 1.0)


if __name__ == "__main__":
    unittest.main()
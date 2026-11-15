"""TurnScheduler 确定性调度测试。

覆盖：顺序确定性、声明顺序起点、两方交替、五方轮转、行动点预算、
末回合边界、max_rounds 默认值、describe() 无泄露、不修改引擎状态。
"""

from __future__ import annotations

import json
import os
import unittest
from copy import deepcopy

from engine import RulesEngine
from engine.scheduler import TurnScheduler
from load_scenario_bridge import convert_b_scenario

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B_SCENARIO_PATH = os.path.join(ROOT, "scenarios", "from_b_chip_controls.json")


def load_b_raw() -> dict:
    with open(B_SCENARIO_PATH, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def b_scenario() -> dict:
    return convert_b_scenario(load_b_raw())


def five_party_scenario(max_rounds: int = 7) -> dict:
    return {
        "scenario_id": "multi-5",
        "parties": [{"id": f"p{index}"} for index in range(1, 6)],
        "max_rounds": max_rounds,
        "action_points_per_round": 2,
    }


class SpeakingOrderTest(unittest.TestCase):
    def test_speaking_order_is_deterministic(self):
        """同一输入两次调用、两个实例调用都必须完全一致（无随机/时间依赖）。"""
        first = TurnScheduler(b_scenario())
        second = TurnScheduler(b_scenario())
        for round_no in (1, 2, 3, 8, 99):
            with self.subTest(round=round_no):
                self.assertEqual(
                    first.speaking_order(round_no), first.speaking_order(round_no)
                )
                self.assertEqual(
                    first.speaking_order(round_no), second.speaking_order(round_no)
                )

    def test_speaking_order_starts_from_declared_first_party(self):
        """第 1 回合必须严格等于 parties 声明顺序。"""
        scheduler = TurnScheduler(b_scenario())
        self.assertEqual(scheduler.speaking_order(1), ["cn", "us"])

    def test_two_party_alternates_by_round(self):
        """两方场景：奇数轮 cn 先、偶数轮 us 先，严格交替。"""
        scheduler = TurnScheduler(b_scenario())
        expected = {
            1: ["cn", "us"],
            2: ["us", "cn"],
            3: ["cn", "us"],
            4: ["us", "cn"],
        }
        for round_no, order in expected.items():
            with self.subTest(round=round_no):
                self.assertEqual(scheduler.speaking_order(round_no), order)

    def test_five_party_rotates_start_position(self):
        """多边 1v5：5 个回合构成完整轮转周期，每回合都是循环移位。"""
        scheduler = TurnScheduler(five_party_scenario())
        parties = ["p1", "p2", "p3", "p4", "p5"]
        starts = []
        for round_no in range(1, 6):
            order = scheduler.speaking_order(round_no)
            with self.subTest(round=round_no):
                self.assertEqual(sorted(order), parties)
                start = parties.index(order[0])
                starts.append(start)
                self.assertEqual(
                    order, parties[start:] + parties[:start], "必须是循环移位"
                )
        self.assertEqual(starts, [0, 1, 2, 3, 4])
        # 第 6 回合回到周期起点。
        self.assertEqual(scheduler.speaking_order(6), parties)


class ActionBudgetTest(unittest.TestCase):
    def test_action_budget_reads_scenario_int(self):
        scheduler = TurnScheduler(b_scenario())
        for party in ("cn", "us"):
            for round_no in (1, 2, 8):
                with self.subTest(party=party, round=round_no):
                    self.assertEqual(scheduler.action_budget(party, round_no), 3)

    def test_action_budget_supports_per_party_mapping(self):
        scenario = five_party_scenario()
        scenario["action_points_per_round"] = {"p1": 4, "p2": 3, "P3": 2}
        scheduler = TurnScheduler(scenario)
        self.assertEqual(scheduler.action_budget("p1", 1), 4)
        self.assertEqual(scheduler.action_budget("p2", 1), 3)
        self.assertEqual(scheduler.action_budget("p3", 1), 2)

    def test_action_budget_unknown_party_returns_zero(self):
        scenario = five_party_scenario()
        scenario["action_points_per_round"] = {"p1": 4}
        scheduler = TurnScheduler(scenario)
        self.assertEqual(scheduler.action_budget("root", 1), 0)

    def test_is_last_round_boundary(self):
        scheduler = TurnScheduler(five_party_scenario(max_rounds=7))
        self.assertFalse(scheduler.is_last_round(6))
        self.assertTrue(scheduler.is_last_round(7))
        self.assertTrue(scheduler.is_last_round(8))

    def test_max_rounds_defaults_to_twelve(self):
        scenario = five_party_scenario()
        scenario.pop("max_rounds")
        scheduler = TurnScheduler(scenario)
        self.assertEqual(scheduler.max_rounds, 12)
        self.assertTrue(scheduler.is_last_round(12))
        self.assertFalse(scheduler.is_last_round(11))

    def test_describe_matches_scheduler_fields(self):
        scheduler = TurnScheduler(five_party_scenario(max_rounds=7))
        described = scheduler.describe()
        self.assertEqual(described["parties"], ["p1", "p2", "p3", "p4", "p5"])
        self.assertEqual(described["party_count"], 5)
        self.assertEqual(described["max_rounds"], 7)
        self.assertEqual(described["action_points_per_round"], 2)
        self.assertEqual(described["last_round"], 7)


class IsolationAndPurityTest(unittest.TestCase):
    def test_describe_has_no_private_fields(self):
        """describe() 是面向 UI / 复盘的只读摘要，不得出现任何底牌叙述。"""
        raw = load_b_raw()
        scheduler = TurnScheduler(b_scenario())
        rendered = json.dumps(scheduler.describe(), ensure_ascii=False)
        for key in ("hidden_task", "batna", "redline", "goals", "private"):
            self.assertNotIn(key, rendered)
        for secret in (
            raw["private_state_by_party"]["cn"]["hidden_task"],
            raw["private_state_by_party"]["us"]["hidden_task"],
            raw["private_state_by_party"]["us"]["batna"]["description"],
            raw["private_state_by_party"]["us"]["batna"]["basis"],
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, rendered)

    def test_scheduler_does_not_mutate_engine_state(self):
        """调度器全程只读：调用任意方法后引擎状态逐字段不变。"""
        engine = RulesEngine(b_scenario(), session_id="scheduler-purity")
        scheduler = TurnScheduler(engine.scenario)
        before = {
            "round": engine.state.round,
            "phase": engine.state.phase,
            "action_points": engine.state.action_points,
            "indices": deepcopy(engine.state.indices),
            "events": len(engine.state.public_events),
            "behavior": len(engine.state.behavior_log),
            "offers": len(engine.state.offers),
            "private": deepcopy(engine.state.private_state_by_party),
        }
        scheduler.speaking_order(3)
        scheduler.action_budget("cn", 3)
        scheduler.is_last_round(3)
        scheduler.describe()
        after = {
            "round": engine.state.round,
            "phase": engine.state.phase,
            "action_points": engine.state.action_points,
            "indices": engine.state.indices,
            "events": len(engine.state.public_events),
            "behavior": len(engine.state.behavior_log),
            "offers": len(engine.state.offers),
            "private": engine.state.private_state_by_party,
        }
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
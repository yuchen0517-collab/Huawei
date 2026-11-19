"""工作流编排状态机回归。

覆盖：完整一局、复盘闸门、非法迁移、失败动作零推进、trace 四段结构、
以及「编排器没有复制引擎状态」的强证明。
"""

import unittest

from engine import IllegalDebriefAccess, RulesEngine, load_scenario
from engine.orchestrator import (
    BARGAINING,
    DEBRIEF,
    IllegalWorkflowTransition,
    NegotiationOrchestrator,
)
from run_workflow import SCENARIO_PATH, workflow_rounds
from tests import make_engine


def new_engine(session_id: str = "orchestrator-test") -> RulesEngine:
    return RulesEngine(load_scenario(SCENARIO_PATH), session_id=session_id)


def started_orchestrator(engine=None):
    engine = engine or new_engine()
    orchestrator = NegotiationOrchestrator(engine)
    orchestrator.confirm()
    orchestrator.begin()
    return orchestrator


class CompleteRunTest(unittest.TestCase):
    def test_full_workflow_reaches_expected_terminal(self):
        engine = new_engine()
        orchestrator = NegotiationOrchestrator(engine)
        trace = orchestrator.run(workflow_rounds(), requester="moderator")

        self.assertEqual(trace["terminal"]["type"], "FULL_AGREEMENT")
        self.assertEqual(trace["terminal"]["coverage"], 1.0)
        self.assertEqual(orchestrator.state, DEBRIEF)
        self.assertEqual(trace["debrief"]["requester"], "moderator")


class DebriefGateTest(unittest.TestCase):
    def test_debrief_before_terminal_raises_engine_gate(self):
        orchestrator = started_orchestrator()
        with self.assertRaises(IllegalDebriefAccess):
            orchestrator.debrief("moderator")
        self.assertEqual(orchestrator.state, BARGAINING)

    def test_debrief_without_requester_raises_engine_gate(self):
        engine = new_engine()
        orchestrator = NegotiationOrchestrator(engine)
        orchestrator.run(workflow_rounds(), requester="moderator")
        # 已进入 debrief；再开一局验证空 requester 的闸门。
        second = NegotiationOrchestrator(new_engine("debrief-empty"))
        second.confirm()
        second.begin()
        second.finish()
        with self.assertRaises(IllegalDebriefAccess):
            second.debrief("")


class IllegalTransitionTest(unittest.TestCase):
    def test_cannot_begin_before_confirm(self):
        orchestrator = NegotiationOrchestrator(make_engine())
        with self.assertRaises(IllegalWorkflowTransition):
            orchestrator.begin()

    def test_cannot_confirm_twice(self):
        orchestrator = NegotiationOrchestrator(make_engine())
        orchestrator.confirm()
        with self.assertRaises(IllegalWorkflowTransition):
            orchestrator.confirm()

    def test_cannot_submit_after_terminal(self):
        engine = new_engine()
        orchestrator = NegotiationOrchestrator(engine)
        orchestrator.run(workflow_rounds(), requester="moderator")
        with self.assertRaises(IllegalWorkflowTransition):
            orchestrator.submit_action(
                {
                    "action_id": "late",
                    "actor": "cn",
                    "action_type": "statement",
                    "card_id": None,
                    "offer_patch": {},
                    "conditions": [],
                    "expected_effect": "终局后提交",
                    "public_message": "终局后提交。",
                }
            )


class FailedActionTest(unittest.TestCase):
    def test_rejected_action_does_not_advance(self):
        orchestrator = started_orchestrator()
        engine = orchestrator.engine
        before = {
            "state": orchestrator.state,
            "version": engine.state.current_version,
            "points": engine.state.action_points,
            "events": len(engine.state.public_events),
            "transitions": len(orchestrator.transitions),
        }
        ok, code, _, _ = orchestrator.submit_action(
            {
                "action_id": "bad-option",
                "actor": "cn",
                "action_type": "offer",
                "card_id": None,
                "offer_patch": {
                    "全球算力资源分配": {"option": "不存在的选项", "note": "非法"}
                },
                "conditions": [],
                "expected_effect": "非法行动",
                "public_message": "非法行动。",
            }
        )
        self.assertFalse(ok)
        self.assertEqual(code, "UNKNOWN_OPTION")
        self.assertEqual(orchestrator.state, BARGAINING)
        self.assertEqual(engine.state.current_version, before["version"])
        self.assertEqual(engine.state.action_points, before["points"])
        self.assertEqual(len(engine.state.public_events), before["events"])
        self.assertEqual(len(orchestrator.transitions), before["transitions"])


class TraceStructureTest(unittest.TestCase):
    def test_trace_contains_required_sections(self):
        orchestrator = NegotiationOrchestrator(new_engine())
        trace = orchestrator.run(workflow_rounds(), requester="moderator")

        for key in ("actions", "rounds", "transitions", "terminal", "audit"):
            with self.subTest(key=key):
                self.assertIn(key, trace)

        self.assertTrue(trace["actions"])
        for item in trace["actions"]:
            self.assertEqual(
                set(item), {"round", "action_id", "actor", "action_type", "ok", "code"}
            )
        self.assertEqual(len(trace["rounds"]), 2)
        for bucket in trace["rounds"]:
            self.assertEqual(set(bucket), {"round", "order", "actions"})
            self.assertTrue(bucket["actions"])

        self.assertEqual(trace["transitions"][0]["from"], "opening")
        self.assertEqual(trace["transitions"][0]["to"], "confirmed")
        self.assertEqual(trace["transitions"][-1]["to"], "debrief")
        for before, after in zip(trace["transitions"], trace["transitions"][1:]):
            self.assertEqual(before["to"], after["from"])

        self.assertEqual(trace["terminal"]["type"], "FULL_AGREEMENT")
        self.assertEqual(trace["terminal"]["coverage"], 1.0)
        self.assertEqual(trace["audit"]["summary"], {"blocking": 0, "warning": 0})


class StateParityTest(unittest.TestCase):
    def test_orchestrated_state_equals_direct_engine(self):
        """同一脚本下，编排器与直接调 RulesEngine 的存档态必须逐字段一致。"""
        rounds = workflow_rounds()

        orchestrated = new_engine("parity-session")
        NegotiationOrchestrator(orchestrated).run(rounds, requester="moderator")

        direct = new_engine("parity-session")
        for index, actions in enumerate(rounds):
            for item in actions:
                ok, code, message, _ = direct.submit_action(item)
                self.assertTrue(ok, f"{code}: {message}")
            if direct.state.status != "ended" and index < len(rounds) - 1:
                direct.next_round()
        if direct.state.status != "ended":
            direct.finish()

        self.assertEqual(
            orchestrated.state.to_archive_dict(), direct.state.to_archive_dict()
        )


if __name__ == "__main__":
    unittest.main()
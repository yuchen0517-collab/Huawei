"""B 契约 1.1：runtime / deadlock_rounds / terminal_rules 三布尔 / initial_ref 测试。"""

import json
import os
import unittest
from copy import deepcopy

from adapter import ScenarioContractError, adapt_scenario, adapt_scenario_with_warnings
from engine import RulesEngine
from tests import make_action

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B_SCENARIO_PATH = os.path.join(ROOT, "scenarios", "from_b_chip_controls.json")


def b_scenario() -> dict:
    with open(B_SCENARIO_PATH, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def clause_by_name(scenario: dict, name: str) -> dict:
    for clause in scenario["clauses"]:
        if clause["name"] == name:
            return clause
    raise AssertionError(f"条款 {name!r} 不存在")


def submit(engine, action_id, actor, action_type, patch=None):
    return engine.submit_action(
        make_action(
            action_id=action_id,
            actor=actor,
            action_type=action_type,
            patch=patch,
        )
    )


class RuntimeTest(unittest.TestCase):
    def test_action_points_explicit_value_applied(self):
        source = b_scenario()
        source["runtime"] = {"action_points_per_round": 5}
        scenario = adapt_scenario(source)
        self.assertEqual(scenario["action_points_per_round"], 5)
        engine = RulesEngine(scenario, session_id="runtime-5")
        self.assertEqual(engine.state.action_points, 5)
        ok, code, message, _ = submit(
            engine, "probe-1", "cn", "statement"
        )
        self.assertTrue(ok, f"{code}: {message}")
        self.assertEqual(engine.state.action_points, 4)
        engine.next_round()
        self.assertEqual(engine.state.action_points, 5)

    def test_action_points_defaulted_with_warning(self):
        source = b_scenario()
        scenario, warnings = adapt_scenario_with_warnings(source)
        self.assertEqual(scenario["action_points_per_round"], 3)
        self.assertIn(
            "RUNTIME_ACTION_POINTS_DEFAULTED",
            {item["code"] for item in warnings},
        )

    def test_action_points_out_of_range_raises(self):
        for value in (0, 6, 2.5, True):
            with self.subTest(value=value):
                source = b_scenario()
                source["runtime"] = {"action_points_per_round": value}
                with self.assertRaises(ScenarioContractError) as context:
                    adapt_scenario(source)
                self.assertIn("action_points_per_round", str(context.exception))


class DeadlockRoundsTest(unittest.TestCase):
    def test_deadlock_rounds_explicit_value_applied(self):
        source = b_scenario()
        source["terminal_rules"]["deadlock_rounds"] = 4
        scenario = adapt_scenario(source)
        self.assertEqual(scenario["deadlock_rounds"], 4)
        engine = RulesEngine(scenario, session_id="deadlock-4")
        for _ in range(3):
            result = engine.next_round()
            self.assertIsNone(result["terminal"])
        result = engine.next_round()
        self.assertEqual(result["terminal"]["type"], "DEADLOCK")

    def test_deadlock_rounds_must_not_exceed_max_rounds(self):
        source = b_scenario()
        source["max_rounds"] = 5
        source["terminal_rules"]["deadlock_rounds"] = 6
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("不得大于 max_rounds", str(context.exception))

    def test_deadlock_rounds_out_of_range_raises(self):
        for value in (1, 11, "3", True):
            with self.subTest(value=value):
                source = b_scenario()
                source["max_rounds"] = 12
                source["terminal_rules"]["deadlock_rounds"] = value
                with self.assertRaises(ScenarioContractError) as context:
                    adapt_scenario(source)
                self.assertIn("deadlock_rounds", str(context.exception))


class TerminalBooleansTest(unittest.TestCase):
    def test_missing_allow_walk_away_raises(self):
        source = b_scenario()
        del source["terminal_rules"]["allow_walk_away"]
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("allow_walk_away", str(context.exception))

    def test_missing_partial_agreement_allowed_raises(self):
        source = b_scenario()
        del source["terminal_rules"]["partial_agreement_allowed"]
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("partial_agreement_allowed", str(context.exception))

    def test_missing_accept_rule_raises(self):
        source = b_scenario()
        del source["terminal_rules"]["accept_requires_no_open_issue"]
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("accept_requires_no_open_issue", str(context.exception))

    def test_non_boolean_is_contract_error(self):
        for value in ("true", 1, 0, None):
            with self.subTest(value=value):
                source = b_scenario()
                source["terminal_rules"]["allow_walk_away"] = value
                with self.assertRaises(ScenarioContractError) as context:
                    adapt_scenario(source)
                self.assertIn("必须", str(context.exception))

    def test_partial_false_blocks_explicit_partial_finish(self):
        source = b_scenario()
        self.assertFalse(source["terminal_rules"]["partial_agreement_allowed"])
        engine = RulesEngine(adapt_scenario(source), session_id="partial-false")
        submit(engine, "cn-one", "cn", "offer", {"受管制先进制程门槛": 14})
        terminal = engine.finish("PARTIAL_AGREEMENT")
        self.assertEqual(terminal["type"], "DEADLOCK")

    def test_partial_false_blocks_accept_with_open_issues(self):
        source = b_scenario()
        engine = RulesEngine(adapt_scenario(source), session_id="partial-accept")
        submit(engine, "u1", "us", "offer", {"受管制先进制程门槛": 14})
        ok, code, _, _ = submit(engine, "c2", "cn", "accept")
        self.assertFalse(ok)
        self.assertEqual(code, "AGREEMENT_HAS_OPEN_ISSUES")

    def test_partial_true_has_independent_finish_trigger(self):
        """partial_allowed=true 且 accept_requires=true 时，finish() 仍可产出部分协议。"""
        source = b_scenario()
        source["terminal_rules"]["partial_agreement_allowed"] = True
        self.assertTrue(source["terminal_rules"]["accept_requires_no_open_issue"])
        engine = RulesEngine(adapt_scenario(source), session_id="partial-true")
        submit(engine, "cn-one", "cn", "offer", {"受管制先进制程门槛": 14})
        terminal = engine.finish()
        self.assertEqual(terminal["type"], "PARTIAL_AGREEMENT")


class ExplicitInitialTest(unittest.TestCase):
    def test_numeric_initial_takes_precedence(self):
        source = b_scenario()
        source["issues"][0]["initial"] = 20
        scenario = adapt_scenario(source)
        self.assertEqual(
            clause_by_name(scenario, "受管制先进制程门槛")["initial"], 20.0
        )

    def test_enumerated_initial_takes_precedence(self):
        source = b_scenario()
        source["issues"][2]["initial"] = "bilateral"
        scenario = adapt_scenario(source)
        self.assertEqual(
            clause_by_name(scenario, "争端解决渠道")["initial"], "bilateral"
        )

    def test_numeric_initial_out_of_range_raises(self):
        source = b_scenario()
        source["issues"][0]["initial"] = 99
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("不在", str(context.exception))

    def test_numeric_initial_not_step_multiple_raises(self):
        source = b_scenario()
        # range [7,28] step 1：14.5 在范围内，但不是 step 的整数倍。
        source["issues"][0]["initial"] = 14.5
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("step", str(context.exception))

    def test_initial_ref_resolves_and_is_preserved(self):
        source = b_scenario()
        source["issues"][0]["initial"] = 14
        source["issues"][0]["initial_ref"] = "A1"
        scenario, warnings = adapt_scenario_with_warnings(source)
        clause = clause_by_name(scenario, "受管制先进制程门槛")
        self.assertEqual(clause["initial_ref"], "A1")
        self.assertIn(
            "INITIAL_REF_RESOLVED", {item["code"] for item in warnings}
        )

    def test_initial_ref_unresolvable_raises(self):
        source = b_scenario()
        source["issues"][0]["initial"] = 14
        source["issues"][0]["initial_ref"] = "A9"
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("initial_ref", str(context.exception))

    def test_initial_ref_non_string_raises(self):
        source = b_scenario()
        source["issues"][0]["initial"] = 14
        source["issues"][0]["initial_ref"] = 123
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("initial_ref", str(context.exception))


if __name__ == "__main__":
    unittest.main()
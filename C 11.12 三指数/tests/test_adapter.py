"""场景契约适配层测试：字段映射、效用推导、红线映射、端到端与信息隔离。"""

import json
import os
import tempfile
import unittest
from copy import deepcopy

from adapter import (
    ScenarioContractError,
    adapt_scenario,
    adapt_scenario_with_warnings,
    load_and_adapt,
    validate_b_contract,
)
from adapter.scenario_adapter import DEFAULT_INDEX_RULES
from engine import RulesEngine, load_scenario
from engine.indices import initial_plan, score, utility
from engine.validator import is_redline_violation, soft_redline_violations
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


class AdapterMappingTest(unittest.TestCase):
    def setUp(self):
        self.source = b_scenario()
        self.adapted = adapt_scenario(self.source)

    def test_party_fields_mapped_and_lowercased(self):
        cn = self.adapted["parties"][0]
        self.assertEqual(cn["id"], "cn")
        self.assertEqual(cn["role"], "中国代表团团长")
        self.assertEqual(cn["batna"], 30)
        self.assertEqual(cn["public_position"], self.source["parties"][0]["public_position"])
        self.assertEqual(
            cn["private"]["bottom_line"],
            self.source["private_state_by_party"]["cn"]["hidden_task"],
        )
        self.assertIn("产业备份产能", cn["private"]["batna_note"])
        self.assertEqual(
            cn["private"]["priority_ranking"],
            self.source["private_state_by_party"]["cn"]["priority_ranking"],
        )

    def test_assumptions_keep_ids(self):
        self.assertEqual(len(self.adapted["assumptions"]), 2)
        self.assertTrue(self.adapted["assumptions"][0].startswith("[A1] "))

    def test_assumptions_detail_preserved(self):
        detail = self.adapted["assumptions_detail"]
        self.assertEqual(len(detail), 2)
        self.assertEqual(detail[0]["assumption_id"], "A1")
        self.assertEqual(
            detail[0]["affects"],
            ["export_license_scope", "license_validity_months"],
        )
        self.assertEqual(
            self.adapted["assumptions"][0], f"[A1] {detail[0]['text']}"
        )

    def test_enum_ranked_scores_edge_target(self):
        forum = clause_by_name(self.adapted, "争端解决渠道")
        scores = {item["id"]: item["score"]["cn"] for item in forum["options"]}
        self.assertEqual(scores, {"wto": 1.0, "bilateral": 0.5, "unilateral": 0.0})

    def test_enum_ranked_scores_centered_target(self):
        forum = clause_by_name(self.adapted, "争端解决渠道")
        scores = {item["id"]: item["score"]["us"] for item in forum["options"]}
        self.assertEqual(scores, {"wto": 0.5, "bilateral": 1.0, "unilateral": 0.5})

    def test_numeric_higher_better_scores(self):
        scope = clause_by_name(self.adapted, "受管制先进制程门槛")
        self.assertEqual(scope["positions"]["cn"]["ideal"], 28.0)
        self.assertEqual(score(scope, 28, "cn"), 1.0)
        self.assertEqual(score(scope, 7, "cn"), 0.0)
        self.assertAlmostEqual(score(scope, 17.5, "cn"), 0.5, places=6)

    def test_numeric_lower_better_scores(self):
        scope = clause_by_name(self.adapted, "受管制先进制程门槛")
        self.assertEqual(scope["positions"]["us"]["ideal"], 14.0)
        self.assertEqual(score(scope, 14, "us"), 1.0)
        self.assertAlmostEqual(score(scope, 28, "us"), 1.0 / 3.0, places=6)
        self.assertLess(score(scope, 28, "us"), score(scope, 14, "us"))

    def test_enum_redline_in_is_inverted(self):
        forum = clause_by_name(self.adapted, "争端解决渠道")
        self.assertEqual(forum["redlines"]["cn"], ["unilateral"])
        self.assertEqual(forum["redlines"]["us"], ["wto"])

    def test_numeric_redline_direction_explicit(self):
        scope = clause_by_name(self.adapted, "受管制先进制程门槛")
        self.assertEqual(scope["positions"]["cn"]["redline"], 14.0)
        self.assertEqual(
            scope["positions"]["cn"]["redline_direction"], "below_is_violation"
        )
        self.assertEqual(scope["positions"]["us"]["redline"], 21.0)
        self.assertEqual(
            scope["positions"]["us"]["redline_direction"], "above_is_violation"
        )

    def test_terminal_rules_mapped(self):
        self.assertEqual(
            self.adapted["terminal_rules"],
            {
                "allow_walk_away": False,
                "accept_requires_no_open_issues": True,
                "partial_agreement_allowed": False,
            },
        )
        self.assertFalse(self.adapted["allow_accept_with_open_issues"])
        self.assertEqual(self.adapted["deadlock_rounds"], 2)
        self.assertEqual(self.adapted["action_points_per_round"], 3)
        self.assertIn("image_actions", self.adapted["index_rules"])

    def test_weights_sum_to_one(self):

        cn_total = sum(clause["weights"]["cn"] for clause in self.adapted["clauses"])
        us_total = sum(clause["weights"]["us"] for clause in self.adapted["clauses"])
        self.assertAlmostEqual(cn_total, 1.0, places=6)
        self.assertAlmostEqual(us_total, 1.0, places=6)


class AdapterContractTest(unittest.TestCase):
    def test_validate_returns_error_list(self):
        errors = validate_b_contract({"scenario_id": "x"})
        self.assertIsInstance(errors, list)
        self.assertTrue(errors)
        self.assertTrue(any("issues" in item for item in errors))

    def test_missing_terminal_rules_raises(self):
        source = b_scenario()
        del source["terminal_rules"]
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("terminal_rules", str(context.exception))

    def test_illegal_issue_type_raises(self):
        source = b_scenario()
        source["issues"][0]["type"] = "boolean"
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("issues[0].type", str(context.exception))

    def test_duplicate_clause_name_raises(self):
        source = b_scenario()
        source["issues"][1]["name"] = source["issues"][0]["name"]
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("重复", str(context.exception))

    def test_assumption_normalized_with_warning(self):
        source = b_scenario()
        source["scenario_type"] = "assumption"
        scenario, warnings = _adapt_with_warnings(source)
        self.assertEqual(scenario["scenario_type"], "hypothesis")
        self.assertTrue(
            any(item["code"] == "SCENARIO_TYPE_NORMALIZED" for item in warnings)
        )

    def test_weight_imbalance_normalized_with_warning(self):
        source = b_scenario()
        goals = source["private_state_by_party"]["cn"]["goals"]
        goals[0]["weight"] = 0.6
        goals[1]["weight"] = 0.5
        goals[2]["weight"] = 0.25
        scenario, warnings = _adapt_with_warnings(source)
        self.assertTrue(
            any(item["code"] == "WEIGHT_NORMALIZED" for item in warnings)
        )
        total = sum(clause["weights"]["cn"] for clause in scenario["clauses"])
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_warnings_are_structured_dicts(self):
        _, warnings = load_and_adapt(B_SCENARIO_PATH)
        self.assertTrue(warnings)
        for item in warnings:
            self.assertEqual(set(item), {"code", "field", "message"})
            self.assertTrue(item["code"])
            self.assertTrue(item["field"])

    def test_bom_file_can_be_loaded(self):
        payload = json.dumps(b_scenario(), ensure_ascii=False)
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        handle.close()
        try:
            with open(handle.name, "w", encoding="utf-8-sig") as target:
                target.write(payload)
            scenario, warnings = load_and_adapt(handle.name)
            self.assertEqual(scenario["scenario_id"], "scn_chip_001")
            self.assertTrue(warnings)
        finally:
            os.unlink(handle.name)

    def test_default_index_rules_matches_demo_scenario(self):
        demo = load_scenario(os.path.join(ROOT, "scenarios", "demo_scenario.json"))
        self.assertEqual(DEFAULT_INDEX_RULES, demo["index_rules"])

    def test_input_index_rules_preserved(self):
        source = b_scenario()
        custom = {
            "scale": [0, 100],
            "initial": {"cn": {"image": 70, "trust": 30}},
            "sensitivity": {"cn": {"image": 1.0, "trust": 1.0}},
            "image_actions": {"procedural": {"slight": 9, "moderate": 9, "major": 9}},
            "trust_actions": {"procedural": {"slight": 9, "moderate": 9, "major": 9}},
        }
        source["index_rules"] = custom
        scenario, warnings = adapt_scenario_with_warnings(source)
        self.assertEqual(scenario["index_rules"], custom)
        self.assertTrue(
            any(item["code"] == "INDEX_RULES_PRESERVED" for item in warnings)
        )
        self.assertFalse(
            any(item["code"] == "DEFAULT_INDEX_RULES" for item in warnings)
        )

    def test_explicit_initial_takes_precedence(self):
        source = b_scenario()
        source["issues"][0]["initial"] = 20
        source["issues"][2]["initial"] = "bilateral"
        scenario, warnings = _adapt_with_warnings(source)
        self.assertEqual(
            clause_by_name(scenario, "受管制先进制程门槛")["initial"], 20.0
        )
        self.assertEqual(
            clause_by_name(scenario, "争端解决渠道")["initial"], "bilateral"
        )
        derived_fields = {
            item["field"] for item in warnings if item["code"] == "INITIAL_DERIVED"
        }
        self.assertNotIn("issues[export_license_scope].initial", derived_fields)
        self.assertNotIn("issues[dispute_forum].initial", derived_fields)
        self.assertIn("issues[license_validity_months].initial", derived_fields)

    def test_illegal_explicit_initial_raises(self):
        out_of_range = b_scenario()
        out_of_range["issues"][0]["initial"] = 99
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(out_of_range)
        self.assertIn("issues[0].initial", str(context.exception))

        bad_enum = b_scenario()
        bad_enum["issues"][2]["initial"] = "war"
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(bad_enum)
        self.assertIn("issues[2].initial", str(context.exception))

        bad_type = b_scenario()
        bad_type["issues"][0]["initial"] = "high"
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(bad_type)
        self.assertIn("issues[0].initial", str(context.exception))

    def test_terminal_rules_plural_key_accepted(self):
        source = b_scenario()
        rules = source["terminal_rules"]
        rules.pop("accept_requires_no_open_issue")
        rules["accept_requires_no_open_issues"] = False
        adapted = adapt_scenario(source)
        self.assertFalse(
            adapted["terminal_rules"]["accept_requires_no_open_issues"]
        )
        self.assertTrue(adapted["allow_accept_with_open_issues"])

    def test_terminal_rules_conflicting_keys_raise(self):
        source = b_scenario()
        source["terminal_rules"]["accept_requires_no_open_issues"] = False
        with self.assertRaises(ScenarioContractError) as context:
            adapt_scenario(source)
        self.assertIn("冲突", str(context.exception))


def _adapt_with_warnings(source: dict):
    return adapt_scenario_with_warnings(source)


class AdapterEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = adapt_scenario(b_scenario())
        cls.plan = initial_plan(cls.scenario)

    def test_initial_utility_matches_engine(self):
        # initial 改为「双方 ideal 中点 + 硬红线可行域夹逼」后的基线：
        # cn=0.796667 / us=0.671667（us 不变是夹具的偶然，见 INTEGRATION_NOTES 5.1）。
        self.assertAlmostEqual(utility(self.plan, "cn", self.scenario), 0.7967, places=4)
        self.assertAlmostEqual(utility(self.plan, "us", self.scenario), 0.6717, places=4)

    def test_initial_plan_respects_hard_redlines(self):
        plan = initial_plan(self.scenario)
        numeric = {
            clause["name"]: clause
            for clause in self.scenario["clauses"]
            if clause["type"] == "numeric"
        }
        self.assertTrue(numeric)
        for name, clause in numeric.items():
            option = plan[name]["option"]
            for party in ("cn", "us"):
                self.assertFalse(
                    is_redline_violation(clause, option, party),
                    f"条款「{name}」初始值 {option!r} 落在 {party} 的硬红线违规区间。",
                )

    def test_initial_derived_clamped_when_redlines_conflict(self):
        source = b_scenario()
        for item in source["private_state_by_party"]["us"]["redlines"]:
            if item["issue_id"] == "export_license_scope":
                item["value"] = 16
        scenario, warnings = _adapt_with_warnings(source)
        clause = clause_by_name(scenario, "受管制先进制程门槛")
        # 中点 (28+14)/2 = 21，us 硬红线 max=16 → 可行域 [14,16] 把中点夹到 16。
        self.assertEqual(clause["initial"], 16.0)
        self.assertFalse(
            any(item["code"] == "REDLINE_RANGE_EMPTY" for item in warnings)
        )

    def test_hard_redline_blocks_action(self):
        engine = RulesEngine(deepcopy(self.scenario), session_id="redline-test")
        ok, code, _, _ = submit(
            engine,
            "cn-too-low",
            "cn",
            "offer",
            {"受管制先进制程门槛": 13},
        )
        self.assertFalse(ok)
        self.assertEqual(code, "REDLINE_VIOLATION")

    def test_boundary_value_is_not_violation(self):
        engine = RulesEngine(deepcopy(self.scenario), session_id="boundary-test")
        ok, code, message, _ = submit(
            engine,
            "cn-boundary",
            "cn",
            "offer",
            {"受管制先进制程门槛": 14},
        )
        self.assertTrue(ok, f"{code}: {message}")

    def test_walk_away_forbidden(self):
        engine = RulesEngine(deepcopy(self.scenario), session_id="walk-test")
        ok, code, _, _ = submit(engine, "cn-walk", "cn", "walk_away")
        self.assertFalse(ok)
        self.assertEqual(code, "WALK_AWAY_FORBIDDEN")
        self.assertEqual(engine.state.status, "active")

    def test_soft_redline_is_warning_not_blocking(self):
        source = b_scenario()
        redlines = source["private_state_by_party"]["us"]["redlines"]
        for item in redlines:
            if item["issue_id"] == "export_license_scope":
                item["hard"] = False
        scenario = adapt_scenario(source)
        engine = RulesEngine(scenario, session_id="soft-test")
        ok, code, message, _ = submit(
            engine,
            "us-soft",
            "us",
            "offer",
            {"受管制先进制程门槛": 25},
        )
        self.assertTrue(ok, f"{code}: {message}")
        plan = initial_plan(scenario)
        plan["受管制先进制程门槛"]["option"] = 25
        self.assertIn(
            ("受管制先进制程门槛", "us"),
            soft_redline_violations(plan, scenario),
        )

    def test_partial_agreement_not_allowed(self):
        engine = RulesEngine(deepcopy(self.scenario), session_id="partial-test")
        submit(
            engine,
            "cn-one",
            "cn",
            "offer",
            {"受管制先进制程门槛": 14},
        )
        terminal = engine.finish()
        self.assertEqual(terminal["type"], "DEADLOCK")

    def test_end_to_end_full_agreement(self):
        engine = RulesEngine(deepcopy(self.scenario), session_id="e2e-test")
        steps = (
            ("c1", "cn", "offer", {"受管制先进制程门槛": 14}),
            ("u1", "us", "counter_offer", {"逐案许可有效期": 12}),
            ("c2", "cn", "counter_offer", {"争端解决渠道": "bilateral"}),
        )
        for action_id, actor, action_type, patch in steps:
            ok, code, message, _ = submit(
                engine, action_id, actor, action_type, patch
            )
            self.assertTrue(ok, f"{action_id}: {code} {message}")
        engine.next_round()
        ok, code, message, _ = submit(engine, "u2", "us", "accept")
        self.assertTrue(ok, f"{code}: {message}")
        self.assertEqual(engine.state.terminal["type"], "FULL_AGREEMENT")
        evaluation = engine.evaluate()
        self.assertEqual(evaluation["agreement_quality"]["coverage"], 1.0)
        self.assertTrue(evaluation["batna_comparison"]["cn"]["better_than_batna"])
        self.assertTrue(evaluation["batna_comparison"]["us"]["better_than_batna"])
        self.assertTrue(engine.replay()["consistent"])

    def test_private_state_isolated_by_viewer(self):
        engine = RulesEngine(deepcopy(self.scenario), session_id="view-test")
        view = engine.public_state("cn")
        self.assertEqual(list(view["private_state_by_party"].keys()), ["cn"])
        rendered = json.dumps(view, ensure_ascii=False)
        us_private = b_scenario()["private_state_by_party"]["us"]
        self.assertNotIn(us_private["hidden_task"], rendered)
        self.assertNotIn("盟友协调机制已具备快速启动条件", rendered)
        self.assertIn(
            b_scenario()["private_state_by_party"]["cn"]["hidden_task"], rendered
        )

    def test_member_a_effect_labels_with_shared_index_table(self):
        """A 复用 demo 整表后，statement + effect_labels 的数字必须与 A 实测一致。"""
        demo = load_scenario(os.path.join(ROOT, "scenarios", "demo_scenario.json"))
        source = b_scenario()
        source["index_rules"] = deepcopy(demo["index_rules"])
        scenario = adapt_scenario(source)
        engine = RulesEngine(scenario, session_id="a-label-test")
        labels = (
            {"label": "personal_attack", "magnitude": "major"},
            {"label": "constructive_proposal", "magnitude": "moderate"},
        )
        for index, label in enumerate(labels):
            ok, code, message, _ = engine.submit_action(
                make_action(
                    action_id=f"label-{index}",
                    actor="cn",
                    action_type="statement",
                    labels=[label],
                )
            )
            self.assertTrue(ok, f"{code}: {message}")
        first, second = engine.state.behavior_log
        self.assertEqual(first["label_mode"], "effect_labels")
        self.assertEqual(first["deltas"], {"image": -9, "trust": -10})
        self.assertEqual(second["deltas"], {"image": 3, "trust": 2})


if __name__ == "__main__":
    unittest.main()
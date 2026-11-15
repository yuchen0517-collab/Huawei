"""load_scenario_bridge 测试：双实现统一、入口回落、BOM、隔离与回归守卫。"""

import json
import os
import tempfile
import unittest
from copy import deepcopy

from adapter import adapt_scenario
from engine import RulesEngine
from load_scenario_bridge import (
    ENGINE_ROOT,
    convert_b_scenario,
    evaluate_for,
    get_last_warnings,
    is_b_scenario,
    load_scenario,
    make_scenario,
    make_scenario_with_warnings,
)
from tests import make_action

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B_SCENARIO_PATH = os.path.join(ROOT, "scenarios", "from_b_chip_controls.json")
DEMO_PATH = os.path.join(ROOT, "scenarios", "demo_scenario.json")


def load_b() -> dict:
    with open(B_SCENARIO_PATH, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_demo() -> dict:
    with open(DEMO_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


class IsBScenarioTest(unittest.TestCase):
    def test_b_format_returns_true(self):
        self.assertTrue(is_b_scenario(load_b()))

    def test_c_format_returns_false(self):
        self.assertFalse(is_b_scenario(load_demo()))

    def test_non_mapping_returns_false(self):
        self.assertFalse(is_b_scenario(None))
        self.assertFalse(is_b_scenario([]))


class ConvertDelegationTest(unittest.TestCase):
    """证明 A 的旧转换器已废除，全项目只有 adapter 一套实现。"""

    def test_convert_output_equals_adapter_output(self):
        source = load_b()
        self.assertEqual(convert_b_scenario(source), adapt_scenario(deepcopy(source)))

    def test_convert_does_not_mutate_input(self):
        source = load_b()
        snapshot = deepcopy(source)
        convert_b_scenario(source)
        self.assertEqual(source, snapshot)

    def test_convert_keeps_all_terminal_rules(self):
        converted = convert_b_scenario(load_b())
        self.assertEqual(
            converted["terminal_rules"],
            {
                "allow_walk_away": False,
                "accept_requires_no_open_issues": True,
                "partial_agreement_allowed": False,
            },
        )


class LoadScenarioEntryTest(unittest.TestCase):
    def test_none_falls_back_to_make_scenario(self):
        scenario = load_scenario(None)
        self.assertEqual(scenario["scenario_id"], "ai_governance")
        self.assertEqual(scenario, make_scenario())

    def test_path_loads_c_scenario_verbatim(self):
        scenario = load_scenario(DEMO_PATH)
        self.assertEqual(scenario["scenario_id"], load_demo()["scenario_id"])
        self.assertNotIn("issues", scenario)

    def test_path_loads_b_scenario_and_adapts(self):
        scenario = load_scenario(B_SCENARIO_PATH)
        self.assertEqual(scenario["scenario_id"], "scn_chip_001")
        self.assertEqual(scenario, convert_b_scenario(load_b()))

    def test_bom_file_can_be_loaded(self):
        payload = json.dumps(load_b(), ensure_ascii=False)
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        handle.close()
        try:
            with open(handle.name, "w", encoding="utf-8-sig") as target:
                target.write(payload)
            scenario = load_scenario(handle.name)
            self.assertEqual(scenario["scenario_id"], "scn_chip_001")
        finally:
            os.unlink(handle.name)


class AdaptedScenarioRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.scenario = convert_b_scenario(load_b())

    def test_engine_loads_adapted_b_scenario(self):
        engine = RulesEngine(self.scenario, session_id="bridge-load")
        state = engine.public_state()
        self.assertEqual(state["scenario_id"], "scn_chip_001")
        self.assertEqual(state["phase"], "opening")
        self.assertEqual(state["action_points"], 3)
        self.assertEqual(state["round"], 1)

    def test_public_state_hides_other_party_private(self):
        engine = RulesEngine(self.scenario, session_id="bridge-sec")
        view = engine.public_state("cn")
        self.assertEqual(list(view["private_state_by_party"].keys()), ["cn"])
        rendered = json.dumps(view, ensure_ascii=False)
        us_private = load_b()["private_state_by_party"]["us"]
        self.assertNotIn(us_private["hidden_task"], rendered)
        self.assertNotIn(us_private["batna"]["description"], rendered)
        self.assertNotIn("goals", json.dumps(view["private_state_by_party"], ensure_ascii=False))
        self.assertIn(
            load_b()["private_state_by_party"]["cn"]["hidden_task"], rendered
        )

    def test_walk_away_forbidden_keeps_state_unchanged(self):
        engine = RulesEngine(self.scenario, session_id="bridge-walk")
        before = (
            engine.state.status,
            engine.state.round,
            engine.state.action_points,
            deepcopy(engine.state.indices),
            len(engine.state.public_events),
        )
        ok, code, message, events = engine.submit_action(
            make_action("walk-1", "cn", "walk_away")
        )
        self.assertFalse(ok)
        self.assertEqual(code, "WALK_AWAY_FORBIDDEN")
        self.assertEqual(events, [])
        after = (
            engine.state.status,
            engine.state.round,
            engine.state.action_points,
            engine.state.indices,
            len(engine.state.public_events),
        )
        self.assertEqual(before, after)
        self.assertEqual(engine.state.terminal, None)


class MakeScenarioRegressionTest(unittest.TestCase):
    """防回归：占位分数（所有选项同分 / 双方理想点相同）一旦回来必须挂测试。"""

    @classmethod
    def setUpClass(cls):
        cls.scenario = make_scenario()

    def test_no_enum_clause_with_uniform_scores(self):
        enum_clauses = [
            clause for clause in self.scenario["clauses"] if clause["type"] == "enum"
        ]
        self.assertEqual(len(enum_clauses), 2)
        for clause in enum_clauses:
            for party in ("cn", "us"):
                values = {item["score"][party] for item in clause["options"]}
                self.assertGreater(
                    len(values),
                    1,
                    f"条款「{clause['name']}」对 {party} 的所有选项同分，Interest 失去区分度。",
                )

    def test_numeric_clause_positions_not_uniform(self):
        for clause in self.scenario["clauses"]:
            if clause["type"] != "numeric":
                continue
            ideals = {clause["positions"][party]["ideal"] for party in ("cn", "us")}
            self.assertGreater(len(ideals), 1, f"条款「{clause['name']}」双方理想点相同。")

    def test_weights_sum_to_one(self):
        for party in ("cn", "us"):
            total = sum(clause["weights"][party] for clause in self.scenario["clauses"])
            self.assertAlmostEqual(total, 1.0, places=6)

    def test_index_rules_still_borrowed_from_demo(self):
        demo_rules = load_demo()["index_rules"]
        for key in ("scale", "sensitivity", "image_actions", "trust_actions"):
            self.assertEqual(self.scenario["index_rules"][key], demo_rules[key])
        self.assertEqual(
            self.scenario["index_rules"]["initial"],
            {
                "cn": {"image": 70, "trust": 65},
                "us": {"image": 70, "trust": 65},
            },
        )

    def test_warnings_are_structured_dicts(self):
        _, warnings = make_scenario_with_warnings()
        codes = {item["code"] for item in warnings}
        self.assertIn("INDEX_RULES_BORROWED", codes)
        self.assertIn("SCORES_DERIVED", codes)
        for item in warnings:
            self.assertEqual(set(item), {"code", "field", "message"})
            self.assertTrue(item["code"])
            self.assertTrue(item["field"])
            self.assertTrue(item["message"])

    def test_get_last_warnings_matches_last_build(self):
        make_scenario()
        first = get_last_warnings()
        self.assertTrue(first)
        make_scenario()
        self.assertEqual(first, get_last_warnings())
        for item in get_last_warnings():
            self.assertEqual(set(item), {"code", "field", "message"})

    def test_make_scenario_is_deterministic(self):
        self.assertEqual(make_scenario(), make_scenario())

    def test_engine_accepts_make_scenario(self):
        engine = RulesEngine(make_scenario(), session_id="bridge-make")
        state = engine.public_state("cn")
        self.assertEqual(state["phase"], "opening")
        for party in ("cn", "us"):
            for index in ("interest", "image", "trust"):
                value = state["indices"][party][index]
                self.assertGreaterEqual(value, 0)
                self.assertLessEqual(value, 100)
        self.assertTrue(ENGINE_ROOT.joinpath("engine", "core.py").is_file())

    def test_design_table_matches_agents_json(self):
        _, warnings = make_scenario_with_warnings()
        mismatches = [
            item
            for item in warnings
            if item["code"] == "DESIGN_TABLE_UNVERIFIED"
            and item["field"].startswith("agents.")
        ]
        self.assertEqual(mismatches, [])

    def test_design_table_unverified_clause_emits_warning(self):
        _, warnings = make_scenario_with_warnings()
        fields = {
            item["field"]
            for item in warnings
            if item["code"] == "DESIGN_TABLE_UNVERIFIED"
        }
        # agenda 里有「全球算力资源分配」「数据跨境流动规则」，能对上；
        # 「前沿模型评测门槛」对不上，必须记 warning。
        self.assertIn("clauses.前沿模型评测门槛", fields)
        self.assertNotIn("clauses.全球算力资源分配", fields)

    def test_agents_fallback_copy_warning(self):
        _, warnings = make_scenario_with_warnings()
        fallback = [
            item for item in warnings if item["code"] == "AGENTS_FALLBACK_COPY"
        ]
        if (ENGINE_ROOT.parent / "agents.json").is_file():
            self.assertEqual(fallback, [])
        else:
            self.assertEqual(len(fallback), 1)

    def test_batna_none_keeps_evaluation_shape(self):
        engine = RulesEngine(make_scenario(), session_id="bridge-batna")
        steps = (
            ("b1", "cn", "offer", {"全球算力资源分配": "附带可核查机制"}),
            ("b2", "us", "counter_offer", {"前沿模型评测门槛": 55}),
            ("b3", "cn", "counter_offer", {"数据跨境流动": "白名单互认"}),
        )
        for action_id, actor, action_type, patch in steps:
            ok, code, message, _ = engine.submit_action(
                make_action(action_id, actor, action_type, patch)
            )
            self.assertTrue(ok, f"{action_id}: {code} {message}")
        engine.next_round()
        ok, code, message, _ = engine.submit_action(make_action("b4", "us", "accept"))
        self.assertTrue(ok, f"{code}: {message}")
        evaluation = engine.evaluate()
        self.assertEqual(evaluation["agreement_quality"]["coverage"], 1.0)
        us_entry = evaluation["batna_comparison"]["us"]
        self.assertEqual(
            set(us_entry), {"batna", "achieved", "net_gain", "better_than_batna"}
        )
        self.assertIsNone(us_entry["batna"])
        self.assertIsNone(us_entry["net_gain"])
        self.assertIsNone(us_entry["better_than_batna"])


class EvaluateForTest(unittest.TestCase):
    def setUp(self):
        self.engine = RulesEngine(
            convert_b_scenario(load_b()), session_id="bridge-eval"
        )

    def test_filters_other_party_batna(self):
        evaluation = evaluate_for(self.engine, "cn")
        self.assertEqual(evaluation["batna_comparison"]["cn"]["batna"], 30)
        self.assertIsNone(evaluation["batna_comparison"]["us"]["batna"])
        self.assertIsNone(evaluation["batna_comparison"]["us"]["net_gain"])
        self.assertIsNone(evaluation["batna_comparison"]["us"]["better_than_batna"])
        self.assertEqual(
            evaluation["batna_comparison"]["us"]["achieved"],
            self.engine.state.indices["us"]["interest"],
        )
        self.assertEqual(
            set(evaluation),
            {
                "terminal_type",
                "agreement_quality",
                "batna_comparison",
                "redline_check",
                "learning_performance",
                "evidence_links",
            },
        )

    def test_rejects_empty_viewer(self):
        with self.assertRaises(ValueError):
            evaluate_for(self.engine, "")


if __name__ == "__main__":
    unittest.main()
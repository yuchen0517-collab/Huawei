"""B 契约 1.1 index_rules 形状转换与防静默失效测试。

覆盖三件事：
1. B 的 13 标签平铺表 → 引擎 image_actions / trust_actions 表的无损映射；
2. 端到端：B 真实场景经适配层后，行为标签必须真的改变 image / trust；
3. IndexRulesShapeError：非空但形状不可识别的 index_rules 必须显式失败。
"""

import json
import os
import unittest
from copy import deepcopy

from adapter import ScenarioContractError, adapt_scenario, adapt_scenario_with_warnings
from adapter.scenario_adapter import (
    INDEX_RULE_LABELS,
    INDEX_RULE_MAGNITUDES,
    _normalize_index_rules,
)
from engine import RulesEngine
from engine.indices import IndexRulesShapeError, behaviour_delta, initial_indices
from engine.validator import LABELS
from tests import make_action

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
INDEX_RULES_PATH = os.path.join(FIXTURES, "index_rules_v1.json")
B_SCENARIO_PATH = os.path.join(FIXTURES, "b_scenario_dst.json")


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def b_table() -> dict:
    return load_json(INDEX_RULES_PATH)


def b_scenario() -> dict:
    return load_json(B_SCENARIO_PATH)


def codes(warnings) -> set:
    return {item["code"] for item in warnings}


class NormalizeShapeTest(unittest.TestCase):
    def setUp(self):
        self.rules, self.warnings = _normalize_index_rules(
            b_table(), ["p1", "p2"]
        )

    def test_b_table_converts_to_engine_tables(self):
        self.assertIn("image_actions", self.rules)
        self.assertIn("trust_actions", self.rules)
        self.assertEqual(
            sorted(self.rules["image_actions"]), sorted(INDEX_RULE_LABELS)
        )
        self.assertEqual(
            sorted(self.rules["trust_actions"]), sorted(INDEX_RULE_LABELS)
        )
        for label in INDEX_RULE_LABELS:
            self.assertEqual(
                list(self.rules["image_actions"][label]), list(INDEX_RULE_MAGNITUDES)
            )
            self.assertEqual(
                list(self.rules["trust_actions"][label]), list(INDEX_RULE_MAGNITUDES)
            )

    def test_b_table_values_preserved(self):
        # personal_attack.major：image -9 / trust -6
        self.assertEqual(
            self.rules["image_actions"]["personal_attack"]["major"], -9
        )
        self.assertEqual(
            self.rules["trust_actions"]["personal_attack"]["major"], -6
        )
        # hardline_stance.moderate：image -4 / trust -4
        self.assertEqual(
            self.rules["image_actions"]["hardline_stance"]["moderate"], -4
        )
        self.assertEqual(
            self.rules["trust_actions"]["hardline_stance"]["moderate"], -4
        )
        # keep_promise.major：image +6 / trust +9
        self.assertEqual(self.rules["image_actions"]["keep_promise"]["major"], 6)
        self.assertEqual(self.rules["trust_actions"]["keep_promise"]["major"], 9)

    def test_initial_expands_to_every_party(self):
        source = b_table()
        source["initial"] = {"image": 70, "trust": 20}
        rules, _ = _normalize_index_rules(source, ["p1", "p2"])
        self.assertEqual(rules["initial"]["p1"], {"image": 70, "trust": 20})
        self.assertEqual(rules["initial"]["p2"], {"image": 70, "trust": 20})

    def test_scale_defaults_to_zero_hundred(self):
        self.assertEqual(self.rules["scale"], [0, 100])

    def test_sensitivity_absent_is_one_and_warned(self):
        self.assertNotIn("sensitivity", self.rules)
        self.assertIn("SENSITIVITY_ABSENT", codes(self.warnings))
        # 缺省敏感度等价于 1.0：major personal_attack 仍是 -9 / -6。
        scenario = {"index_rules": self.rules}
        delta = behaviour_delta(
            "p1", {"label": "personal_attack", "magnitude": "major"}, scenario
        )
        self.assertEqual(delta, {"image": -9, "trust": -6})

    def test_interest_delta_ignored_with_warning(self):
        self.assertIn("INTEREST_DELTA_UNSUPPORTED", codes(self.warnings))
        self.assertNotIn("interest", self.rules)
        self.assertNotIn("interest_actions", self.rules)

    def test_native_shape_preserved(self):
        native = {
            "scale": [0, 100],
            "initial": {"p1": {"image": 10, "trust": 20}},
            "image_actions": {"procedural": {"slight": 5, "moderate": 5, "major": 5}},
            "trust_actions": {"procedural": {"slight": 5, "moderate": 5, "major": 5}},
        }
        rules, warnings = _normalize_index_rules(native, ["p1", "p2"])
        self.assertEqual(rules, native)
        self.assertIn("INDEX_RULES_ALREADY_NATIVE", codes(warnings))

    def test_missing_label_filled_with_zero(self):
        source = b_table()
        del source["personal_attack"]
        rules, warnings = _normalize_index_rules(source, ["p1", "p2"])
        self.assertEqual(
            rules["image_actions"]["personal_attack"],
            {"slight": 0, "moderate": 0, "major": 0},
        )
        self.assertEqual(
            rules["trust_actions"]["personal_attack"],
            {"slight": 0, "moderate": 0, "major": 0},
        )
        self.assertIn("INDEX_RULE_LABEL_MISSING", codes(warnings))

    def test_unknown_label_ignored_with_warning(self):
        source = b_table()
        source["bribe"] = {
            "slight": {"interest_delta": 9, "image_delta": 9, "trust_delta": 9},
            "moderate": {"interest_delta": 9, "image_delta": 9, "trust_delta": 9},
            "major": {"interest_delta": 9, "image_delta": 9, "trust_delta": 9},
        }
        rules, warnings = _normalize_index_rules(source, ["p1", "p2"])
        self.assertNotIn("bribe", rules["image_actions"])
        self.assertIn("INDEX_RULE_LABEL_UNKNOWN", codes(warnings))

    def test_unrecognizable_shape_raises(self):
        with self.assertRaises(ScenarioContractError) as context:
            _normalize_index_rules({"foo": 1}, ["p1", "p2"])
        self.assertIn("形状不可识别", str(context.exception))

    def test_adapter_labels_match_engine_labels(self):
        self.assertEqual(INDEX_RULE_LABELS, LABELS)


class ShapeErrorTest(unittest.TestCase):
    def test_behaviour_delta_raises_on_unrecognizable_rules(self):
        scenario = {"index_rules": {"foo": 1}}
        with self.assertRaises(IndexRulesShapeError) as context:
            behaviour_delta(
                "cn", {"label": "personal_attack", "magnitude": "major"}, scenario
            )
        message = str(context.exception)
        self.assertIn("既无 image_actions 也无 trust_actions", message)
        self.assertIn("foo", message)

    def test_behaviour_delta_accepts_empty_rules(self):
        scenario = {"index_rules": {}}
        delta = behaviour_delta(
            "cn", {"label": "personal_attack", "magnitude": "major"}, scenario
        )
        self.assertEqual(delta, {"image": 0, "trust": 0})

    def test_behaviour_delta_accepts_missing_rules(self):
        delta = behaviour_delta(
            "cn", {"label": "personal_attack", "magnitude": "major"}, {}
        )
        self.assertEqual(delta, {"image": 0, "trust": 0})

    def test_magnitude_missing_reports_warning(self):
        scenario = {
            "index_rules": {
                "image_actions": {"personal_attack": {"slight": -3}},
                "trust_actions": {"personal_attack": {"slight": -2}},
            }
        }
        warnings = []
        delta = behaviour_delta(
            "cn",
            {"label": "personal_attack", "magnitude": "major"},
            scenario,
            warnings,
        )
        self.assertEqual(delta, {"image": 0, "trust": 0})
        self.assertEqual(
            [item["code"] for item in warnings],
            ["INDEX_RULE_MAGNITUDE_MISSING", "INDEX_RULE_MAGNITUDE_MISSING"],
        )


class EndToEndBTableTest(unittest.TestCase):
    def setUp(self):
        self.source = b_scenario()
        self.source["index_rules"] = b_table()
        self.scenario, self.warnings = adapt_scenario_with_warnings(self.source)

    def test_initial_indices_use_b_table_global_values(self):
        source = b_scenario()
        table = b_table()
        table["initial"] = {"image": 80, "trust": 30}
        source["index_rules"] = table
        scenario, _ = adapt_scenario_with_warnings(source)
        indices = initial_indices(scenario)
        for party in ("p1", "p2"):
            self.assertEqual(indices[party]["image"], 80)
            self.assertEqual(indices[party]["trust"], 30)

    def test_adapted_scenario_has_engine_tables(self):
        rules = self.scenario["index_rules"]
        self.assertIn("image_actions", rules)
        self.assertIn("trust_actions", rules)
        self.assertNotIn("personal_attack", rules)

    def test_personal_attack_major_drops_image_and_trust(self):
        """本轮最重要的回归：B 1.1 表经完整链路后绝不能静默归零。"""
        engine = RulesEngine(deepcopy(self.scenario), session_id="b-index-e2e")
        before = deepcopy(engine.state.indices["p1"])
        ok, code, message, _ = engine.submit_action(
            make_action(
                action_id="b-attack",
                actor="p1",
                action_type="statement",
                labels=[{"label": "personal_attack", "magnitude": "major"}],
            )
        )
        self.assertTrue(ok, f"{code}: {message}")
        entry = engine.state.behavior_log[-1]
        self.assertEqual(entry["deltas"], {"image": -9, "trust": -6})
        self.assertEqual(
            engine.state.indices["p1"]["image"], before["image"] - 9
        )
        self.assertEqual(
            engine.state.indices["p1"]["trust"], before["trust"] - 6
        )
        self.assertLess(engine.state.indices["p1"]["image"], before["image"])
        self.assertLess(engine.state.indices["p1"]["trust"], before["trust"])
        self.assertTrue(engine.replay()["consistent"])


if __name__ == "__main__":
    unittest.main()
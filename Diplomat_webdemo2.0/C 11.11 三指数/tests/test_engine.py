import json
import unittest
from pathlib import Path

from engine.indices import apply_effects
from engine.state import NegotiationState
from engine.terminal import check_terminal, evaluate, evaluate_agreement
from engine.validator import ERRORS, validate_action, validate_effect

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "scenarios" / "demo_scenario.json"


def load_scenario():
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


def new_state(session_id="test-session"):
    return NegotiationState(session_id=session_id, scenario=load_scenario())


class BaselineEngineTests(unittest.TestCase):
    def test_scenario_loads_three_clauses(self):
        scenario = load_scenario()
        self.assertEqual(len(scenario["clauses"]), 3)
        self.assertIn("index_rules", scenario)

    def test_state_initializes_indices_from_scenario(self):
        state = new_state()
        self.assertEqual(state.indices["CN"]["interest"], 50)
        self.assertEqual(state.indices["CN"]["image"], 60)
        self.assertEqual(state.indices["US"]["trust"], 40)

    def test_state_initializes_offers_from_defaults(self):
        state = new_state()
        self.assertEqual(state.offers["territorial_sea"], 12)
        self.assertEqual(state.offers["eez"], 50)
        self.assertEqual(state.offers["straits_transit"], 12)

    def test_public_dict_contains_indices_and_hides_private(self):
        state = new_state()
        state.private_state_by_party = {"CN": {"task": "守住 200 海里"}}

        public = state.to_public_dict()
        self.assertEqual(public["indices"], state.indices)
        self.assertNotIn("private_state", public)

        own_view = state.to_public_dict("CN")
        self.assertEqual(own_view["private_state"], {"task": "守住 200 海里"})

    def test_validate_action_accepts_known_action(self):
        state = new_state()
        ok, code, message = validate_action(
            {"actor": "CN", "action_type": "procedural", "round": 1}, state
        )
        self.assertTrue(ok)
        self.assertIsNone(code)
        self.assertEqual(message, "")

    def test_validate_action_rejects_unknown_action(self):
        state = new_state()
        ok, code, _ = validate_action(
            {"actor": "CN", "action_type": "teleport", "round": 1}, state
        )
        self.assertFalse(ok)
        self.assertEqual(code, "UNKNOWN_ACTION")
        self.assertIn("未知的动作类型", ERRORS[code])

    def test_validate_effect_accepts_clause_value(self):
        effect = {
            "actor": "CN",
            "action_type": "concession",
            "magnitude": "moderate",
            "clause": "领海宽度",
            "value": 10,
        }
        ok, code, message = validate_effect(effect, load_scenario())
        self.assertTrue(ok)
        self.assertIsNone(code)
        self.assertEqual(message, "")

    def test_validate_effect_rejects_numeric_delta(self):
        effect = {"action_type": "concession", "magnitude": "moderate", "interest_delta": 6}
        ok, code, message = validate_effect(effect, load_scenario())
        self.assertFalse(ok)
        self.assertEqual(code, "UNKNOWN_EFFECT_LABEL")
        self.assertIn("数值增量", message)

    def test_check_terminal_not_terminal_initially(self):
        state = new_state()
        self.assertFalse(check_terminal(state)["terminal"])

    def test_check_terminal_round_limit(self):
        state = new_state()
        state.round = 13
        result = check_terminal(state)
        self.assertTrue(result["terminal"])
        self.assertEqual(result["reason"], "round_limit")

    def test_evaluate_agreement_reports_index_changes(self):
        state = new_state()
        apply_effects(
            state,
            state.scenario,
            [{"actor": "CN", "action_type": "constructive_proposal", "magnitude": "major"}],
        )
        result = evaluate_agreement(state)
        self.assertEqual(result["final_indices"]["CN"]["image"], 65)
        self.assertEqual(result["index_changes"]["CN"]["image"], 5)
        self.assertFalse(result["interest_below_initial"])

    def test_evaluate_evidence_links_include_index_events(self):
        state = new_state()
        apply_effects(
            state,
            state.scenario,
            [{"actor": "CN", "action_type": "personal_attack", "magnitude": "moderate"}],
        )
        result = evaluate(state)
        event_ids = [event["event_id"] for event in state.public_events]
        self.assertTrue(event_ids)
        self.assertEqual(result["evidence_links"], event_ids)
        self.assertEqual(result["index_event_count"], len(event_ids))



if __name__ == "__main__":
    unittest.main()
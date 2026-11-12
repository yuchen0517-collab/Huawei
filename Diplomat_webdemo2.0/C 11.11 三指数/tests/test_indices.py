import json
import unittest
from copy import deepcopy
from pathlib import Path

from engine.indices import (
    EffectRejected,
    apply_effects,
    replay_indices,
    resolve_behavior_delta,
    round_half_away,
)
from engine.state import NegotiationState
from engine.validator import ERRORS, validate_effect

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "scenarios" / "demo_scenario.json"
EXAMPLE_STATE_PATH = ROOT / "state.example.json"


def load_scenario():
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


def new_state(session_id="indices-test"):
    return NegotiationState(session_id=session_id, scenario=load_scenario())


class ThreeIndicesTests(unittest.TestCase):
    def test_delta_matches_table(self):
        scenario = load_scenario()
        delta = resolve_behavior_delta("CN", "concession", "major", scenario)
        self.assertEqual(delta["trust"], round_half_away(1 * 1.2))
        self.assertEqual(delta["trust"], 1)

    def test_clamp_at_bounds(self):
        state = new_state()
        effect = {
            "actor": "CN",
            "action_type": "constructive_proposal",
            "magnitude": "major",
        }
        for _ in range(30):
            apply_effects(state, state.scenario, [effect])

        self.assertEqual(state.indices["CN"]["image"], 100)
        image_events = [
            event for event in state.public_events if event["index"] == "image"
        ]
        self.assertTrue(any(event["clamped"] for event in image_events))
        self.assertEqual(image_events[-1]["after"], 100)

    def test_replay_same_events_same_state(self):
        scenario = load_scenario()
        source = NegotiationState(session_id="replay-source", scenario=scenario)
        apply_effects(
            source,
            scenario,
            [
                {
                    "actor": "CN",
                    "action_type": "constructive_proposal",
                    "magnitude": "major",
                    "clause": "专属经济区宽度",
                    "value": 80,
                },
                {"actor": "US", "action_type": "personal_attack", "magnitude": "major"},
                {"actor": "CN", "action_type": "protect_ally", "magnitude": "moderate"},
            ],
        )

        first = replay_indices(source.public_events, scenario)
        second = replay_indices(source.public_events, scenario)

        self.assertEqual(first.indices, source.indices)
        self.assertEqual(second.indices, source.indices)
        self.assertEqual(first.public_events, source.public_events)
        self.assertEqual(second.public_events, source.public_events)
        self.assertEqual(first.public_events, second.public_events)

    def test_replay_from_log(self):
        scenario = load_scenario()
        saved = json.loads(EXAMPLE_STATE_PATH.read_text(encoding="utf-8"))
        replay = replay_indices(saved["public_events"], scenario)

        self.assertEqual(replay.indices, saved["indices"])
        self.assertEqual(replay.public_events, saved["public_events"])
        self.assertTrue(saved["public_events"])

    def test_unknown_label_rejected(self):
        effect = {"actor": "CN", "action_type": "concession", "magnitude": "huge"}
        ok, code, message = validate_effect(effect, load_scenario())
        self.assertFalse(ok)
        self.assertEqual(code, "UNKNOWN_EFFECT_LABEL")
        self.assertIn(ERRORS["UNKNOWN_EFFECT_LABEL"], message)

    def test_interest_only_from_clauses(self):
        state = new_state()
        before = deepcopy(state.indices)

        events = apply_effects(
            state,
            state.scenario,
            [
                {
                    "actor": "CN",
                    "action_type": "concession",
                    "magnitude": "moderate",
                    "clause": "领海宽度",
                    "reason": "接受12海里",
                }
            ],
        )

        self.assertEqual(state.indices, before)
        self.assertEqual(events, [])
        self.assertEqual(state.offers["territorial_sea"], 12)
        self.assertEqual(len(state.behavior_log), 1)

    def test_image_not_reversed(self):
        state = new_state()
        us_before = state.indices["US"]["image"]

        apply_effects(
            state,
            state.scenario,
            [
                {
                    "actor": "CN",
                    "action_type": "personal_attack",
                    "magnitude": "major",
                    "reason": "人身攻击",
                }
            ],
        )

        self.assertEqual(state.indices["CN"]["image"], 60 + round_half_away(-10 * 0.9))
        self.assertEqual(state.indices["US"]["image"], us_before)

    def test_sensitivity_applied(self):
        scenario = load_scenario()
        cn = resolve_behavior_delta("CN", "constructive_proposal", "major", scenario)
        us = resolve_behavior_delta("US", "constructive_proposal", "major", scenario)

        self.assertEqual(cn["image"], round_half_away(5 * 0.9))
        self.assertEqual(us["image"], round_half_away(5 * 1.1))
        self.assertNotEqual(cn["image"], us["image"])
        self.assertLess(abs(cn["image"] / us["image"] - 0.9 / 1.1), 0.05)

    def test_batch_rejected_atomically(self):
        state = new_state()
        indices_before = deepcopy(state.indices)
        offers_before = deepcopy(state.offers)

        effects = [
            {
                "actor": "CN",
                "action_type": "constructive_proposal",
                "magnitude": "major",
                "clause": "专属经济区宽度",
                "value": 120,
            },
            {"actor": "US", "action_type": "concession", "magnitude": "huge"},
        ]

        with self.assertRaises(EffectRejected) as raised:
            apply_effects(state, state.scenario, effects)

        self.assertEqual(raised.exception.code, "UNKNOWN_EFFECT_LABEL")
        self.assertEqual(raised.exception.index, 1)
        self.assertEqual(state.indices, indices_before)
        self.assertEqual(state.offers, offers_before)
        self.assertEqual(state.public_events, [])
        self.assertEqual(state.behavior_log, [])


if __name__ == "__main__":
    unittest.main()
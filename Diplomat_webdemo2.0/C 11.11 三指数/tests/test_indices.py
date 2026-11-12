import unittest
from copy import deepcopy

from engine import load_scenario
from engine.indices import (
    closeness,
    derive_magnitude,
    initial_indices,
    initial_plan,
    interest_value,
    replay_indices,
    score,
    utility,
)
from engine.validator import apply_patch
from tests import full_engine, make_engine, make_action, submit


class IndicesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = load_scenario("scenarios/demo_scenario.json")
        cls.plan = initial_plan(cls.scenario)
        cls.assignment = cls.scenario["clauses"][0]
        cls.threshold = cls.scenario["clauses"][1]

    def test_closeness_at_ideal(self):
        self.assertEqual(closeness(100, 100, 10, 100), 1.0)
        self.assertEqual(closeness(10, 10, 10, 100), 1.0)

    def test_closeness_at_endpoints(self):
        self.assertEqual(closeness(10, 100, 10, 100), 0.0)
        self.assertEqual(closeness(100, 10, 10, 100), 0.0)

    def test_closeness_at_midpoint(self):
        self.assertAlmostEqual(closeness(55, 100, 10, 100), 0.5, places=6)

    def test_enum_score_lookup(self):
        self.assertEqual(score(self.assignment, "附带可核查机制", "cn"), 0.45)
        self.assertEqual(score(self.assignment, "市场主导", "us"), 0.95)

    def test_enum_unknown_option_returns_zero(self):
        self.assertEqual(score(self.assignment, "联合管理", "cn"), 0.0)

    def test_initial_utility(self):
        self.assertAlmostEqual(utility(self.plan, "cn", self.scenario), 0.6817, places=4)
        self.assertAlmostEqual(utility(self.plan, "us", self.scenario), 0.3547, places=4)

    def test_initial_interest(self):
        indices = initial_indices(self.scenario)
        self.assertEqual(indices["cn"]["interest"], 68)
        self.assertEqual(indices["us"]["interest"], 35)
        self.assertEqual(interest_value(self.plan, "cn", self.scenario), 68)

    def test_interest_is_bidirectional(self):
        engine = make_engine()
        submit(
            engine,
            action_id="shift-1",
            patch={"全球算力资源分配": "附带可核查机制"},
        )
        self.assertEqual(engine.state.indices["cn"]["interest"], 50)
        self.assertEqual(engine.state.indices["us"]["interest"], 60)
        self.assertLess(engine.state.indices["cn"]["interest"], 68)
        self.assertGreater(engine.state.indices["us"]["interest"], 35)

    def test_sensitivity_applies_to_trust(self):
        engine = make_engine()
        ok, code, message, _ = submit(
            engine,
            action_id="protect-1",
            action_type="statement",
            labels=[{"label": "protect_ally", "magnitude": "major"}],
        )
        self.assertTrue(ok, f"{code}: {message}")
        self.assertEqual(engine.state.indices["cn"]["trust"], 52)

    def test_same_label_different_party(self):
        cn_engine = make_engine()
        submit(
            cn_engine,
            action_id="attack-cn",
            actor="cn",
            action_type="statement",
            labels=[{"label": "personal_attack", "magnitude": "major"}],
        )
        self.assertEqual(cn_engine.state.indices["cn"]["image"], 51)

        us_engine = make_engine()
        submit(
            us_engine,
            action_id="attack-us",
            actor="us",
            action_type="statement",
            labels=[{"label": "personal_attack", "magnitude": "major"}],
        )
        self.assertEqual(us_engine.state.indices["us"]["image"], 44)

    def test_path_one_uses_effect_labels(self):
        engine = make_engine()
        submit(
            engine,
            action_id="label-1",
            labels=[{"label": "diplomatic_reframe", "magnitude": "moderate"}],
        )
        entry = engine.state.behavior_log[-1]
        self.assertEqual(entry["label_mode"], "effect_labels")
        self.assertEqual(entry["labels"][0]["label"], "diplomatic_reframe")

    def test_path_two_falls_back_to_action_type(self):
        engine = make_engine()
        submit(
            engine,
            action_id="fallback-1",
            patch={"全球算力资源分配": "附带可核查机制"},
        )
        entry = engine.state.behavior_log[-1]
        self.assertEqual(entry["label_mode"], "fallback")
        self.assertEqual(
            [item["label"] for item in entry["labels"]],
            ["constructive_proposal", "conditional_concession"],
        )

    def test_path_two_magnitude_buckets(self):
        for value, expected in ((32, "slight"), (50, "moderate"), (80, "major")):
            with self.subTest(value=value):
                action = make_action(
                    action_type="offer",
                    patch={"前沿模型评测门槛": value},
                )
                new_plan = apply_patch(self.plan, action["offer_patch"])
                self.assertEqual(
                    derive_magnitude(action, self.plan, new_plan, self.scenario),
                    expected,
                )

    def test_empty_patch_is_slight(self):
        for action_type in ("probe", "statement"):
            with self.subTest(action_type=action_type):
                action = make_action(action_type=action_type)
                self.assertEqual(
                    derive_magnitude(action, self.plan, self.plan, self.scenario),
                    "slight",
                )

    def test_illegal_label_batch_rejected_atomically(self):
        engine = make_engine()
        indices = {k: dict(v) for k, v in engine.state.indices.items()}
        behavior_len = len(engine.state.behavior_log)
        ok, code, _, events = submit(
            engine,
            action_id="bad-label",
            labels=[
                {"label": "constructive_proposal", "magnitude": "moderate"},
                {"label": "bribe", "magnitude": "major"},
            ],
        )
        self.assertFalse(ok)
        self.assertEqual(code, "SCHEMA_VIOLATION")
        self.assertEqual(events, [])
        self.assertEqual(engine.state.indices, indices)
        self.assertEqual(len(engine.state.behavior_log), behavior_len)

    def test_clamp_upper_bound_leaves_trace(self):
        engine = make_engine()
        engine.state.indices["cn"]["image"] = 98
        events = engine.state.apply_index_changes(
            [("cn", "image", 10)], "测试上限", "test-source"
        )
        event = events[0]
        self.assertEqual(event["before"], 98)
        self.assertEqual(event["after"], 100)
        self.assertEqual(event["delta"], 2)
        self.assertEqual(event["requested_delta"], 10)
        self.assertTrue(event["clamped"])
        self.assertEqual(event["source"], "test-source")

    def test_clamp_lower_bound_leaves_trace(self):
        engine = make_engine()
        engine.state.indices["cn"]["image"] = 3
        events = engine.state.apply_index_changes(
            [("cn", "image", -10)], "测试下限", "test-source"
        )
        event = events[0]
        self.assertEqual(event["before"], 3)
        self.assertEqual(event["after"], 0)
        self.assertEqual(event["delta"], -3)
        self.assertEqual(event["requested_delta"], -10)
        self.assertTrue(event["clamped"])

    def test_replay_matches_current(self):
        engine = full_engine()
        result = engine.replay()
        self.assertTrue(result["consistent"])
        self.assertEqual(result["replayed"], result["current"])

    def test_replay_is_pure(self):
        events = [
            {"type": "index_change", "party": "cn", "index": "image", "requested_delta": 10},
            {"type": "index_change", "party": "cn", "index": "image", "requested_delta": -20},
            {"type": "other", "party": "us", "index": "trust", "requested_delta": 50},
        ]
        indices = {"cn": {"interest": 0, "image": 0, "trust": 0}}
        snapshot_events = deepcopy(events)
        snapshot_indices = deepcopy(indices)
        first = replay_indices(events, indices)
        second = replay_indices(events, indices)
        self.assertEqual(first, second)
        self.assertEqual(events, snapshot_events)
        self.assertEqual(indices, snapshot_indices)
        self.assertEqual(first["cn"]["image"], 0)


if __name__ == "__main__":
    unittest.main()
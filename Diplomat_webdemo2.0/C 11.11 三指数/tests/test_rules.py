import unittest

from engine import TERMINAL_TYPES, load_scenario
from engine.indices import initial_plan, utility
from tests import full_engine, make_engine, submit


class RulesTest(unittest.TestCase):
    def test_initial_state_fields(self):
        engine = make_engine()
        state = engine.state
        self.assertEqual(state.round, 1)
        self.assertEqual(state.phase, "opening")
        self.assertEqual(state.current_version, 0)
        self.assertEqual(state.action_points, 3)
        self.assertEqual(state.status, "active")
        self.assertEqual(state.offers, [])
        self.assertIsNone(state.agreement)
        self.assertIsNone(state.terminal)
        self.assertEqual(len(state.open_issues), 3)
        self.assertEqual(state.final_offer_declared_by, {"cn": None, "us": None})
        self.assertEqual(state.seen_action_ids, [])

    def test_initial_indices_from_utility(self):
        engine = make_engine()
        scenario = load_scenario("scenarios/demo_scenario.json")
        plan = initial_plan(scenario)
        self.assertAlmostEqual(utility(plan, "cn", scenario), 0.6817, places=4)
        self.assertAlmostEqual(utility(plan, "us", scenario), 0.3547, places=4)
        self.assertEqual(engine.state.indices["cn"]["interest"], 68)
        self.assertEqual(engine.state.indices["us"]["interest"], 35)
        self.assertEqual(engine.state.indices["cn"]["image"], 60)
        self.assertEqual(engine.state.indices["us"]["trust"], 40)

    def test_unknown_action_type(self):
        engine = make_engine()
        version = engine.state.current_version
        indices = {k: dict(v) for k, v in engine.state.indices.items()}
        ok, code, message, events = submit(
            engine, action_id="bad-type", action_type="demand"
        )
        self.assertFalse(ok)
        self.assertEqual(code, "UNKNOWN_ACTION_TYPE")
        self.assertTrue(message)
        self.assertEqual(events, [])
        self.assertEqual(engine.state.current_version, version)
        self.assertEqual(engine.state.indices, indices)

    def test_duplicate_action_id(self):
        engine = make_engine()
        ok, _, _, _ = submit(
            engine, action_id="dup-1", patch={"全球算力资源分配": "附带可核查机制"}
        )
        self.assertTrue(ok)
        ok, code, _, _ = submit(
            engine,
            action_id="dup-1",
            patch={"前沿模型评测门槛": 50},
        )
        self.assertFalse(ok)
        self.assertEqual(code, "DUPLICATE_ACTION")

    def test_unknown_clause(self):
        engine = make_engine()
        ok, code, _, _ = submit(
            engine,
            action_id="unknown-clause",
            patch={"不存在的议题": "附带可核查机制"},
        )
        self.assertFalse(ok)
        self.assertEqual(code, "UNKNOWN_CLAUSE")

    def test_unknown_option(self):
        engine = make_engine()
        ok, code, _, _ = submit(
            engine,
            action_id="unknown-option",
            patch={"全球算力资源分配": "联合管理"},
        )
        self.assertFalse(ok)
        self.assertEqual(code, "UNKNOWN_OPTION")

    def test_value_out_of_range(self):
        engine = make_engine()
        ok, code, _, _ = submit(
            engine,
            action_id="out-of-range",
            patch={"前沿模型评测门槛": 999},
        )
        self.assertFalse(ok)
        self.assertEqual(code, "VALUE_OUT_OF_RANGE")

    def test_redline_violation(self):
        engine = make_engine()
        indices = {k: dict(v) for k, v in engine.state.indices.items()}
        ok, code, _, _ = submit(
            engine,
            action_id="redline",
            patch={"全球算力资源分配": "市场主导"},
        )
        self.assertFalse(ok)
        self.assertEqual(code, "REDLINE_VIOLATION")
        self.assertEqual(engine.state.indices, indices)
        self.assertEqual(engine.state.current_version, 0)

    def test_accept_with_open_issues(self):
        engine = make_engine()
        submit(engine, action_id="cn-1", patch={"全球算力资源分配": "附带可核查机制"})
        submit(
            engine,
            action_id="us-1",
            actor="us",
            action_type="counter_offer",
            patch={"前沿模型评测门槛": 50},
        )
        ok, code, _, _ = submit(
            engine, action_id="cn-accept", actor="cn", action_type="accept"
        )
        self.assertFalse(ok)
        self.assertEqual(code, "AGREEMENT_HAS_OPEN_ISSUES")

    def test_accept_without_counterpart_offer(self):
        engine = make_engine()
        submit(engine, action_id="cn-1", patch={"全球算力资源分配": "附带可核查机制"})
        ok, code, _, _ = submit(
            engine, action_id="cn-accept", actor="cn", action_type="accept"
        )
        self.assertFalse(ok)
        self.assertEqual(code, "NO_COUNTERPART_OFFER")

    def test_action_points_insufficient(self):
        engine = make_engine()
        for index in range(3):
            ok, code, _, _ = submit(
                engine, action_id=f"stmt-{index}", action_type="statement"
            )
            self.assertTrue(ok, code)
        self.assertEqual(engine.state.action_points, 0)
        ok, code, _, _ = submit(
            engine, action_id="stmt-4", action_type="statement"
        )
        self.assertFalse(ok)
        self.assertEqual(code, "ACTION_POINTS_INSUFFICIENT")

    def test_phase_closed(self):
        engine = make_engine()
        submit(engine, action_id="walk", action_type="walk_away")
        self.assertEqual(engine.state.status, "ended")
        ok, code, _, _ = submit(
            engine, action_id="after-end", action_type="statement"
        )
        self.assertFalse(ok)
        self.assertEqual(code, "PHASE_CLOSED")

    def test_offer_side_effects(self):
        engine = make_engine()
        ok, code, message, events = submit(
            engine,
            action_id="cn-1",
            patch={"全球算力资源分配": "附带可核查机制"},
        )
        self.assertTrue(ok, f"{code}: {message}")
        self.assertEqual(engine.state.current_version, 1)
        self.assertEqual(len(engine.state.open_issues), 2)
        self.assertEqual(engine.state.action_points, 2)
        self.assertEqual(engine.state.phase, "bargaining")
        self.assertEqual(len(engine.state.offers), 1)
        self.assertTrue(events)

    def test_full_agreement(self):
        engine = full_engine()
        self.assertEqual(engine.state.terminal["type"], "FULL_AGREEMENT")
        self.assertEqual(engine.state.status, "ended")
        self.assertEqual(engine.state.phase, "ended")
        evaluation = engine.evaluate()
        self.assertEqual(evaluation["terminal_type"], "FULL_AGREEMENT")
        self.assertEqual(evaluation["agreement_quality"]["coverage"], 1.0)
        self.assertEqual(evaluation["agreement_quality"]["missing"], [])
        self.assertTrue(evaluation["batna_comparison"]["cn"]["better_than_batna"])
        self.assertTrue(evaluation["batna_comparison"]["us"]["better_than_batna"])
        self.assertIsNone(evaluation["learning_performance"])

    def test_partial_agreement(self):
        engine = make_engine()
        submit(engine, action_id="cn-1", patch={"全球算力资源分配": "附带可核查机制"})
        terminal = engine.finish()
        self.assertEqual(terminal["type"], "PARTIAL_AGREEMENT")
        evaluation = engine.evaluate()
        self.assertAlmostEqual(
            evaluation["agreement_quality"]["coverage"], 0.3333, places=4
        )
        self.assertEqual(
            evaluation["agreement_quality"]["missing"],
            ["前沿模型评测门槛", "数据跨境流动"],
        )

    def test_walk_away(self):
        engine = make_engine()
        ok, code, message, _ = submit(
            engine, action_id="walk", action_type="walk_away"
        )
        self.assertTrue(ok, f"{code}: {message}")
        self.assertEqual(engine.state.terminal["type"], "WITHDRAWAL")

    def test_deadlock_after_two_rounds_without_offer(self):
        engine = make_engine()
        first = engine.next_round()
        self.assertIsNone(first["terminal"])
        second = engine.next_round()
        self.assertEqual(second["terminal"]["type"], "DEADLOCK")
        self.assertEqual(engine.state.status, "ended")

    def test_rounds_exhausted(self):
        engine = make_engine(max_rounds=1, deadlock_rounds=99)
        result = engine.next_round()
        self.assertEqual(result["terminal"]["type"], "ROUNDS_EXHAUSTED")

    def test_private_state_filtered_by_viewer(self):
        engine = make_engine()
        self.assertEqual(
            list(engine.public_state("cn")["private_state_by_party"].keys()), ["cn"]
        )
        self.assertEqual(
            list(engine.public_state("us")["private_state_by_party"].keys()), ["us"]
        )
        self.assertEqual(engine.public_state("fr")["private_state_by_party"], {})
        self.assertEqual(engine.public_state()["private_state_by_party"], {})
        self.assertEqual(
            engine.public_state("cn")["private_state_by_party"]["cn"]["bottom_line"],
            "可接受附带可核查机制的算力分配安排",
        )

    def test_probe_and_statement_change_nothing_but_points(self):
        engine = make_engine()
        indices = {k: dict(v) for k, v in engine.state.indices.items()}
        ok, code, _, _ = submit(engine, action_id="probe-1", action_type="probe")
        self.assertTrue(ok, code)
        ok, code, _, _ = submit(engine, action_id="stmt-1", action_type="statement")
        self.assertTrue(ok, code)
        self.assertEqual(engine.state.current_version, 0)
        self.assertEqual(engine.state.offers, [])
        self.assertEqual(engine.state.action_points, 1)
        self.assertEqual(engine.state.indices, indices)
        self.assertEqual(len(engine.state.behavior_log), 2)

    def test_terminal_types_constant(self):
        self.assertEqual(
            set(TERMINAL_TYPES),
            {
                "FULL_AGREEMENT",
                "PARTIAL_AGREEMENT",
                "WITHDRAWAL",
                "DEADLOCK",
                "ROUNDS_EXHAUSTED",
            },
        )


if __name__ == "__main__":
    unittest.main()
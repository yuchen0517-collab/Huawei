import unittest

from tests import make_engine, submit


def prepared_engine():
    engine = make_engine(action_points_per_round=6)
    ok, code, message, _ = submit(
        engine,
        action_id="base-1",
        actor="cn",
        action_type="offer",
        patch={"全球算力资源分配": "附带可核查机制"},
    )
    assert ok, f"{code}: {message}"
    return engine


def declare_final(engine, action_id="final-1"):
    return submit(
        engine,
        action_id=action_id,
        actor="cn",
        action_type="final_offer",
        patch={"数据跨境流动": "白名单互认"},
    )


class FinalOfferTest(unittest.TestCase):
    def test_first_declaration_records_version(self):
        engine = prepared_engine()
        ok, code, message, events = declare_final(engine)
        self.assertTrue(ok, f"{code}: {message}")
        self.assertEqual(engine.state.final_offer_declared_by["cn"], 2)
        self.assertEqual(engine.state.current_version, 2)

    def test_second_declaration_rejected_and_state_unchanged(self):
        engine = prepared_engine()
        declare_final(engine)
        before = {
            "version": engine.state.current_version,
            "points": engine.state.action_points,
            "indices": {k: dict(v) for k, v in engine.state.indices.items()},
            "seen": list(engine.state.seen_action_ids),
        }
        ok, code, message, events = declare_final(engine, "final-2")
        self.assertFalse(ok)
        self.assertEqual(code, "FINAL_OFFER_ALREADY_DECLARED")
        self.assertTrue(message)
        self.assertEqual(events, [])
        self.assertEqual(engine.state.current_version, before["version"])
        self.assertEqual(engine.state.action_points, before["points"])
        self.assertEqual(engine.state.indices, before["indices"])
        self.assertEqual(engine.state.seen_action_ids, before["seen"])

    def test_offer_after_declaration_locked(self):
        engine = prepared_engine()
        declare_final(engine)
        clauses_before = engine.state.offers[-1].clauses.copy()
        ok, code, _, _ = submit(
            engine,
            action_id="late-offer",
            actor="cn",
            action_type="offer",
            patch={"前沿模型评测门槛": 40},
        )
        self.assertFalse(ok)
        self.assertEqual(code, "FINAL_OFFER_LOCKED")
        self.assertEqual(engine.state.offers[-1].clauses, clauses_before)

    def test_counter_offer_after_declaration_locked(self):
        engine = prepared_engine()
        declare_final(engine)
        ok, code, _, _ = submit(
            engine,
            action_id="late-counter",
            actor="cn",
            action_type="counter_offer",
            patch={"前沿模型评测门槛": 40},
        )
        self.assertFalse(ok)
        self.assertEqual(code, "FINAL_OFFER_LOCKED")

    def test_conditional_exchange_after_declaration_locked(self):
        engine = prepared_engine()
        declare_final(engine)
        ok, code, _, _ = submit(
            engine,
            action_id="late-exchange",
            actor="cn",
            action_type="conditional_exchange",
            patch={"前沿模型评测门槛": 40},
        )
        self.assertFalse(ok)
        self.assertEqual(code, "FINAL_OFFER_LOCKED")

    def test_accept_allowed_after_declaration(self):
        engine = prepared_engine()
        declare_final(engine)
        ok, code, message, _ = submit(
            engine,
            action_id="us-counter",
            actor="us",
            action_type="counter_offer",
            patch={"前沿模型评测门槛": 50},
        )
        self.assertTrue(ok, f"{code}: {message}")
        ok, code, message, _ = submit(
            engine, action_id="cn-accept", actor="cn", action_type="accept"
        )
        self.assertTrue(ok, f"{code}: {message}")
        self.assertEqual(engine.state.terminal["type"], "FULL_AGREEMENT")

    def test_reject_allowed_after_declaration(self):
        engine = prepared_engine()
        declare_final(engine)
        ok, code, message, _ = submit(
            engine, action_id="cn-reject", actor="cn", action_type="reject"
        )
        self.assertTrue(ok, f"{code}: {message}")
        self.assertEqual(engine.state.status, "active")

    def test_walk_away_allowed_after_declaration(self):
        engine = prepared_engine()
        declare_final(engine)
        ok, code, message, _ = submit(
            engine, action_id="cn-walk", actor="cn", action_type="walk_away"
        )
        self.assertTrue(ok, f"{code}: {message}")
        self.assertEqual(engine.state.terminal["type"], "WITHDRAWAL")

    def test_final_offer_without_patch_rejected(self):
        engine = make_engine()
        ok, code, _, _ = submit(
            engine, action_id="empty-final", actor="cn", action_type="final_offer"
        )
        self.assertFalse(ok)
        self.assertEqual(code, "FINAL_OFFER_EMPTY")

    def test_counterpart_still_can_counter(self):
        engine = prepared_engine()
        declare_final(engine)
        ok, code, message, _ = submit(
            engine,
            action_id="us-counter",
            actor="us",
            action_type="counter_offer",
            patch={"前沿模型评测门槛": 50},
        )
        self.assertTrue(ok, f"{code}: {message}")
        self.assertEqual(engine.state.current_version, 3)

    def test_phase_becomes_closing(self):
        engine = prepared_engine()
        declare_final(engine)
        self.assertEqual(engine.state.phase, "closing")

    def test_final_offer_declared_event_exists(self):
        engine = prepared_engine()
        declare_final(engine)
        events = [
            event
            for event in engine.state.public_events
            if event.get("type") == "final_offer_declared"
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["party"], "cn")
        self.assertEqual(events[0]["version"], 2)

    def test_statement_allowed_after_declaration(self):
        engine = prepared_engine()
        declare_final(engine)
        ok, code, message, _ = submit(
            engine, action_id="cn-statement", actor="cn", action_type="statement"
        )
        self.assertTrue(ok, f"{code}: {message}")


if __name__ == "__main__":
    unittest.main()
import unittest
from copy import deepcopy

from agent.audit import audit_agreement
from engine.state import Offer
from tests import full_engine, make_engine, submit


def clean_agreement(engine):
    return engine.state.agreement


class AuditTest(unittest.TestCase):
    def test_no_agreement(self):
        engine = make_engine()
        result = audit_agreement(engine.state, engine.scenario)
        self.assertFalse(result["ok"])
        self.assertEqual(result["summary"]["blocking"], 1)
        self.assertEqual(result["issues"][0]["check"], "clause_missing")

    def test_missing_clauses(self):
        engine = make_engine()
        submit(engine, action_id="cn-1", patch={"全球算力资源分配": "附带可核查机制"})
        engine.finish()
        result = audit_agreement(engine.state, engine.scenario)
        self.assertFalse(result["ok"])
        missing = [
            issue for issue in result["issues"] if issue["check"] == "clause_missing"
        ]
        self.assertEqual(len(missing), 2)
        self.assertTrue(all(item["severity"] == "blocking" for item in missing))

    def test_clean_agreement(self):
        engine = full_engine()
        result = audit_agreement(engine.state, engine.scenario)
        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"], {"blocking": 0, "warning": 0})
        self.assertEqual(result["issues"], [])

    def test_version_mismatch(self):
        engine = full_engine()
        agreement = deepcopy(clean_agreement(engine))
        agreement.version = 99
        result = audit_agreement(engine.state, engine.scenario, agreement)
        self.assertFalse(result["ok"])
        checks = [issue["check"] for issue in result["issues"]]
        self.assertIn("version_mismatch", checks)

    def test_redline_conflict(self):
        engine = full_engine()
        agreement = deepcopy(clean_agreement(engine))
        agreement.clauses["全球算力资源分配"] = {
            "option": "市场主导",
            "note": "测试越线",
        }
        result = audit_agreement(engine.state, engine.scenario, agreement)
        self.assertFalse(result["ok"])
        conflicts = [
            issue for issue in result["issues"] if issue["check"] == "redline_conflict"
        ]
        self.assertTrue(conflicts)
        self.assertTrue(any(item["party"] == "cn" for item in conflicts))

    def test_vague_condition(self):
        engine = full_engine()
        agreement = deepcopy(clean_agreement(engine))
        agreement.conditions = ["后续安排另行商定"]
        result = audit_agreement(engine.state, engine.scenario, agreement)
        self.assertTrue(result["ok"])  # 只有 warning，blocking 为 0
        checks = [issue["check"] for issue in result["issues"]]
        self.assertIn("vague_condition", checks)
        self.assertEqual(result["summary"]["warning"], 1)

    def test_unverifiable_condition(self):
        engine = full_engine()
        agreement = deepcopy(clean_agreement(engine))
        agreement.conditions = ["双方保持沟通"]
        result = audit_agreement(engine.state, engine.scenario, agreement)
        checks = [issue["check"] for issue in result["issues"]]
        self.assertIn("unverifiable_condition", checks)
        self.assertEqual(result["summary"]["warning"], 1)

    def test_verifiable_condition_passes(self):
        engine = full_engine()
        agreement = deepcopy(clean_agreement(engine))
        agreement.conditions = ["2027 年提交核查报告"]
        result = audit_agreement(engine.state, engine.scenario, agreement)
        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["warning"], 0)

    def test_audit_does_not_modify_state(self):
        engine = full_engine()
        offers_len = len(engine.state.offers)
        events_len = len(engine.state.public_events)
        indices = {k: dict(v) for k, v in engine.state.indices.items()}
        agreement = deepcopy(engine.state.agreement.to_dict())

        audit_agreement(engine.state, engine.scenario)

        self.assertEqual(len(engine.state.offers), offers_len)
        self.assertEqual(len(engine.state.public_events), events_len)
        self.assertEqual(engine.state.indices, indices)
        self.assertEqual(engine.state.agreement.to_dict(), agreement)

    def test_multiple_issues_reported_together(self):
        engine = make_engine()
        agreement = Offer(
            action_id="bad",
            actor="cn",
            version=engine.state.current_version,
            clauses={
                "全球算力资源分配": {"option": "市场主导", "note": "越线"}
            },
            created_round=1,
            kind="agreement",
            conditions=["后续安排另行商定", "双方保持沟通"],
        )
        result = audit_agreement(engine.state, engine.scenario, agreement)
        checks = {issue["check"] for issue in result["issues"]}
        self.assertIn("clause_missing", checks)
        self.assertIn("redline_conflict", checks)
        self.assertIn("vague_condition", checks)
        self.assertIn("unverifiable_condition", checks)
        self.assertGreaterEqual(result["summary"]["blocking"], 3)
        self.assertGreaterEqual(result["summary"]["warning"], 2)


if __name__ == "__main__":
    unittest.main()
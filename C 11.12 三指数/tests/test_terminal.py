"""终局评价的 viewer 裁剪与预留字段回归。

覆盖两条隔离口径：
- `redline_check` 按 viewer 裁剪，与 `batna_comparison` 一致；
- `speaker_score` / `est_confidence` 只在出口占位为 None，不携带任何数值。
"""

import unittest

from load_scenario_bridge import evaluate_for
from tests import full_engine, make_engine


class RedlineViewerTest(unittest.TestCase):
    def test_internal_evaluate_keeps_full_boolean_table(self):
        """无 viewer 是内部全量：每个议题的双方值都必须是 bool。"""
        engine = full_engine()
        check = engine.evaluate()["redline_check"]
        self.assertTrue(check)
        for clause, row in check.items():
            with self.subTest(clause=clause):
                self.assertEqual(set(row), {"cn", "us"})
                for party, value in row.items():
                    self.assertIs(type(value), bool, f"{clause}.{party}={value!r}")

    def test_viewer_cn_hides_other_party_booleans(self):
        """viewer="cn"：己方仍是 bool，他方必须是 None。"""
        engine = full_engine()
        check = engine.evaluate("cn")["redline_check"]
        self.assertTrue(check)
        for clause, row in check.items():
            with self.subTest(clause=clause):
                self.assertIs(type(row["cn"]), bool)
                self.assertIsNone(row["us"])

    def test_unknown_viewer_sees_no_booleans(self):
        """未知 viewer（root / *）不得因为字符串像特权身份而拿到任何布尔值。"""
        engine = full_engine()
        for viewer in ("root", "*"):
            with self.subTest(viewer=viewer):
                check = engine.evaluate(viewer)["redline_check"]
                self.assertTrue(check)
                for clause, row in check.items():
                    for party, value in row.items():
                        self.assertIsNone(value, f"{clause}.{party}={value!r}")

    def test_redline_check_empty_before_agreement(self):
        """未终局、无 agreement 时没有可核对的红线表，返回空 dict。"""
        engine = make_engine()
        self.assertIsNone(engine.state.agreement)
        self.assertEqual(engine.evaluate()["redline_check"], {})
        self.assertEqual(engine.evaluate("cn")["redline_check"], {})

    def test_batna_and_redline_share_the_same_boundary(self):
        """同一个 viewer 下，两条隔离口径必须同时遮住他方信息。"""
        engine = full_engine()
        view = engine.evaluate("cn")
        self.assertIsNone(view["batna_comparison"]["us"]["net_gain"])
        self.assertTrue(view["redline_check"])
        for clause, row in view["redline_check"].items():
            with self.subTest(clause=clause):
                self.assertIsNone(row["us"])


class ReservedFieldTest(unittest.TestCase):
    def test_reserved_fields_are_none_on_state(self):
        engine = full_engine()
        self.assertIsNone(engine.state.speaker_score)
        self.assertIsNone(engine.state.est_confidence)

    def test_reserved_fields_are_none_in_public_dict(self):
        engine = full_engine()
        for viewer in ("", "cn", "us"):
            with self.subTest(viewer=viewer):
                view = engine.state.to_public_dict(viewer)
                self.assertIn("speaker_score", view)
                self.assertIn("est_confidence", view)
                self.assertIsNone(view["speaker_score"])
                self.assertIsNone(view["est_confidence"])

    def test_reserved_fields_are_none_in_archive_dict(self):
        engine = full_engine()
        archive = engine.state.to_archive_dict()
        self.assertIn("speaker_score", archive)
        self.assertIn("est_confidence", archive)
        self.assertIsNone(archive["speaker_score"])
        self.assertIsNone(archive["est_confidence"])

    def test_public_dict_private_still_single_viewer(self):
        """回归：新增两个公开键不得放宽 private_state_by_party 的过滤。"""
        engine = full_engine()
        self.assertEqual(
            set(engine.state.to_public_dict("cn")["private_state_by_party"]), {"cn"}
        )
        self.assertEqual(
            set(engine.state.to_public_dict("us")["private_state_by_party"]), {"us"}
        )
        self.assertEqual(engine.state.to_public_dict("root")["private_state_by_party"], {})
        self.assertEqual(engine.state.to_public_dict("")["private_state_by_party"], {})


class EvaluateForRedlineIsolationTest(unittest.TestCase):
    """evaluate_for 必须把 redline_check 也按 viewer 裁剪，防止反推对方红线。"""

    def test_cn_view_redline_us_is_none_and_cn_is_bool(self):
        result = evaluate_for(full_engine(), "cn")
        check = result["redline_check"]
        self.assertTrue(check)
        clause = next(iter(check))
        self.assertIsNone(check[clause]["us"])
        self.assertIs(type(check[clause]["cn"]), bool)

    def test_cn_view_hides_us_on_every_clause(self):
        result = evaluate_for(full_engine(), "cn")
        self.assertTrue(result["redline_check"])
        for clause, row in result["redline_check"].items():
            with self.subTest(clause=clause):
                self.assertIsNone(row["us"])
                self.assertIs(type(row["cn"]), bool)

    def test_us_view_is_symmetric(self):
        result = evaluate_for(full_engine(), "us")
        self.assertTrue(result["redline_check"])
        for clause, row in result["redline_check"].items():
            with self.subTest(clause=clause):
                self.assertIsNone(row["cn"])
                self.assertIs(type(row["us"]), bool)

    def test_empty_viewer_still_raises(self):
        with self.assertRaises(ValueError):
            evaluate_for(full_engine(), "")


if __name__ == "__main__":
    unittest.main()
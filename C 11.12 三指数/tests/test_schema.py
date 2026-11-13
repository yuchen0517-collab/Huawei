import unittest

from engine.validator import ACTION_TYPES, validate_schema
from tests import make_action

A_EXAMPLE = {
    "action_id": "us-counter-offer-0001",
    "actor": "us",
    "action_type": "counter_offer",
    "card_id": None,
    "offer_patch": {
        "全球算力资源分配": {
            "option": "采用附带可核查机制的全球算力资源分配方案",
            "note": "美国提出反报价，并以中国接受可核查机制作为推进算力资源分配安排的交换条件。",
        }
    },
    "conditions": ["中国接受可核查机制，对全球算力资源分配方案的落实情况进行核查。"],
    "expected_effect": "推动中国接受可核查机制，为双方就全球算力资源分配方案达成一致创造条件。",
    "public_message": (
        "美国提出反报价：美方愿继续协商全球算力资源分配方案，但中国接受可核查机制是推进这项安排的交换条件。"
        "该机制将用于核查双方对既定分配方案的执行情况，以增强安排的透明度和可验证性。"
    ),
}


class SchemaTest(unittest.TestCase):
    def test_a_example_passes_verbatim(self):
        ok, code, message = validate_schema(A_EXAMPLE)
        self.assertTrue(ok, f"{code}: {message}")

    def test_missing_public_message(self):
        action = make_action()
        del action["public_message"]
        ok, code, _ = validate_schema(action)
        self.assertFalse(ok)
        self.assertEqual(code, "SCHEMA_VIOLATION")

    def test_extra_effects_field(self):
        action = make_action()
        action["effects"] = []
        ok, code, _ = validate_schema(action)
        self.assertFalse(ok)
        self.assertEqual(code, "SCHEMA_VIOLATION")

    def test_unknown_action_type(self):
        action = make_action(action_type="demand")
        ok, code, _ = validate_schema(action)
        self.assertFalse(ok)
        self.assertEqual(code, "UNKNOWN_ACTION_TYPE")

    def test_card_id_number(self):
        action = make_action(card_id=7)
        ok, code, _ = validate_schema(action)
        self.assertFalse(ok)
        self.assertEqual(code, "SCHEMA_VIOLATION")

    def test_card_id_null(self):
        action = make_action(card_id=None)
        ok, code, _ = validate_schema(action)
        self.assertTrue(ok, f"{code}")

    def test_patch_entry_missing_note(self):
        action = make_action()
        action["offer_patch"] = {"全球算力资源分配": {"option": "附带可核查机制"}}
        ok, code, _ = validate_schema(action)
        self.assertFalse(ok)
        self.assertEqual(code, "SCHEMA_VIOLATION")

    def test_patch_entry_extra_key(self):
        action = make_action()
        action["offer_patch"] = {
            "全球算力资源分配": {
                "option": "附带可核查机制",
                "note": "说明",
                "extra": 1,
            }
        }
        ok, code, _ = validate_schema(action)
        self.assertFalse(ok)
        self.assertEqual(code, "SCHEMA_VIOLATION")

    def test_conditions_must_be_array(self):
        action = make_action()
        action["conditions"] = "中国接受可核查机制"
        ok, code, _ = validate_schema(action)
        self.assertFalse(ok)
        self.assertEqual(code, "SCHEMA_VIOLATION")

    def test_accept_with_patch_rejected(self):
        action = make_action(action_type="accept", patch={"数据跨境流动": "白名单互认"})
        ok, code, _ = validate_schema(action)
        self.assertFalse(ok)
        self.assertEqual(code, "PATCH_NOT_ALLOWED")

    def test_statement_with_patch_rejected(self):
        action = make_action(action_type="statement", patch={"数据跨境流动": "白名单互认"})
        ok, code, _ = validate_schema(action)
        self.assertFalse(ok)
        self.assertEqual(code, "PATCH_NOT_ALLOWED")

    def test_all_nine_action_types_pass_schema(self):
        for action_type in ACTION_TYPES:
            patch = (
                {"全球算力资源分配": "附带可核查机制"}
                if action_type
                in ("offer", "counter_offer", "conditional_exchange", "final_offer")
                else None
            )
            with self.subTest(action_type=action_type):
                ok, code, message = validate_schema(
                    make_action(action_type=action_type, patch=patch)
                )
                self.assertTrue(ok, f"{action_type}: {code} {message}")

    def test_direct_delta_field_on_action_rejected(self):
        action = make_action()
        action["interest_delta"] = 6
        ok, code, _ = validate_schema(action)
        self.assertFalse(ok)
        self.assertEqual(code, "SCHEMA_VIOLATION")

    def test_direct_delta_field_in_effect_label_rejected(self):
        action = make_action(
            labels=[
                {
                    "label": "personal_attack",
                    "magnitude": "major",
                    "interest_delta": 6,
                }
            ]
        )
        ok, code, _ = validate_schema(action)
        self.assertFalse(ok)
        self.assertEqual(code, "SCHEMA_VIOLATION")


if __name__ == "__main__":
    unittest.main()
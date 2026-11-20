"""BACKLOG #2：三份交付场景必须各自携带 index_rules，而不是借用内置表。

此前场景里没有 `index_rules`，适配层会借 `C 11.12 三指数/scenarios/demo_scenario.json`
的整表并打 `DEFAULT_INDEX_RULES` 警告。现在每份场景都显式声明自己的规则，
下面锁定「存在、可校验、键集完整」三件事。
"""

import json
import unittest
from pathlib import Path

from agent.scenario.models import EFFECT_LABELS, validate_scenario

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = (
    "main_chip_controls.json",
    "no_zopa_variant.json",
    "backup_dst_bilateral.json",
)
OPTIONAL_KEYS = {"initial", "scale", "sensitivity"}


class ScenarioIndexRulesTest(unittest.TestCase):
    def load(self, name: str) -> dict:
        with open(ROOT / "data" / "scenarios" / name, encoding="utf-8-sig") as handle:
            return json.load(handle)

    def test_every_scenario_ships_its_own_index_rules(self):
        for name in SCENARIOS:
            with self.subTest(scenario=name):
                data = self.load(name)
                rules = data.get("index_rules")
                self.assertIsInstance(rules, dict, f"{name} 缺少 index_rules")
                self.assertEqual(validate_scenario(data), [], f"{name} 契约校验未通过")
                self.assertEqual(set(rules) - OPTIONAL_KEYS, set(EFFECT_LABELS))
                self.assertEqual(rules["scale"], [0, 100])

    def test_initial_and_sensitivity_cover_every_party(self):
        for name in SCENARIOS:
            with self.subTest(scenario=name):
                data = self.load(name)
                rules = data["index_rules"]
                party_ids = {party["party_id"] for party in data["parties"]}
                self.assertEqual(set(rules["initial"]), party_ids)
                self.assertEqual(set(rules["sensitivity"]), party_ids)
                for block in rules["initial"].values():
                    self.assertEqual(set(block), {"image", "trust"})
                    for value in block.values():
                        self.assertTrue(0 <= value <= 100)
                for block in rules["sensitivity"].values():
                    self.assertEqual(set(block), {"image", "trust"})
                    for value in block.values():
                        self.assertTrue(0 < value <= 3)


if __name__ == "__main__":
    unittest.main()

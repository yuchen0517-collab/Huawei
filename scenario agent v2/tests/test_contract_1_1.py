"""契约 1.1 新增字段的回归测试：R12 终局规则 / R13 开局现状 / R14 运行参数。"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.scenario.models import (  # noqa: E402
    Scenario,
    TerminalRules,
    validate_index_rules,
    validate_scenario,
)

EXAMPLE_PATH = ROOT / "docs" / "contracts" / "scenario.example.json"
SCHEMA_PATH = ROOT / "docs" / "contracts" / "scenario.schema.json"
INDEX_RULES_PATH = ROOT / "docs" / "contracts" / "index_rules.v1.json"


def load_example() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def load_index_rules() -> dict:
    return json.loads(INDEX_RULES_PATH.read_text(encoding="utf-8"))


def variant(mutate) -> dict:
    data = copy.deepcopy(load_example())
    mutate(data)
    return data


def codes(data: dict) -> set[str]:
    return {problem.code for problem in validate_scenario(data)}


def test_example_passes_all_rules():
    assert validate_scenario(load_example()) == []


def test_example_matches_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(load_example()))
    assert errors == [], [f"{list(e.path)}: {e.message}" for e in errors]


def test_scenario_with_index_rules_matches_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    data = load_example()
    data["index_rules"] = load_index_rules()
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(data))
    assert errors == [], [f"{list(e.path)}: {e.message}" for e in errors]


# ---------------------------------------------------------------------------
# R12 终局规则
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "field",
    ["allow_walk_away", "accept_requires_no_open_issue", "partial_agreement_allowed"],
)
def test_r12_rejects_missing_bool(field):
    def drop(data):
        data["terminal_rules"].pop(field)

    assert codes(variant(drop)) == {"R12_terminal_rules"}


def test_r12_rejects_string_bool():
    def mutate(data):
        data["terminal_rules"]["allow_walk_away"] = "false"

    assert "R12_terminal_rules" in codes(variant(mutate))


def test_r12_rejects_integer_bool():
    def mutate(data):
        data["terminal_rules"]["partial_agreement_allowed"] = 1

    assert "R12_terminal_rules" in codes(variant(mutate))


def test_r12_accepts_deadlock_rounds():
    def mutate(data):
        data["terminal_rules"]["deadlock_rounds"] = 2

    assert codes(variant(mutate)) == set()


def test_r12_rejects_deadlock_rounds_over_max_rounds():
    def mutate(data):
        data["terminal_rules"]["deadlock_rounds"] = 9
        data["max_rounds"] = 8

    assert "R12_terminal_rules" in codes(variant(mutate))


def test_r12_rejects_deadlock_rounds_bool():
    def mutate(data):
        data["terminal_rules"]["deadlock_rounds"] = True

    assert "R12_terminal_rules" in codes(variant(mutate))


def test_terminal_rules_from_dict_does_not_coerce_strings():
    rules = TerminalRules.from_dict({"allow_walk_away": "false", "partial_agreement_allowed": 1})
    assert rules.allow_walk_away is False
    assert rules.partial_agreement_allowed is False
    assert rules.deadlock_rounds == 2


# ---------------------------------------------------------------------------
# R13 开局现状
# ---------------------------------------------------------------------------
def test_r13_rejects_initial_out_of_range():
    def mutate(data):
        data["issues"][0]["initial"] = 99

    assert "R13_initial" in codes(variant(mutate))


def test_r13_rejects_initial_off_step_grid():
    def mutate(data):
        data["issues"][0]["initial"] = 18.5

    assert "R13_initial" in codes(variant(mutate))


def test_r13_rejects_bad_option_id():
    def mutate(data):
        data["issues"][2]["initial"] = "nope"

    assert "R13_initial" in codes(variant(mutate))


def test_r13_rejects_unknown_initial_ref():
    def mutate(data):
        data["issues"][0]["initial_ref"] = "NOT-A-FACT"

    assert "R13_initial" in codes(variant(mutate))


def test_r13_accepts_fact_ref_and_assumption_ref():
    def mutate(data):
        data["issues"][0]["initial_ref"] = "CN-01"
        data["issues"][1]["initial_ref"] = data["assumptions"][0]["assumption_id"]

    assert codes(variant(mutate)) == set()


def test_r13_rejects_empty_initial_ref():
    def mutate(data):
        data["issues"][0]["initial_ref"] = ""

    assert "R13_initial" in codes(variant(mutate))


# ---------------------------------------------------------------------------
# R14 运行参数
# ---------------------------------------------------------------------------
def test_r14_accepts_defaults():
    assert codes(load_example()) == set()


def test_r14_rejects_action_points_out_of_range():
    def mutate(data):
        data["runtime"]["action_points_per_round"] = 6

    assert "R14_runtime" in codes(variant(mutate))


# ---------------------------------------------------------------------------
# R15 行为标签表（13 标签 × 三档）
# ---------------------------------------------------------------------------
def test_index_rules_table_is_valid():
    assert validate_index_rules(load_index_rules()) == []


def test_index_rules_attached_to_scenario_passes():
    data = load_example()
    data["index_rules"] = load_index_rules()
    assert validate_scenario(data) == []


def test_r15_rejects_missing_label():
    table = load_index_rules()
    table.pop("procedural")
    data = load_example()
    data["index_rules"] = table
    assert "R15_index_rules" in codes(data)


def test_r15_rejects_missing_magnitude():
    table = load_index_rules()
    table["procedural"].pop("major")
    data = load_example()
    data["index_rules"] = table
    assert "R15_index_rules" in codes(data)


def test_r15_rejects_delta_out_of_range():
    table = load_index_rules()
    table["hardline_stance"]["major"]["interest_delta"] = 11
    data = load_example()
    data["index_rules"] = table
    assert "R15_index_rules" in codes(data)


def test_r15_rejects_delta_not_integer():
    table = load_index_rules()
    table["hardline_stance"]["slight"]["trust_delta"] = "2"
    data = load_example()
    data["index_rules"] = table
    assert "R15_index_rules" in codes(data)


def test_r15_rejects_unknown_label():
    table = load_index_rules()
    table["warn"] = {
        "slight": {"interest_delta": 1, "image_delta": 1, "trust_delta": 1},
        "moderate": {"interest_delta": 1, "image_delta": 1, "trust_delta": 1},
        "major": {"interest_delta": 1, "image_delta": 1, "trust_delta": 1},
    }
    data = load_example()
    data["index_rules"] = table
    assert "R15_index_rules" in codes(data)


def test_r15_rejects_bad_initial():
    table = load_index_rules()
    table["initial"]["image"] = 101
    data = load_example()
    data["index_rules"] = table
    assert "R15_index_rules" in codes(data)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
def test_scenario_dataclass_keeps_initial_and_runtime():
    scenario = Scenario.from_dict(load_example())
    assert scenario.issues[0].initial == 18
    assert scenario.issues[2].initial == "bilateral"
    assert scenario.runtime["action_points_per_round"] == 3
    assert scenario.terminal_rules.deadlock_rounds == 2
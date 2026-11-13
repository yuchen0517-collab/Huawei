import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.scenario.models import validate_scenario

EXAMPLE_PATH = ROOT / "docs" / "contracts" / "scenario.example.json"


def load_example() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def build_variant(mutate) -> dict:
    data = copy.deepcopy(load_example())
    mutate(data)
    return data


def _r1_weight(data: dict) -> None:
    data["private_state_by_party"]["cn"]["goals"][0]["weight"] = 0.55


def _r2_target(data: dict) -> None:
    data["private_state_by_party"]["cn"]["goals"][0]["target"] = 99


def _r3_step(data: dict) -> None:
    data["issues"][0]["range"]["step"] = 0


def _r4_public_claim(data: dict) -> None:
    data["parties"][0]["public_position"] = "主张受管制先进制程门槛不低于 20"


def _r5_utility(data: dict) -> None:
    data["private_state_by_party"]["cn"]["batna"]["utility"] = 0


def _r6_ranking(data: dict) -> None:
    data["private_state_by_party"]["cn"]["priority_ranking"] = [
        "export_license_scope",
        "license_validity_months",
    ]


def _r7_uncovered(data: dict) -> None:
    data["private_state_by_party"]["cn"]["goals"] = [
        {
            "issue_id": "export_license_scope",
            "target": 28,
            "weight": 1.0,
            "direction": "higher_better",
        }
    ]
    data["private_state_by_party"]["us"]["goals"] = [
        {
            "issue_id": "export_license_scope",
            "target": 14,
            "weight": 1.0,
            "direction": "lower_better",
        }
    ]


VIOLATIONS = [
    ("R1_weight_sum", _r1_weight),
    ("R2_target_in_range", _r2_target),
    ("R3_range_sane", _r3_step),
    ("R4_redline_consistency", _r4_public_claim),
    ("R5_batna_sane", _r5_utility),
    ("R6_priority_ranking", _r6_ranking),
    ("R7_every_issue_covered", _r7_uncovered),
]

IDS = [code for code, _ in VIOLATIONS]


@pytest.mark.parametrize("code, mutate", VIOLATIONS, ids=IDS)
def test_rejects_single_violation(code, mutate):
    problems = validate_scenario(build_variant(mutate))
    detected = {problem.code for problem in problems}
    detail = [(problem.code, problem.path, problem.message) for problem in problems]
    assert detected == {code}, f"{code} 用例应只命中自身，实际: {detail}"


@pytest.mark.parametrize("code", IDS, ids=IDS)
def test_example_passes(code):
    problems = validate_scenario(load_example())
    detail = [(problem.code, problem.path, problem.message) for problem in problems]
    assert not problems, f"示例应为空列表，实际: {detail}"
    assert code not in {problem.code for problem in problems}

def test_empty_scenario_reports_r0():
    codes = {problem.code for problem in validate_scenario({})}
    assert "R0_required_fields" in codes


def test_missing_parties_reports_r0():
    def drop_parties(data):
        data.pop("parties", None)

    codes = {problem.code for problem in validate_scenario(build_variant(drop_parties))}
    assert "R0_required_fields" in codes


def test_single_party_reports_r0():
    def keep_single_party(data):
        data["parties"] = data["parties"][:1]

    codes = {problem.code for problem in validate_scenario(build_variant(keep_single_party))}
    assert "R0_required_fields" in codes


def test_unknown_scenario_type_reports_r8():
    def set_unknown_type(data):
        data["scenario_type"] = "乱写"

    codes = {problem.code for problem in validate_scenario(build_variant(set_unknown_type))}
    assert "R8_enum_values" in codes


def test_unknown_goal_direction_reports_r8():
    def set_unknown_direction(data):
        data["private_state_by_party"]["cn"]["goals"][0]["direction"] = "whatever"

    codes = {problem.code for problem in validate_scenario(build_variant(set_unknown_direction))}
    assert "R8_enum_values" in codes
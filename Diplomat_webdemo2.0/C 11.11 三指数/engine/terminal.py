"""五类终局判定与六字段评价。"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional

from .indices import initial_plan, round_half_up, utility
from .validator import (
    clause_map,
    clause_names,
    is_redline_violation,
    option_value,
    party_ids,
)

TERMINAL_TYPES = (
    "FULL_AGREEMENT",
    "PARTIAL_AGREEMENT",
    "WITHDRAWAL",
    "DEADLOCK",
    "ROUNDS_EXHAUSTED",
)

TERMINAL_LABELS = {
    "FULL_AGREEMENT": "完整协议",
    "PARTIAL_AGREEMENT": "部分协议",
    "WITHDRAWAL": "退出谈判",
    "DEADLOCK": "僵局",
    "ROUNDS_EXHAUSTED": "轮次耗尽",
}


def coverage(agreement_clauses: Dict[str, dict], scenario: dict) -> tuple[list, list]:
    names = clause_names(scenario)
    covered = [name for name in names if name in agreement_clauses]
    missing = [name for name in names if name not in agreement_clauses]
    return covered, missing


def agreement_quality(state, scenario: dict) -> dict:
    if state.agreement is None:
        return {
            "coverage": 0.0,
            "covered": [],
            "missing": clause_names(scenario),
            "mean_utility": None,
            "conditions_count": 0,
        }

    clauses = state.agreement.clauses
    covered, missing = coverage(clauses, scenario)
    total = len(clause_names(scenario))
    cov = (len(covered) / total) if total else 0.0

    plan = initial_plan(scenario)
    for name, entry in clauses.items():
        plan[name] = deepcopy(entry)
    utils = [utility(plan, party, scenario) for party in party_ids(scenario)]
    mean_utility = round_half_up(sum(utils) / len(utils) * 100.0) if utils else None

    return {
        "coverage": cov,
        "covered": covered,
        "missing": missing,
        "mean_utility": mean_utility,
        "conditions_count": len(state.agreement.conditions),
    }


def batna_comparison(state, scenario: dict, viewer: str = "") -> dict:
    """BATNA 对比。viewer 为空表示内部全量（复盘 / 审计 / 演示）。

    传入参与方 id 时只给该方真值；其余各方 batna / net_gain /
    better_than_batna 一律置 null，避免 net_gain = achieved - batna
    反推出对方底牌。achieved 来自公开指数，可以下发。
    """
    result = {}
    for party in scenario.get("parties", []):
        if isinstance(party, dict):
            party_id = party["id"]
            batna = party.get("batna")
        else:
            party_id = party
            batna = None
        achieved = int(state.indices.get(party_id, {}).get("interest", 0))
        hidden = bool(viewer) and party_id != viewer
        if batna is None or hidden:
            result[party_id] = {
                "batna": None,
                "achieved": achieved,
                "net_gain": None,
                "better_than_batna": None,
            }
            continue
        batna = int(batna)
        result[party_id] = {
            "batna": batna,
            "achieved": achieved,
            "net_gain": achieved - batna,
            "better_than_batna": achieved > batna,
        }
    return result


def redline_check(state, scenario: dict) -> dict:
    clauses = state.agreement.clauses if state.agreement else {}
    scenario_clauses = clause_map(scenario)
    result: Dict[str, Dict[str, bool]] = {}
    for name, entry in clauses.items():
        clause = scenario_clauses.get(name)
        if clause is None:
            continue
        option = option_value(entry)
        result[name] = {
            party: is_redline_violation(clause, option, party)
            for party in party_ids(scenario)
        }
    return result


def determine_terminal_type(state, scenario: dict) -> Optional[str]:
    """优先级：agreement → walk_away → 已结束无协议 → 僵局 → 轮次耗尽。"""
    if state.agreement is not None:
        covered, missing = coverage(state.agreement.clauses, scenario)
        if not missing:
            return "FULL_AGREEMENT"
        rules = scenario.get("terminal_rules", {}) or {}
        if rules.get("partial_agreement_allowed", True) is False:
            return "DEADLOCK"
        return "PARTIAL_AGREEMENT"

    for event in state.public_events:
        if event.get("type") == "action" and event.get("action_type") == "walk_away":
            return "WITHDRAWAL"

    if state.status == "ended":
        return "DEADLOCK"

    deadlock_rounds = int(scenario.get("deadlock_rounds", 2))
    if int(state.rounds_without_offer) >= deadlock_rounds:
        return "DEADLOCK"

    max_rounds = int(scenario.get("max_rounds", 12))
    if int(state.round) > max_rounds:
        return "ROUNDS_EXHAUSTED"

    return None


def build_terminal(state, scenario: dict, terminal_type: Optional[str] = None) -> dict:
    resolved = terminal_type or determine_terminal_type(state, scenario) or "DEADLOCK"
    quality = agreement_quality(state, scenario)
    return {
        "type": resolved,
        "label": TERMINAL_LABELS.get(resolved, resolved),
        "round": int(state.round),
        "coverage": quality["coverage"],
    }


def evaluate(state, scenario: dict, viewer: str = "") -> dict:
    """六字段评价。learning_performance 恒为 None，归成员D。

    viewer 为空是内部全量；传参与方 id 时，batna_comparison 只暴露该方真值。
    对外给玩家看的评价必须传 viewer，不得无参调用。
    """
    terminal_type = (
        state.terminal.get("type")
        if state.terminal
        else (determine_terminal_type(state, scenario) or "DEADLOCK")
    )

    evidence = [
        index
        for index, event in enumerate(state.public_events)
        if event.get("type")
        in ("action", "index_change", "final_offer_declared", "terminal")
    ]

    return {
        "terminal_type": terminal_type,
        "agreement_quality": agreement_quality(state, scenario),
        "batna_comparison": batna_comparison(state, scenario, viewer),
        "redline_check": redline_check(state, scenario),
        "learning_performance": None,
        "evidence_links": evidence,
    }
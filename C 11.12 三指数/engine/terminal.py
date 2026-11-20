"""五类终局判定与六字段评价。"""

from __future__ import annotations

from typing import Dict, List, Optional

from .indices import round_half_up, score
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


def package_utility(agreement_clauses: Dict[str, dict], scenario: dict, party: str) -> float:
    """只计「本次协议里真正写明的条款」的效用，0~1。

    部分协议里被搁置的议题不计入本次成交收益（手册 5.2：其余议题被明确搁置、
    延期或转入其他程序）。这与 B 的 `zopa.evaluate_deal` 同口径，否则同一份
    部分协议在 App 与 QA 里会给出相反结论。

    注意与过程指数 `interest` 的区别：`interest` 是「当前局面」（未谈成的条款
    按现状延续），`package_utility` 是「这份协议本身值多少」，用途不同。
    """
    total = 0.0
    for clause in scenario.get("clauses", []):
        entry = agreement_clauses.get(clause["name"])
        if entry is None:
            continue
        weight = float((clause.get("weights") or {}).get(party, 0.0))
        total += weight * score(clause, option_value(entry), party)
    return total


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

    utils = [
        package_utility(clauses, scenario, party) for party in party_ids(scenario)
    ]
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
        # 有协议时用「协议包效用」而不是过程指数：部分协议里被搁置的议题
        # 不属于本次成交收益，否则会与 B 的 zopa 口径得出相反结论。
        if state.agreement is not None:
            achieved = round_half_up(
                package_utility(state.agreement.clauses, scenario, party_id) * 100.0
            )
        else:
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


def redline_check(state, scenario: dict, viewer: str = "") -> dict:
    """红线核对。viewer 为空表示内部全量（复盘 / 审计 / 演示）。

    传入参与方 id 时只返回该方自己的布尔值；其余各方一律置 null。
    原实现无条件返回全部参与方的布尔表，终局有协议时前端可据此反推
    对方红线位置（R2 信息隔离），故按 viewer 裁剪，与 batna_comparison
    保持同一口径：未知 viewer 一律看不到任何他方布尔。
    """
    clauses = state.agreement.clauses if state.agreement else {}
    scenario_clauses = clause_map(scenario)
    result: Dict[str, Dict[str, Optional[bool]]] = {}
    for name, entry in clauses.items():
        clause = scenario_clauses.get(name)
        if clause is None:
            continue
        option = option_value(entry)
        result[name] = {
            party: (
                is_redline_violation(clause, option, party)
                if not viewer or party == viewer
                else None
            )
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

    viewer 为空是内部全量；传参与方 id 时，batna_comparison 与
    redline_check 都只暴露该方真值，他方一律置 null。
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
        "redline_check": redline_check(state, scenario, viewer),
        "learning_performance": None,
        "evidence_links": evidence,
    }
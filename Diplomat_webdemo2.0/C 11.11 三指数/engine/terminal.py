"""终局判断与结算评估。

增量说明：evaluate_agreement 增加三指数维度；evaluate 的 evidence_links
带上所有三指数变化事件的 ID。
"""

from __future__ import annotations

from copy import deepcopy

from .state import INDEX_NAMES


def _initial_indices(state, scenario) -> dict:
    rules = (scenario.get("index_rules", {}) or {}) if scenario else {}
    return deepcopy(rules.get("initial", {}))


def check_terminal(state, scenario: dict | None = None) -> dict:
    scenario = scenario or state.scenario or {}
    max_rounds = int(scenario.get("max_rounds", 12))

    if state.status in ("agreed", "collapsed", "ended"):
        return {"terminal": True, "reason": state.status}

    if state.agreement:
        return {"terminal": True, "reason": "agreement"}

    if int(state.round) > max_rounds:
        return {"terminal": True, "reason": "round_limit"}

    return {"terminal": False, "reason": None}


def evaluate_agreement(state, scenario: dict | None = None) -> dict:
    scenario = scenario or state.scenario or {}
    initial = _initial_indices(state, scenario)

    final = {party: dict(values) for party, values in state.indices.items()}
    changes: dict[str, dict[str, int]] = {}
    for party, values in final.items():
        base = initial.get(party, values)
        changes[party] = {
            name: int(values[name]) - int(base.get(name, values[name]))
            for name in INDEX_NAMES
        }

    interest_below_initial = [
        party
        for party in scenario.get("parties", final)
        if party in final
        and int(final[party]["interest"])
        < int(initial.get(party, final[party]).get("interest", final[party]["interest"]))
    ]

    return {
        "agreed": bool(state.agreement),
        "status": state.status,
        "clauses": deepcopy(state.offers),
        "final_indices": final,
        "initial_indices": initial,
        "index_changes": changes,
        "interest_below_initial": interest_below_initial,
        "is_loss": bool(interest_below_initial),
    }


def evaluate(state, scenario: dict | None = None) -> dict:
    scenario = scenario or state.scenario or {}
    agreement = evaluate_agreement(state, scenario)
    initial = agreement["initial_indices"]
    final = agreement["final_indices"]

    outcome_by_party: dict[str, str] = {}
    for party, values in final.items():
        base = initial.get(party, values)
        delta = int(values["interest"]) - int(
            base.get("interest", values["interest"])
        )
        outcome_by_party[party] = "win" if delta > 0 else ("loss" if delta < 0 else "draw")

    total_final = sum(values["interest"] for values in final.values())
    total_initial = sum(
        initial.get(party, values).get("interest", values["interest"])
        for party, values in final.items()
    )
    if total_final < total_initial:
        outcome = "loss"
    elif total_final > total_initial:
        outcome = "win"
    else:
        outcome = "draw"

    index_events = [
        event
        for event in state.public_events
        if event.get("type") == "index_change"
    ]

    return {
        "session_id": state.session_id,
        "status": state.status,
        "round": state.round,
        "outcome": outcome,
        "outcome_by_party": outcome_by_party,
        "agreement": agreement,
        "index_event_count": len(index_events),
        "evidence_links": [event["event_id"] for event in index_events],
    }
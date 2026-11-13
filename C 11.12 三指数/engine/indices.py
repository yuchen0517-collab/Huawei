"""三指数结算。

Interest：由条款效用计算，不由发言查表。
Image / Trust：只影响发言方，查表后乘该方敏感度。
模型只提供离散标签；数值由本模块算出并交给 state.apply_index_changes 写入。
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Dict, List, Tuple

from .state import NegotiationState
from .validator import (
    MAGNITUDES,
    clause_map,
    is_number,
    option_value,
    party_ids,
)

FALLBACK_LABELS = {
    "offer": ("constructive_proposal", "conditional_concession"),
    "counter_offer": ("constructive_proposal", "conditional_concession"),
    "conditional_exchange": ("constructive_proposal", "conditional_concession"),
    "final_offer": ("hardline_stance", "hardline_stance"),
    "accept": ("diplomatic_reframe", "keep_promise"),
    "reject": ("hardline_stance", "vague_stance"),
    "walk_away": ("hardline_stance", "betray_ally"),
    "probe": ("procedural", "procedural"),
    "statement": ("procedural", "procedural"),
}

INDEX_NAMES = ("interest", "image", "trust")


def round_half_up(value: float) -> int:
    """四舍五入（0.5 远离零），避免 Python 银行家舍入在结算边界产生歧义。"""
    if value >= 0:
        return int(math.floor(value + 0.5))
    return int(math.ceil(value - 0.5))


def closeness(value: float, ideal: float, low: float, high: float) -> float:
    span = float(high) - float(low)
    if span <= 0:
        return 1.0 if float(value) == float(ideal) else 0.0
    score = 1.0 - abs(float(value) - float(ideal)) / span
    return max(0.0, min(1.0, score))


def score(clause: dict, option, party: str) -> float:
    """统一打分接口，返回 0~1。未知 option 返回 0.0（由校验层报 UNKNOWN_OPTION）。"""
    if clause.get("type") == "numeric":
        position = (clause.get("positions") or {}).get(party, {})
        ideal = position.get("ideal", clause.get("initial"))
        low, high = clause.get("range", [0, 0])
        try:
            numeric = float(option)
        except (TypeError, ValueError):
            return 0.0
        return closeness(numeric, float(ideal), float(low), float(high))

    for item in clause.get("options", []):
        if item.get("id") == option:
            return float((item.get("score") or {}).get(party, 0.0))
    return 0.0


def initial_plan(scenario: dict) -> Dict[str, dict]:
    return {
        clause["name"]: {
            "option": clause.get("initial"),
            "note": "场景初始方案",
        }
        for clause in scenario.get("clauses", [])
    }


def _plan_option(plan: Dict[str, dict], clause: dict) -> object:
    entry = plan.get(clause["name"])
    if entry is None:
        return clause.get("initial")
    return option_value(entry)


def utility(plan: Dict[str, dict], party: str, scenario: dict) -> float:
    total = 0.0
    for clause in scenario.get("clauses", []):
        weight = float((clause.get("weights") or {}).get(party, 0.0))
        option = _plan_option(plan, clause)
        total += weight * score(clause, option, party)
    return total


def interest_value(plan: Dict[str, dict], party: str, scenario: dict) -> int:
    return round_half_up(utility(plan, party, scenario) * 100.0)


def initial_indices(scenario: dict) -> Dict[str, Dict[str, int]]:
    plan = initial_plan(scenario)
    rules = scenario.get("index_rules", {}) or {}
    initial = rules.get("initial", {}) or {}
    result: Dict[str, Dict[str, int]] = {}
    for party in party_ids(scenario):
        values = initial.get(party, {}) or {}
        result[party] = {
            "interest": interest_value(plan, party, scenario),
            "image": int(values.get("image", 50)),
            "trust": int(values.get("trust", 50)),
        }
    return result


def derive_magnitude(
    action: dict, base_plan: Dict[str, dict], new_plan: Dict[str, dict], scenario: dict
) -> str:
    """路径2：由 action_type 映射标签，由条款实际变动幅度决定档位。"""
    patch = action.get("offer_patch") or {}
    if not patch:
        return "slight"

    clauses = clause_map(scenario)
    action_type = action.get("action_type")
    actor = action.get("actor")
    ratios: List[float] = []

    for name, entry in patch.items():
        clause = clauses.get(name)
        if clause is None:
            continue
        old_entry = base_plan.get(name, {"option": clause.get("initial")})
        old = option_value(old_entry)
        new = entry.get("option")

        if clause.get("type") == "numeric":
            low, high = clause.get("range", [0, 0])
            span = float(high) - float(low)
            try:
                ratio = abs(float(new) - float(old)) / span if span > 0 else 0.0
            except (TypeError, ValueError):
                ratio = 0.0
            if action_type == "final_offer":
                position = (clause.get("positions") or {}).get(actor, {})
                ideal = position.get("ideal", clause.get("initial"))
                far_endpoint = low if abs(float(ideal) - float(high)) >= abs(
                    float(ideal) - float(low)
                ) else high
                if float(new) == float(far_endpoint):
                    ratio = 1.0
        else:
            options = [item["id"] for item in clause.get("options", [])]
            span = len(options) - 1
            if span > 0 and old in options and new in options:
                ratio = abs(options.index(new) - options.index(old)) / span
            else:
                ratio = 0.0
            if action_type == "final_offer" and options:
                lowest = min(
                    options,
                    key=lambda item: score(clause, item, actor),
                )
                if new == lowest:
                    ratio = 1.0

        ratios.append(min(1.0, max(0.0, ratio)))

    ratio = max(ratios) if ratios else 0.0
    if ratio < 0.15:
        return "slight"
    if ratio < 0.45:
        return "moderate"
    return "major"


def resolve_labels(
    action: dict, base_plan: Dict[str, dict], new_plan: Dict[str, dict], scenario: dict
) -> Tuple[List[dict], str]:
    """路径1 优先；没有 effect_labels 时走路径2 兜底。"""
    raw = action.get("effect_labels")
    if raw:
        labels = []
        for item in raw:
            labels.append(
                {
                    "label": item["label"],
                    "magnitude": item["magnitude"],
                    "clause": item.get("clause"),
                    "reason": item.get("reason", ""),
                    "target": "both",
                }
            )
        return labels, "effect_labels"

    action_type = action.get("action_type")
    image_label, trust_label = FALLBACK_LABELS[action_type]
    magnitude = derive_magnitude(action, base_plan, new_plan, scenario)
    return (
        [
            {
                "label": image_label,
                "magnitude": magnitude,
                "clause": None,
                "reason": "由 action_type 与条款变动幅度推导",
                "target": "image",
            },
            {
                "label": trust_label,
                "magnitude": magnitude,
                "clause": None,
                "reason": "由 action_type 与条款变动幅度推导",
                "target": "trust",
            },
        ],
        "fallback",
    )


def _table_delta(
    table: dict, sensitivity: dict, index: str, label: str, magnitude: str
) -> int:
    base = (table.get(label) or {}).get(magnitude)
    if base is None:
        return 0
    factor = float((sensitivity or {}).get(index, 1.0))
    return round_half_up(float(base) * factor)


def behaviour_delta(actor: str, item: dict, scenario: dict) -> Dict[str, int]:
    rules = scenario.get("index_rules", {}) or {}
    sensitivity = (rules.get("sensitivity") or {}).get(actor, {}) or {}
    image_table = rules.get("image_actions", {}) or {}
    trust_table = rules.get("trust_actions", {}) or {}

    label = item["label"]
    magnitude = item["magnitude"]
    target = item.get("target", "both")
    deltas = {"image": 0, "trust": 0}

    if target in ("image", "both"):
        deltas["image"] = _table_delta(
            image_table, sensitivity, "image", label, magnitude
        )
    if target in ("trust", "both"):
        deltas["trust"] = _table_delta(
            trust_table, sensitivity, "trust", label, magnitude
        )
    return deltas


def apply_effects(
    state: NegotiationState,
    scenario: dict,
    action: dict,
    base_plan: Dict[str, dict],
    new_plan: Dict[str, dict],
) -> Tuple[List[dict], dict]:
    """整批标签先算后写；任何异常都发生在写状态之前。"""
    labels, mode = resolve_labels(action, base_plan, new_plan, scenario)
    actor = action["actor"]

    new_interest = {
        party: interest_value(new_plan, party, scenario)
        for party in party_ids(scenario)
    }

    interest_changes: List[Tuple[str, str, int]] = []
    for party in party_ids(scenario):
        before = int(state.indices[party]["interest"])
        delta = new_interest[party] - before
        if delta != 0:
            interest_changes.append((party, "interest", delta))

    behaviour_total = {"image": 0, "trust": 0}
    for item in labels:
        deltas = behaviour_delta(actor, item, scenario)
        behaviour_total["image"] += deltas["image"]
        behaviour_total["trust"] += deltas["trust"]

    events: List[dict] = []
    action_id = action["action_id"]

    if interest_changes:
        events.extend(
            state.apply_index_changes(
                interest_changes,
                reason="条款效用重算",
                source=action_id,
            )
        )

    if behaviour_total["image"] != 0:
        events.extend(
            state.apply_index_changes(
                [(actor, "image", behaviour_total["image"])],
                reason="发言标签：" + "/".join(
                    f"{item['label']}:{item['magnitude']}" for item in labels
                ),
                source=action_id,
            )
        )
    if behaviour_total["trust"] != 0:
        events.extend(
            state.apply_index_changes(
                [(actor, "trust", behaviour_total["trust"])],
                reason="发言标签：" + "/".join(
                    f"{item['label']}:{item['magnitude']}" for item in labels
                ),
                source=action_id,
            )
        )

    entry = {
        "action_id": action_id,
        "actor": actor,
        "round": int(state.round),
        "action_type": action.get("action_type"),
        "label_mode": mode,
        "labels": deepcopy(labels),
        "deltas": deepcopy(behaviour_total),
        "clause_changes": [
            {
                "clause": name,
                "before": option_value(base_plan.get(name, {})),
                "after": option_value(new_plan.get(name, {})),
            }
            for name in (action.get("offer_patch") or {})
        ],
    }
    state.behavior_log.append(entry)
    return events, entry


def replay_indices(events: List[dict], indices: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
    """纯函数：只消费 index_change 事件，不修改入参。"""
    result = deepcopy(indices)
    for event in events:
        if event.get("type") != "index_change":
            continue
        party = event["party"]
        index = event["index"]
        requested = int(event.get("requested_delta", event.get("delta", 0)))
        bucket = result.setdefault(party, {})
        before = int(bucket.get(index, 0))
        bucket[index] = max(0, min(100, before + requested))
    return result


def clamp_delta(before: int, requested_delta: int) -> int:
    return max(0, min(100, int(before) + int(requested_delta))) - int(before)
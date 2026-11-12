"""三指数结算模块。

核心分工：
- Interest：由条款效用差计算，双方各自算，只有条款数值真的变化才可能变化。
- Image / Trust：只由说话方自己的行为标签决定，单向，不做反向。
- 所有数值由引擎计算；模型只提供 action_type + magnitude 标签。
"""

from __future__ import annotations

import math
from copy import deepcopy


from .state import NegotiationState
from .validator import clause_lookup, normalize_action_type, validate_effect

INDEX_NAME_MAP = {"image": "image_actions", "trust": "trust_actions"}


class EffectRejected(ValueError):
    """整批效果被拒绝时抛出，携带可直接展示给 UI 的错误码。"""

    def __init__(self, code: str, message: str, index: int | None = None):
        self.code = code
        self.message = message
        self.index = index
        super().__init__(f"{code}: {message}")


def round_half_away(value: float) -> int:
    """四舍五入（0.5 远离 0），避免 Python 银行家舍入带来的歧义。"""
    if value >= 0:
        return int(math.floor(value + 0.5))
    return int(math.ceil(value - 0.5))


def closeness(value: float, clause: dict) -> float:
    """单条款贴近度，0~1。clause 必须带有 lo / hi / ideal。"""
    lo = float(clause["lo"])
    hi = float(clause["hi"])
    ideal = float(clause["ideal"])
    span = hi - lo
    if span <= 0:
        return 1.0 if float(value) == ideal else 0.0
    score = 1.0 - abs(float(value) - ideal) / span
    return max(0.0, min(1.0, score))


def _clause_for_party(clause: dict, party: str) -> dict:
    position = (clause.get("positions", {}) or {}).get(party, {})
    resolved = dict(clause)
    resolved["ideal"] = position.get("ideal", clause.get("default", clause["lo"]))
    resolved["weight"] = position.get("weight", 0.0)
    resolved["redline"] = position.get("redline")
    return resolved


def utility(offer_clauses: dict, party: str, scenario: dict) -> float:
    """方案对某一方的总效用：Σ weight_c * closeness_c。"""
    total = 0.0
    for clause in scenario.get("clauses", []):
        resolved = _clause_for_party(clause, party)
        value = offer_clauses.get(clause["id"], clause.get("default", clause["lo"]))
        total += float(resolved["weight"]) * closeness(value, resolved)
    return total


def compute_interest_delta(
    old_offer: dict, new_offer: dict, party: str, scenario: dict
) -> int:
    """Interest 只由条款效用差产生，不看发言类型。"""
    scale = float(
        (scenario.get("index_rules", {}) or {}).get("interest_scale", 20)
    )
    diff = utility(new_offer, party, scenario) - utility(old_offer, party, scenario)
    return round_half_away(diff * scale)


def resolve_behavior_delta(
    actor: str, action_type: str, magnitude: str, scenario: dict
) -> dict[str, int]:
    """把发言标签翻译成 Image / Trust 增量，只落在 actor 身上。

    Image / Trust 不做反向：对方不因 actor 的失态而加分。
    """
    rules = scenario.get("index_rules", {}) or {}
    normalized = normalize_action_type(action_type)
    sensitivity = (rules.get("sensitivity", {}) or {}).get(actor, {})
    deltas: dict[str, int] = {}

    for index, table_key in INDEX_NAME_MAP.items():
        table = rules.get(table_key, {}) or {}
        if normalized not in table:
            continue
        base = table[normalized].get(magnitude)
        if base is None:
            continue
        factor = float(sensitivity.get(index, 1.0))
        deltas[index] = round_half_away(float(base) * factor)

    return deltas


def _clause_values(effect: dict, lookup: dict[str, dict]) -> list[tuple[dict, object]]:
    targets: list[tuple[dict, object]] = []
    clause_ref = effect.get("clause")
    if clause_ref is not None and "value" in effect:
        clause = lookup.get(clause_ref)
        if clause is not None:
            targets.append((clause, effect["value"]))
    for key in ("clause_values", "proposal"):
        mapping = effect.get(key)
        if isinstance(mapping, dict):
            for ref, value in mapping.items():
                clause = lookup.get(ref)
                if clause is not None:
                    targets.append((clause, value))
    return targets


def _is_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def apply_effects(state, scenario: dict, effects: list[dict]) -> list[dict]:
    """对外唯一入口：整批校验通过后才结算，任何一条非法则整批拒绝。"""
    if not isinstance(effects, list):
        raise EffectRejected("UNKNOWN_EFFECT_LABEL", "effects 必须是数组")

    for position, effect in enumerate(effects):
        ok, code, message = validate_effect(effect, scenario)
        if not ok:
            raise EffectRejected(code, message, position)

    lookup = clause_lookup(scenario)
    old_offer = deepcopy(state.offers)
    new_offer = deepcopy(state.offers)

    behavior_entries: list[dict] = []
    clause_changes: list[dict] = []

    for effect in effects:
        actor = effect.get("actor")
        action_type = effect.get("action_type")
        magnitude = effect.get("magnitude")
        normalized = normalize_action_type(action_type)

        entry_changes: list[dict] = []
        for clause, raw_value in _clause_values(effect, lookup):
            if not _is_number(raw_value):
                raise EffectRejected(
                    "UNKNOWN_EFFECT_LABEL", "条款数值必须是有限数字"
                )
            before = new_offer.get(
                clause["id"], clause.get("default", clause["lo"])
            )
            applied = min(float(clause["hi"]), max(float(clause["lo"]), float(raw_value)))
            if isinstance(raw_value, int):
                applied = int(applied)
            new_offer[clause["id"]] = applied
            change = {
                "clause_id": clause["id"],
                "clause": clause["name"],
                "before": before,
                "after": applied,
                "raw_value": raw_value,
            }
            entry_changes.append(change)
            clause_changes.append(change)

        behavior_entries.append(
            {
                "round": int(state.round),
                "actor": actor,
                "action_type": action_type,
                "normalized_action_type": normalized,
                "magnitude": magnitude,
                "clause": effect.get("clause"),
                "reason": effect.get("reason", ""),
                "clause_changes": entry_changes,
                "deltas": {},
            }
        )

    events: list[dict] = []

    interest_deltas: dict[str, dict[str, int]] = {}
    for party in scenario.get("parties", {}):
        delta = compute_interest_delta(old_offer, new_offer, party, scenario)
        if delta != 0:
            interest_deltas.setdefault(party, {})["interest"] = delta

    if interest_deltas:
        if clause_changes:
            reason = "条款变更：" + "；".join(
                f"{c['clause']} {c['before']}→{c['after']}" for c in clause_changes
            )
        else:
            reason = "条款未变，interest 变化为 0"
        events.extend(state.apply_indices(interest_deltas, reason, state.round))

    for entry in behavior_entries:
        actor = entry["actor"]
        if not actor:
            continue
        deltas = resolve_behavior_delta(
            actor, entry["action_type"], entry["magnitude"], scenario
        )
        deltas = {k: v for k, v in deltas.items() if v != 0}
        entry["deltas"] = deltas
        if deltas:
            reason = entry["reason"] or (
                f"{entry['normalized_action_type']}/{entry['magnitude']}"
            )
            events.extend(
                state.apply_indices(
                    {actor: deltas},
                    reason,
                    state.round,
                    meta={
                        "actor": actor,
                        "action_type": entry["normalized_action_type"],
                        "magnitude": entry["magnitude"],
                    },
                )
            )

    state.offers = new_offer
    state.behavior_log.extend(behavior_entries)
    return events


def replay_indices(events: list[dict], scenario: dict) -> NegotiationState:
    """重放事件流重建指数，不调用模型，不使用随机/时间。

    只消费 type=index_change 的事件；返回一个新的 NegotiationState。
    """
    state = NegotiationState(session_id="replay", scenario=scenario)
    for event in events:
        if event.get("type") != "index_change":
            continue
        meta = {
            key: event[key]
            for key in ("actor", "action_type", "magnitude")
            if key in event
        }
        state.apply_indices(
            {event["party"]: {event["index"]: event["delta"]}},
            event.get("reason", ""),
            event.get("round", 1),
            meta=meta or None,
        )
    return state
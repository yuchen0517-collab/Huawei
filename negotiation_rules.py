"""谈判行动契约 v2：卡牌、响应闭包与推进不变量的纯函数校验。

设计立场
--------
本模块不修改、也不依赖 C 侧引擎的实现细节，只读取引擎已经写进
`NegotiationState` 的公开事实（`offers` / `public_events` / `round` /
`action_points`）。因此它可以脱离引擎单独运行、单独测试，也可以作为
`engine.validator.validate_action` 的前置一层直接插入：

    from negotiation_rules import check_card_action
    ok, code, detail = check_card_action(action, state, scenario)
    if not ok:
        return fail(code, detail)

三条判定法则
------------
1. 报价板法则：一张牌的产出若要写进 agreement（条款表 ∪ 条件），就必须
   走报价板并产生新版本；反之不得修改条款。
2. 响应闭包：出现新版本后，对方必须在 1 次过渡行动内表态
   （接受／拒绝／反报价／最后报价）。
3. 推进不变量：任何行动都必须改变某样可观测的东西——条款、信息、程序
   或承诺；"只说话、什么都不变"的空转回合一律拒绝。

所有判定只读状态、不写状态，返回 `(ok, code, detail)`，与引擎
`validate_action` 的返回形状一致。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_REGISTRY = Path(__file__).resolve().with_name("card_registry.json")

OFFER_ACTIONS = ("offer", "counter_offer", "conditional_exchange", "final_offer")
# 会解除 pending 的行动：表态或产生新版本，或直接终局。
RESOLVING_ACTIONS = (
    "accept",
    "reject",
    "walk_away",
    "offer",
    "counter_offer",
    "conditional_exchange",
    "final_offer",
)

TRANSITION_FAMILIES = ("info", "procedure", "stance")
TRANSITION_TYPES = ("probe", "statement")

ERRORS: Dict[str, str] = {
    "CARD_UNKNOWN": "未登记的卡牌。",
    "CARD_ACTION_MISMATCH": "该卡牌不能用于此行动类型。",
    "CARD_REQUIRES_QUOTE_BOARD": "该卡牌必须走报价板并给出条款变更。",
    "CARD_FORBIDS_QUOTE_BOARD": "非报价类卡牌不得修改条款。",
    "CARD_COOLING": "该卡牌仍在冷却中。",
    "CARD_EXHAUSTED": "该卡牌本局使用次数已用尽。",
    "CARD_PAYLOAD_MISSING": "该卡牌缺少必要的载荷字段。",
    "CARD_PAYLOAD_FORBIDDEN": "该卡牌不允许携带载荷。",
    "CARD_PAYLOAD_INVALID": "卡牌载荷不合法。",
    "PENDING_RESPONSE_EXCEEDED": "必须对当前报价版本表态：接受、拒绝或反报价。",
    "SELF_REVISION_LOCKED": "对方尚未表态，不得自行改版。",
    "REPEAT_HOLD_FORBIDDEN": "无新信息时不得连续维持原报价。",
    "EMPTY_TURN": "该行动不会改变任何状态，属于空转回合。",
}


# ----------------------------------------------------------------------
# 载入与访问器（同时兼容 dataclass 状态与 dict 状态）
# ----------------------------------------------------------------------
def load_registry(path: Optional[str | Path] = None) -> dict:
    with open(path or DEFAULT_REGISTRY, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _fail(code: str, detail: str = "") -> Tuple[bool, str, str]:
    message = ERRORS.get(code, code)
    if detail:
        message = f"{message}{detail}"
    return False, code, message


def _ok() -> Tuple[bool, str, str]:
    return True, "", ""


def _parties(scenario: dict) -> List[str]:
    parties = scenario.get("parties", [])
    if isinstance(parties, dict):
        return list(parties.keys())
    return [party["id"] for party in parties]


def _other(actor: str, scenario: dict) -> Optional[str]:
    for party in _parties(scenario):
        if party != actor:
            return party
    return None


def _action_events(state: Any) -> List[dict]:
    return [
        event
        for event in _get(state, "public_events", []) or []
        if isinstance(event, dict) and event.get("type") == "action"
    ]


def _card_index(registry: dict) -> Dict[str, dict]:
    return {card["id"]: card for card in registry.get("cards", [])}


# ----------------------------------------------------------------------
# 派生事实：pending、过渡次数、卡牌使用历史
# ----------------------------------------------------------------------
def pending_response(state: Any, scenario: dict) -> Optional[dict]:
    """当前挂起的表态窗口；没有报价时为 None。"""
    offers = _get(state, "offers", []) or []
    if not offers:
        return None
    last = offers[-1]
    actor = _get(last, "actor")
    responder = _other(actor, scenario)
    if responder is None:
        return None
    return {
        "responder": responder,
        "offeror": actor,
        "version": _get(last, "version"),
        "action_id": _get(last, "action_id"),
    }


def _events_after(state: Any, action_id: Any) -> List[dict]:
    events = _action_events(state)
    for index, event in enumerate(events):
        if event.get("action_id") == action_id:
            return events[index + 1 :]
    return events


def is_transition(action_type: str, card: Optional[dict]) -> bool:
    """是否属于"不表态的过渡行动"。"""
    if card is not None:
        return card.get("family") in TRANSITION_FAMILIES
    return action_type in TRANSITION_TYPES


def deferral_count(
    state: Any,
    scenario: dict,
    actor: str,
    registry: dict,
    pending: Optional[dict] = None,
) -> int:
    """本版本窗口内，该方已经用掉的过渡次数。"""
    pending = pending or pending_response(state, scenario)
    if pending is None:
        return 0
    cards = _card_index(registry)
    used = 0
    for event in _events_after(state, pending["action_id"]):
        if event.get("actor") != actor:
            continue
        card = cards.get(event.get("card_id") or "")
        if is_transition(event.get("action_type"), card):
            used += 1
    return used


def _last_use_round(state: Any, actor: str, card_id: str) -> Optional[int]:
    last = None
    for event in _action_events(state):
        if event.get("actor") == actor and event.get("card_id") == card_id:
            last = int(event.get("round", 0))
    return last


def _use_count(state: Any, actor: str, card_id: str) -> int:
    return sum(
        1
        for event in _action_events(state)
        if event.get("actor") == actor and event.get("card_id") == card_id
    )


# ----------------------------------------------------------------------
# 载荷校验
# ----------------------------------------------------------------------
def _check_payload(
    card: dict, action: dict, scenario: dict
) -> Tuple[bool, str, str]:
    spec = card.get("payload") or {}
    kind = spec.get("kind")
    payload = action.get("card_payload") or {}

    if kind == "offer_patch":
        patch = action.get("offer_patch") or {}
        if not patch:
            return _fail("CARD_REQUIRES_QUOTE_BOARD", f"卡牌 {card['id']} 要求条款变更。")
        role = spec.get("clause_role")
        roles = (scenario.get("clause_roles") or {}) if isinstance(scenario, dict) else {}
        role_clause = roles.get(role) if role else None
        if role_clause and role_clause not in patch:
            return _fail(
                "CARD_PAYLOAD_INVALID",
                f"卡牌 {card['id']} 必须写入「{role_clause}」条款。",
            )
        if action.get("card_payload"):
            return _fail("CARD_PAYLOAD_FORBIDDEN", f"卡牌 {card['id']} 不使用 card_payload。")
        return _ok()

    if not payload:
        if spec.get("required"):
            return _fail("CARD_PAYLOAD_MISSING", f"卡牌 {card['id']} 缺少载荷。")
        return _ok()

    required = spec.get("required") or []
    optional = spec.get("optional") or []
    missing = [name for name in required if not payload.get(name)]
    if missing:
        return _fail(
            "CARD_PAYLOAD_MISSING", f"卡牌 {card['id']} 缺少 {', '.join(missing)}。"
        )
    extra = [name for name in payload if name not in required and name not in optional]
    if extra:
        return _fail(
            "CARD_PAYLOAD_INVALID", f"卡牌 {card['id']} 不接受字段 {', '.join(extra)}。"
        )
    target = payload.get("target")
    if target is not None and target not in _parties(scenario):
        return _fail("CARD_PAYLOAD_INVALID", f"target={target!r} 不是场景参与方。")
    return _ok()


# ----------------------------------------------------------------------
# 主校验
# ----------------------------------------------------------------------
def check_card_action(
    action: dict,
    state: Any,
    scenario: dict,
    registry: Optional[dict] = None,
) -> Tuple[bool, str, str]:
    """契约 v2 校验。返回 (ok, code, detail)，与引擎 validate_action 同形。"""
    registry = registry or load_registry()
    strict = registry.get("strict") or {}
    cards = _card_index(registry)

    action_type = action.get("action_type")
    actor = action.get("actor")
    card_id = action.get("card_id")
    patch = action.get("offer_patch") or {}

    card = None
    if card_id:
        card = cards.get(card_id)
        if card is None:
            return _fail("CARD_UNKNOWN", f"card_id={card_id!r}。")
        if action_type not in (card.get("action_types") or []):
            return _fail(
                "CARD_ACTION_MISMATCH",
                f"卡牌 {card_id} 只允许 {card.get('action_types')}，收到 {action_type!r}。",
            )

        if not card.get("quote_board") and patch:
            return _fail(
                "CARD_FORBIDS_QUOTE_BOARD",
                f"卡牌 {card_id} 属于「{card.get('family')}」，不得修改条款。",
            )

        ok, code, detail = _check_payload(card, action, scenario)
        if not ok:
            return ok, code, detail

        cooldown = int(card.get("cooldown") or 0)
        if cooldown > 0:
            last_round = _last_use_round(state, actor, card_id)
            if last_round is not None:
                available = last_round + cooldown + 1
                if int(_get(state, "round", 1)) < available:
                    return _fail(
                        "CARD_COOLING",
                        f"卡牌 {card_id} 冷却至第 {available} 回合（当前第 {_get(state, 'round', 1)} 回合）。",
                    )

        limit = card.get("uses_per_game")
        if limit is not None and _use_count(state, actor, card_id) >= int(limit):
            return _fail("CARD_EXHAUSTED", f"卡牌 {card_id} 本局限用 {limit} 次。")
    else:
        # ---- 基础行动 ----
        if action_type in OFFER_ACTIONS and not patch:
            return _fail(
                "EMPTY_TURN",
                f"{action_type} 必须给出至少一条条款变更，否则会空转地推进版本号。",
            )
        if strict.get("require_card_for_statement", True) and action_type in TRANSITION_TYPES:
            return _fail("EMPTY_TURN", f"{action_type} 必须挂靠一张策略卡。")

    # ---- 响应闭包 ----
    pending = pending_response(state, scenario)
    limit = int(strict.get("max_deferrals", 1))
    if pending is not None:
        if actor == pending["responder"]:
            if is_transition(action_type, card):
                used = deferral_count(state, scenario, actor, registry, pending)
                if used >= limit:
                    return _fail(
                        "PENDING_RESPONSE_EXCEEDED",
                        f"V{pending['version']} 已给过 {limit} 次过渡，必须表态。",
                    )
        elif actor == pending["offeror"] and action_type in OFFER_ACTIONS:
            if not strict.get("allow_self_revision", False):
                return _fail(
                    "SELF_REVISION_LOCKED",
                    f"V{pending['version']} 对方尚未表态。",
                )

    # ---- 重复维持原报价 ----
    if action_type == "reject" and not patch:
        last = None
        for event in _action_events(state):
            if event.get("actor") == actor:
                last = event
        if (
            last is not None
            and last.get("action_type") == "reject"
            and last.get("version") == _get(state, "current_version")
        ):
            return _fail("REPEAT_HOLD_FORBIDDEN", "")

    return _ok()


# ----------------------------------------------------------------------
# 给前端用：可解释的挂起状态 + 可用卡牌
# ----------------------------------------------------------------------
def pending_hint(
    state: Any, scenario: dict, registry: Optional[dict] = None
) -> Optional[dict]:
    registry = registry or load_registry()
    strict = registry.get("strict") or {}
    pending = pending_response(state, scenario)
    if pending is None:
        return None
    used = deferral_count(state, scenario, pending["responder"], registry, pending)
    limit = int(strict.get("max_deferrals", 1))
    return {
        "responder": pending["responder"],
        "version": pending["version"],
        "deferrals_used": used,
        "deferrals_left": max(0, limit - used),
        "must_resolve": used >= limit,
        "text": (
            f"等 {pending['responder']} 对 V{pending['version']} 表态，"
            f"还剩 {max(0, limit - used)} 次过渡机会。"
        ),
    }


def available_cards(
    actor: str, state: Any, registry: Optional[dict] = None
) -> List[Dict[str, Any]]:
    """列出该方当前可用卡牌及不可用原因，供前端置灰。"""
    registry = registry or load_registry()
    result: List[Dict[str, Any]] = []
    for card in registry.get("cards", []):
        reason = ""
        cooldown = int(card.get("cooldown") or 0)
        last_round = _last_use_round(state, actor, card["id"])
        if cooldown > 0 and last_round is not None:
            available = last_round + cooldown + 1
            if int(_get(state, "round", 1)) < available:
                reason = f"冷却至第 {available} 回合"
        limit = card.get("uses_per_game")
        if not reason and limit is not None and _use_count(state, actor, card["id"]) >= int(limit):
            reason = f"本局限用 {limit} 次，已用尽"
        result.append(
            {
                "id": card["id"],
                "name": card["name"],
                "family": card["family"],
                "quote_board": bool(card.get("quote_board")),
                "available": not reason,
                "reason": reason,
            }
        )
    return result

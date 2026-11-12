"""行动结构校验、effect 标签校验与红线判定。

校验顺序固定：
schema → action_type（schema 内）→ phase → 幂等 → 版本
→ final_offer 三条规则 → 行动点 → 条款/取值/范围 → 红线。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional, Tuple

ACTION_TYPES = (
    "offer",
    "counter_offer",
    "conditional_exchange",
    "accept",
    "reject",
    "final_offer",
    "walk_away",
    "probe",
    "statement",
)
OFFER_ACTIONS = frozenset(
    {"offer", "counter_offer", "conditional_exchange", "final_offer"}
)
NON_OFFER_ACTIONS = frozenset(
    {"accept", "reject", "walk_away", "probe", "statement"}
)
MAGNITUDES = ("slight", "moderate", "major")
LABELS = (
    "constructive_proposal",
    "cite_rules",
    "hardline_stance",
    "broken_promise",
    "personal_attack",
    "redline_provoke",
    "procedural",
    "diplomatic_reframe",
    "protect_ally",
    "keep_promise",
    "betray_ally",
    "vague_stance",
    "conditional_concession",
)

REQUIRED_FIELDS = (
    "action_id",
    "actor",
    "action_type",
    "card_id",
    "offer_patch",
    "conditions",
    "expected_effect",
    "public_message",
)
ALLOWED_FIELDS = frozenset(REQUIRED_FIELDS) | {"effect_labels"}
PATCH_ENTRY_FIELDS = frozenset({"option", "note"})
EFFECT_FIELDS = frozenset({"label", "magnitude", "clause", "reason"})

ERRORS = {
    "SCHEMA_VIOLATION": "行动结构不符合 schema。",
    "UNKNOWN_ACTION_TYPE": "action_type 不在允许的 9 个枚举值内。",
    "PATCH_NOT_ALLOWED": "非报价类行动不得携带非空 offer_patch。",
    "PHASE_CLOSED": "谈判已结束，不能再提交行动。",
    "DUPLICATE_ACTION": "action_id 已生效过。",
    "VERSION_CONFLICT": "行动与当前版本不一致。",
    "AGREEMENT_HAS_OPEN_ISSUES": "还有未决条款，不能接受协议。",
    "NO_COUNTERPART_OFFER": "对方还没有报价，不能接受。",
    "ACTION_POINTS_INSUFFICIENT": "本轮行动点已用完。",
    "UNKNOWN_CLAUSE": "引用了不存在的条款。",
    "UNKNOWN_OPTION": "枚举型条款给了不在 options 里的取值。",
    "TERM_LOCKED": "条款已锁定，不能再改。",
    "VALUE_OUT_OF_RANGE": "数值型条款超出 range。",
    "REDLINE_VIOLATION": "方案触碰红线。",
    "FINAL_OFFER_ALREADY_DECLARED": "已声明过最后报价，不得再次声明。",
    "FINAL_OFFER_LOCKED": "已声明最后报价，不能再修改条款。",
    "FINAL_OFFER_EMPTY": "最后报价没有带任何条款。",
}


def party_ids(scenario: dict) -> List[str]:
    parties = scenario.get("parties", [])
    if isinstance(parties, dict):
        return list(parties.keys())
    return [party["id"] for party in parties]


def clause_map(scenario: dict) -> Dict[str, dict]:
    return {clause["name"]: clause for clause in scenario.get("clauses", [])}


def clause_names(scenario: dict) -> List[str]:
    return [clause["name"] for clause in scenario.get("clauses", [])]


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def option_value(entry) -> object:
    if isinstance(entry, dict):
        return entry.get("option")
    return entry


def fail(code: str, detail: str = "") -> Tuple[bool, str, str]:
    message = ERRORS.get(code, code)
    if detail:
        message = f"{message}{detail}"
    return False, code, message


def validate_schema(action) -> Tuple[bool, str, str]:
    """逐条实现成员A 的 JSON Schema（含 additionalProperties:false）。"""
    if not isinstance(action, dict):
        return fail("SCHEMA_VIOLATION", "行动必须是 JSON 对象。")

    missing = [name for name in REQUIRED_FIELDS if name not in action]
    if missing:
        return fail("SCHEMA_VIOLATION", f"缺少字段：{', '.join(missing)}。")

    extra = [name for name in action if name not in ALLOWED_FIELDS]
    if extra:
        return fail("SCHEMA_VIOLATION", f"出现未允许字段：{', '.join(extra)}。")

    for name in ("action_id", "actor", "expected_effect", "public_message"):
        if not isinstance(action[name], str):
            return fail("SCHEMA_VIOLATION", f"{name} 必须是字符串。")
    if not action["action_id"]:
        return fail("SCHEMA_VIOLATION", "action_id 不能为空。")
    if not action["actor"]:
        return fail("SCHEMA_VIOLATION", "actor 不能为空。")

    action_type = action["action_type"]
    if not isinstance(action_type, str) or action_type not in ACTION_TYPES:
        return fail("UNKNOWN_ACTION_TYPE", f"收到 action_type={action_type!r}。")

    card_id = action["card_id"]
    if card_id is not None and not isinstance(card_id, str):
        return fail("SCHEMA_VIOLATION", "card_id 必须是字符串或 null。")

    conditions = action["conditions"]
    if not isinstance(conditions, list) or not all(
        isinstance(item, str) for item in conditions
    ):
        return fail("SCHEMA_VIOLATION", "conditions 必须是字符串数组。")

    patch = action["offer_patch"]
    if not isinstance(patch, dict):
        return fail("SCHEMA_VIOLATION", "offer_patch 必须是对象。")

    for clause_name, entry in patch.items():
        if not isinstance(clause_name, str) or not clause_name:
            return fail("SCHEMA_VIOLATION", "offer_patch 的键必须是非空字符串。")
        if not isinstance(entry, dict):
            return fail("SCHEMA_VIOLATION", f"offer_patch[{clause_name}] 必须是对象。")
        missing_entry = [
            name for name in ("option", "note") if name not in entry
        ]
        if missing_entry:
            return fail(
                "SCHEMA_VIOLATION",
                f"offer_patch[{clause_name}] 缺少 {', '.join(missing_entry)}。",
            )
        extra_entry = [name for name in entry if name not in PATCH_ENTRY_FIELDS]
        if extra_entry:
            return fail(
                "SCHEMA_VIOLATION",
                f"offer_patch[{clause_name}] 出现未允许字段：{', '.join(extra_entry)}。",
            )
        option = entry["option"]
        if not isinstance(option, str) and not is_number(option):
            return fail(
                "SCHEMA_VIOLATION",
                f"offer_patch[{clause_name}].option 必须是字符串或数字。",
            )
        if not isinstance(entry["note"], str):
            return fail(
                "SCHEMA_VIOLATION", f"offer_patch[{clause_name}].note 必须是字符串。"
            )

    if action_type in NON_OFFER_ACTIONS and patch:
        return fail(
            "PATCH_NOT_ALLOWED",
            f"{action_type} 是非报价类行动，offer_patch 必须为空对象。",
        )

    labels = action.get("effect_labels")
    if labels is not None:
        if not isinstance(labels, list):
            return fail("SCHEMA_VIOLATION", "effect_labels 必须是数组。")
        for position, item in enumerate(labels):
            if not isinstance(item, dict):
                return fail(
                    "SCHEMA_VIOLATION", f"effect_labels[{position}] 必须是对象。"
                )
            missing_label = [
                name for name in ("label", "magnitude") if name not in item
            ]
            if missing_label:
                return fail(
                    "SCHEMA_VIOLATION",
                    f"effect_labels[{position}] 缺少 {', '.join(missing_label)}。",
                )
            extra_label = [name for name in item if name not in EFFECT_FIELDS]
            if extra_label:
                return fail(
                    "SCHEMA_VIOLATION",
                    f"effect_labels[{position}] 出现未允许字段：{', '.join(extra_label)}。",
                )
            if item["label"] not in LABELS:
                return fail(
                    "SCHEMA_VIOLATION",
                    f"effect_labels[{position}].label={item['label']!r} 不在枚举内。",
                )
            if item["magnitude"] not in MAGNITUDES:
                return fail(
                    "SCHEMA_VIOLATION",
                    f"effect_labels[{position}].magnitude={item['magnitude']!r} 不在枚举内。",
                )
            clause_ref = item.get("clause")
            if clause_ref is not None and not isinstance(clause_ref, str):
                return fail(
                    "SCHEMA_VIOLATION",
                    f"effect_labels[{position}].clause 必须是字符串或 null。",
                )
            reason = item.get("reason", "")
            if not isinstance(reason, str):
                return fail(
                    "SCHEMA_VIOLATION",
                    f"effect_labels[{position}].reason 必须是字符串。",
                )

    return True, None, ""


def latest_offer(state, actor: str):
    for offer in reversed(state.offers):
        if offer.actor == actor:
            return offer
    return None


def effective_plan(state, scenario: dict) -> Dict[str, dict]:
    """按已提交报价重建当前全局方案；未表态条款落回场景初始值。"""
    plan = {
        clause["name"]: {
            "option": clause.get("initial"),
            "note": "场景初始方案",
        }
        for clause in scenario.get("clauses", [])
    }
    for offer in state.offers:
        for name, entry in offer.clauses.items():
            if name in plan:
                plan[name] = deepcopy(entry)
    return plan


def apply_patch(plan: Dict[str, dict], patch: Dict[str, dict]) -> Dict[str, dict]:
    merged = deepcopy(plan)
    for name, entry in patch.items():
        merged[name] = {"option": entry["option"], "note": entry.get("note", "")}
    return merged


def is_redline_violation(clause: dict, option, party: str) -> bool:
    if clause.get("type") == "numeric":
        position = (clause.get("positions") or {}).get(party, {})
        if "ideal" not in position or "redline" not in position:
            return False
        ideal = position["ideal"]
        redline = position["redline"]
        if ideal > redline:
            return option < redline
        if ideal < redline:
            return option > redline
        return False
    return option in ((clause.get("redlines") or {}).get(party) or [])


def redline_violations(plan: Dict[str, dict], scenario: dict) -> List[Tuple[str, str]]:
    violations: List[Tuple[str, str]] = []
    clauses = clause_map(scenario)
    for name, entry in plan.items():
        clause = clauses.get(name)
        if clause is None:
            continue
        option = option_value(entry)
        for party in party_ids(scenario):
            if is_redline_violation(clause, option, party):
                violations.append((name, party))
    return violations


def _other_party(state, actor: str) -> Optional[str]:
    others = [party for party in state.indices if party != actor]
    return others[0] if others else None


def validate_action(action, state, scenario: dict) -> Tuple[bool, str, str]:
    """完整行动校验。任何失败都发生在状态写入之前。"""
    ok, code, message = validate_schema(action)
    if not ok:
        return ok, code, message

    action_type = action["action_type"]
    actor = action["actor"]
    parties = party_ids(scenario)
    if actor not in parties:
        return fail("SCHEMA_VIOLATION", f"actor={actor!r} 不是场景参与方。")

    if state.status != "active" or state.phase == "ended":
        return fail("PHASE_CLOSED", "")

    if action["action_id"] in state.seen_action_ids:
        return fail("DUPLICATE_ACTION", f"action_id={action['action_id']!r} 已生效。")

    expected_version = state.offers[-1].version if state.offers else 0
    if state.current_version != expected_version:
        return fail(
            "VERSION_CONFLICT",
            f"状态内部版本不一致：current_version={state.current_version}，最新报价={expected_version}。",
        )

    declared = state.final_offer_declared_by.get(actor)
    patch = action["offer_patch"]
    if action_type == "final_offer":
        if declared is not None:
            return fail(
                "FINAL_OFFER_ALREADY_DECLARED",
                f"你已在 V{declared} 声明过最后报价，不得再次声明。",
            )
        if not patch:
            return fail("FINAL_OFFER_EMPTY", "")
    elif declared is not None and action_type in {
        "offer",
        "counter_offer",
        "conditional_exchange",
    }:
        return fail(
            "FINAL_OFFER_LOCKED",
            f"你已在 V{declared} 声明过最后报价，不能再修改条款。",
        )

    if action_type == "accept":
        counterpart = _other_party(state, actor)
        if counterpart is None or latest_offer(state, counterpart) is None:
            return fail("NO_COUNTERPART_OFFER", "")
        rules = scenario.get("terminal_rules", {}) or {}
        if rules.get("accept_requires_no_open_issues", True) and state.open_issues:
            return fail(
                "AGREEMENT_HAS_OPEN_ISSUES",
                f"未决条款：{', '.join(state.open_issues)}。",
            )

    if state.action_points <= 0:
        return fail("ACTION_POINTS_INSUFFICIENT", "")

    clauses = clause_map(scenario)
    for name, entry in patch.items():
        clause = clauses.get(name)
        if clause is None:
            return fail("UNKNOWN_CLAUSE", f"条款 {name!r} 不存在。")
        if clause.get("locked") is True:
            return fail("TERM_LOCKED", f"条款 {name!r} 已锁定。")

        option = entry["option"]
        if clause.get("type") == "numeric":
            if not is_number(option):
                return fail(
                    "VALUE_OUT_OF_RANGE", f"条款 {name!r} 需要数值。"
                )
            low, high = clause.get("range", [0, 0])
            if option < low or option > high:
                return fail(
                    "VALUE_OUT_OF_RANGE",
                    f"条款 {name!r} 取值 {option} 不在 [{low}, {high}]。",
                )
        else:
            options = [item["id"] for item in clause.get("options", [])]
            if not isinstance(option, str) or option not in options:
                return fail(
                    "UNKNOWN_OPTION", f"条款 {name!r} 没有选项 {option!r}。"
                )

    for position, item in enumerate(action.get("effect_labels") or []):
        clause_ref = item.get("clause")
        if clause_ref is not None and clause_ref not in clauses:
            return fail(
                "UNKNOWN_CLAUSE",
                f"effect_labels[{position}].clause={clause_ref!r} 不存在。",
            )

    if action_type in OFFER_ACTIONS and patch:
        plan = apply_patch(effective_plan(state, scenario), patch)
        touched = {name: plan[name] for name in patch if name in plan}
        violations = redline_violations(touched, scenario)
    elif action_type == "accept":
        violations = redline_violations(effective_plan(state, scenario), scenario)
    else:
        violations = []

    if violations:
        detail = "；".join(f"{name} 触碰 {party} 红线" for name, party in violations)
        return fail("REDLINE_VIOLATION", detail + "。")

    return True, None, ""
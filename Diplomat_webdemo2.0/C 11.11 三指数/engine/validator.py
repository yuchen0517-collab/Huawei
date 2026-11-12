"""动作与效果标签校验。

设计口径：模型只允许输出离散标签（action_type + magnitude），
任何直接给出数值增量的字段都会在 validate_effect 阶段被拒绝。
"""

from __future__ import annotations

ERRORS = {
    "INVALID_ACTION_SHAPE": "动作必须是一个 JSON 对象，请检查提交格式。",
    "UNKNOWN_PARTY": "未知的谈判主体，请使用场景中已定义的参与方。",
    "MISSING_ACTION_TYPE": "动作缺少 action_type，无法判断发言类型。",
    "UNKNOWN_ACTION": "未知的动作类型，请使用规则允许的 action_type。",
    "INVALID_ROUND": "回合数必须是整数。",
    "UNKNOWN_EFFECT_LABEL": "无法识别的发言效果标签：只允许使用规定的 action_type 与 slight/moderate/major，且不得直接给出数值增量。",
    "MISSING_MAGNITUDE": "发言效果缺少 magnitude，请从 slight、moderate、major 三档中选择一档。",
    "UNKNOWN_CLAUSE": "发言效果引用了不存在的条款，请使用场景中已定义的条款 id 或名称。",
    "EFFECT_BATCH_REJECTED": "本批发言效果未通过校验，整批未生效，局面保持不变。",
}

ACTION_TYPES = frozenset(
    {
        # 场景 index_rules 中出现的动作标签
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
        # 与规则原文八类发言对齐的别名
        "concession",
    }
)

MAGNITUDES = frozenset({"slight", "moderate", "major"})

ALIASES = {
    "concession": "conditional_concession",
}

EFFECT_LABELS = {
    "action_types": ACTION_TYPES,
    "magnitudes": MAGNITUDES,
}

# 这些字段代表“模型直接给数”，一律拒绝。
FORBIDDEN_DELTA_KEYS = frozenset(
    {
        "interest_delta",
        "image_delta",
        "trust_delta",
        "delta",
        "interest",
        "image",
        "trust",
    }
)

VALUE_KEYS = ("value", "clause_values", "proposal")


def normalize_action_type(action_type: str) -> str:
    return ALIASES.get(action_type, action_type)


def clause_lookup(scenario: dict) -> dict[str, dict]:
    """同时支持用条款 id 或中文名引用条款。"""
    lookup: dict[str, dict] = {}
    for clause in scenario.get("clauses", []):
        lookup[clause["id"]] = clause
        lookup[clause["name"]] = clause
    return lookup


def resolve_clause_ref(scenario: dict, ref) -> dict | None:
    if not isinstance(ref, str):
        return None
    return clause_lookup(scenario).get(ref)


def _fail(code: str, detail: str = "") -> tuple[bool, str, str]:
    message = ERRORS.get(code, code)
    if detail:
        message = f"{message}（{detail}）"
    return False, code, message


def validate_action(action, state) -> tuple[bool, str | None, str]:
    """校验一条谈判动作。字段沿用既有对局状态，不改变命名。"""
    if not isinstance(action, dict):
        return _fail("INVALID_ACTION_SHAPE")

    actor = action.get("actor")
    parties = getattr(state, "indices", {}) or {}
    if not actor or actor not in parties:
        return _fail("UNKNOWN_PARTY")

    action_type = action.get("action_type")
    if not action_type:
        return _fail("MISSING_ACTION_TYPE")
    if action_type not in ACTION_TYPES:
        return _fail("UNKNOWN_ACTION")

    round_no = action.get("round")
    if round_no is not None and not isinstance(round_no, int):
        return _fail("INVALID_ROUND")

    return True, None, ""


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _value_targets(effect: dict, lookup: dict[str, dict]) -> list[tuple[dict, object]]:
    """返回本次效果引用的 (条款, 数值) 列表，供校验与结算共用。"""
    targets: list[tuple[dict, object]] = []

    clause_ref = effect.get("clause")
    if clause_ref is not None:
        clause = lookup.get(clause_ref) if isinstance(clause_ref, str) else None
        if clause is None:
            return []
        if "value" in effect:
            targets.append((clause, effect["value"]))

    for key in ("clause_values", "proposal"):
        mapping = effect.get(key)
        if isinstance(mapping, dict):
            for ref, value in mapping.items():
                clause = lookup.get(ref) if isinstance(ref, str) else None
                if clause is not None:
                    targets.append((clause, value))

    return targets


def validate_effect(effect, scenario) -> tuple[bool, str | None, str]:
    """校验模型给出的效果标签。

    校验顺序：直接给数 → 未知 action_type → 缺 magnitude → 非法 magnitude
    → 引用不存在的条款。
    """
    if not isinstance(effect, dict):
        return _fail("UNKNOWN_EFFECT_LABEL", "效果必须是对象")

    for key in FORBIDDEN_DELTA_KEYS:
        if key in effect:
            return _fail("UNKNOWN_EFFECT_LABEL", f"禁止直接给出数值字段 {key}")

    action_type = effect.get("action_type")
    if action_type not in ACTION_TYPES:
        return _fail("UNKNOWN_EFFECT_LABEL", f"未知 action_type={action_type!r}")

    if "magnitude" not in effect or effect.get("magnitude") is None:
        return _fail("MISSING_MAGNITUDE")

    magnitude = effect.get("magnitude")
    if magnitude not in MAGNITUDES:
        return _fail("UNKNOWN_EFFECT_LABEL", f"非法 magnitude={magnitude!r}")

    lookup = clause_lookup(scenario)

    clause_ref = effect.get("clause")
    if clause_ref is not None:
        if not isinstance(clause_ref, str) or clause_ref not in lookup:
            return _fail("UNKNOWN_CLAUSE", f"clause={clause_ref!r}")

    for key in ("clause_values", "proposal"):
        mapping = effect.get(key)
        if mapping is None:
            continue
        if not isinstance(mapping, dict):
            return _fail("UNKNOWN_EFFECT_LABEL", f"{key} 必须是条款到数值的对象")
        for ref in mapping:
            if not isinstance(ref, str) or ref not in lookup:
                return _fail("UNKNOWN_CLAUSE", f"{key} 引用了 {ref!r}")

    actor = effect.get("actor")
    if actor is not None and actor not in scenario.get("parties", {}):
        return _fail("UNKNOWN_PARTY", f"actor={actor!r}")

    if "value" in effect and clause_ref is None:
        return _fail("UNKNOWN_CLAUSE", "给出 value 时必须同时指定 clause")

    for _clause, value in _value_targets(effect, lookup):
        if not _is_number(value):
            return _fail("UNKNOWN_EFFECT_LABEL", "条款数值必须是数字")

    return True, None, ""
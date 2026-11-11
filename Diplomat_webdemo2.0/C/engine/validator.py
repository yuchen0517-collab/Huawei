# -*- coding: utf-8 -*-
"""行动合法性校验器 —— 对应手册 5.1「行动合法性」+ 5.3「统一错误码」

原则：非法行动被拒绝，且**不改变任何状态**。D 只需要拿到 error_code 就能显示人话。
"""

from typing import Any, Dict, Optional, Tuple

# 统一错误码（给 A 和 D 用，别各写一套文案）
ERRORS: Dict[str, str] = {
    "ACTION_POINTS_INSUFFICIENT": "行动点不足，本轮无法再提交行动",
    "TERM_LOCKED": "该条款已锁定，本局不再变更",
    "VALUE_OUT_OF_RANGE": "数值超出可谈范围",
    "PHASE_CLOSED": "谈判已结束，页面进入只读",
    "VERSION_CONFLICT": "版本冲突：对方已有更新版本，请刷新后重试",
    "DUPLICATE_ACTION": "重复提交：这次行动已经生效过了",
    "REDLINE_VIOLATION": "该方案触碰我方红线，不能作为我方提案提交",
    "AGREEMENT_HAS_OPEN_ISSUES": "仍有未决条款，现在不能接受",
    "NO_COUNTERPART_OFFER": "对方还没有报价，没有可接受的对象",
    "UNKNOWN_ACTION_TYPE": "未知的行动类型",
}

ALLOWED_ACTIONS = {
    "offer", "counter_offer", "conditional_swap",
    "final_offer", "accept", "reject", "withdraw",
}

# 指数更新标签：模型只允许输出这些离散标签，数值一律由 engine/indices.py 查表得出
EFFECT_LABELS = {
    "cooperative_winwin", "firm_stand", "conditional_concession",
    "procedural", "redline_provoke", "over_concede",
    "emotional_attack", "diplomatic_ease",
}
EFFECT_MAGNITUDES = {"slight", "moderate", "major"}


def _clause_spec(scenario: dict, name: str) -> Optional[dict]:
    for c in scenario.get("clauses", []):
        if c["name"] == name:
            return c
    return None


def validate_action(state, action: dict, scenario: dict) -> Tuple[bool, Optional[str], str]:
    """返回 (ok, error_code, message)。ok=True 时 error_code 为 None。"""
    atype = action.get("action_type")
    actor = action.get("actor")
    action_id = action.get("action_id", "")

    if atype not in ALLOWED_ACTIONS:
        return False, "UNKNOWN_ACTION_TYPE", ERRORS["UNKNOWN_ACTION_TYPE"]

    if state.status != "active":
        return False, "PHASE_CLOSED", ERRORS["PHASE_CLOSED"]

    if action_id and action_id in state.seen_action_ids:
        return False, "DUPLICATE_ACTION", ERRORS["DUPLICATE_ACTION"]

    # 版本冲突：客户端基于旧版本提交
    base_version = action.get("base_version")
    if base_version is not None and base_version != state.current_version:
        return False, "VERSION_CONFLICT", ERRORS["VERSION_CONFLICT"]

    # 接受类行动
    if atype == "accept":
        if state.open_issues:
            return False, "AGREEMENT_HAS_OPEN_ISSUES", ERRORS["AGREEMENT_HAS_OPEN_ISSUES"]
        if not [o for o in state.offers if o.actor != actor]:
            return False, "NO_COUNTERPART_OFFER", ERRORS["NO_COUNTERPART_OFFER"]
        return True, None, "ok"

    if atype in ("reject", "withdraw"):
        return True, None, "ok"

    # 报价类行动需要行动点
    if state.action_points <= 0:
        return False, "ACTION_POINTS_INSUFFICIENT", ERRORS["ACTION_POINTS_INSUFFICIENT"]

    patch = action.get("offer_patch") or {}
    if not patch:
        return False, "VALUE_OUT_OF_RANGE", "报价内容为空"

    party = (scenario.get("parties") or {}).get(actor, {})

    for name, value in patch.items():
        spec = _clause_spec(scenario, name)
        if spec is None:
            return False, "VALUE_OUT_OF_RANGE", f"未知条款：{name}"

        if spec.get("locked"):
            return False, "TERM_LOCKED", ERRORS["TERM_LOCKED"]

        lo, hi = spec.get("range", [None, None])
        if isinstance(value, (int, float)):
            if lo is not None and value < lo:
                return False, "VALUE_OUT_OF_RANGE", f"{name} 不能低于 {lo}{spec.get('unit','')}"
            if hi is not None and value > hi:
                return False, "VALUE_OUT_OF_RANGE", f"{name} 不能高于 {hi}{spec.get('unit','')}"

        # 自己主动提的方案不该越过自己的红线
        red = (party.get("redline") or {}).get(name)
        if red and isinstance(value, (int, float)):
            if "min" in red and value < red["min"]:
                return False, "REDLINE_VIOLATION", f"{name} 低于我方红线 {red['min']}"
            if "max" in red and value > red["max"]:
                return False, "REDLINE_VIOLATION", f"{name} 高于我方红线 {red['max']}"

    return True, None, "ok"


def validate_effect(effect: dict, scenario: dict):
    """校验模型输出的指数更新标签，返回 (ok, error_code, message)。

    原则：模型只能给离散标签（action_type + magnitude），不能给数值；
    数值由引擎查 scenario.index_rules 得出，保证可回放、可审计。
    """
    atype = effect.get("action_type")
    if atype not in EFFECT_LABELS:
        return False, "UNKNOWN_EFFECT_LABEL", f"未知的发言标签：{atype}"
    mag = effect.get("magnitude", "moderate")
    if mag not in EFFECT_MAGNITUDES:
        return False, "MISSING_MAGNITUDE", f"缺失或非法的幅度档位：{mag}，应为 slight/moderate/major"
    rule = (scenario.get("index_rules") or {}).get("actions") or {}
    if atype not in rule:
        return False, "UNKNOWN_EFFECT_LABEL", f"场景未配置该发言标签：{atype}"
    return True, None, "ok"

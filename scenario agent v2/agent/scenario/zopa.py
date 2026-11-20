"""ZOPA 与效用：交付给规则引擎的确定性参考实现。

回答两个问题：
1. 每个议题上，双方的可行区间有没有交集（ZOPA）
2. 任一份成交方案，双方效用是否都高于各自的 BATNA

只做纯计算，不调模型、不写状态。

口径（与引擎 `engine/indices.py::score` 完全一致，两处必须同改）：
· numeric：红线锚定。红线（无硬红线退软红线，再无退区间端点）为 0，
  目标值为 1，超过目标封顶 1.0。踩红线等于不谈，BATNA 比较才有意义
· enumerated：逐方按 target 位次衰减（target=1.0，其余按 order 距离线性递减），
  不再用「P2 取 order/N」的反推公式，因为那假设双方偏好完全相反，
  而实际场景 P1 目标 O2、P2 目标 O3，假设不成立（BACKLOG #4）
· 效用 = 100 × Σ(weight × score)
"""
from __future__ import annotations

import itertools
from typing import Any, Mapping

__all__ = [
    "accept_region", "issue_feasibility", "scenario_feasibility",
    "score", "utility", "evaluate_deal", "suggest_deal",
]

_EPS = 1e-9


def _parties(scenario: Mapping[str, Any]) -> list[str]:
    return [party["party_id"] for party in scenario.get("parties") or []]


def _issues(scenario: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {issue["issue_id"]: issue for issue in scenario.get("issues") or []}


def _state(scenario: Mapping[str, Any], party_id: str) -> Mapping[str, Any]:
    return (scenario.get("private_state_by_party") or {}).get(party_id) or {}


def _goal(state: Mapping[str, Any], issue_id: str) -> Mapping[str, Any]:
    for goal in state.get("goals") or []:
        if goal.get("issue_id") == issue_id:
            return goal
    return {}


def _edge_redlines(state: Mapping[str, Any], issue_id: str) -> list[Mapping[str, Any]]:
    """边界红线：优先硬红线；该议题一条硬红线都没有时退回软红线。

    只用硬红线会让「没设硬红线」的议题变成全区间可接受，
    ZOPA 假性变宽、参考成交点跑到 range 极值。
    """
    matched = [r for r in state.get("redlines") or [] if r.get("issue_id") == issue_id]
    hard = [r for r in matched if r.get("hard")]
    return hard or matched


def _option_ids(issue: Mapping[str, Any]) -> list[str]:
    return [option["option_id"] for option in issue.get("options") or []]


def _order_of(issue: Mapping[str, Any], option_id: str) -> int:
    for option in issue.get("options") or []:
        if option.get("option_id") == option_id:
            return int(option.get("order", 1))
    raise KeyError(f"{issue.get('issue_id')} 没有选项 {option_id!r}")


def accept_region(scenario: Mapping[str, Any], party_id: str, issue_id: str) -> Any:
    """该方在该议题上的可接受范围。numeric 返回 (lo, hi)，enumerated 返回集合。"""
    issue = _issues(scenario)[issue_id]
    state = _state(scenario, party_id)
    redlines = _edge_redlines(state, issue_id)

    if issue.get("type") == "numeric":
        value_range = issue.get("range") or {}
        low = float(value_range.get("min", 0))
        high = float(value_range.get("max", low))
        for redline in redlines:
            value = redline.get("value")
            if not isinstance(value, (int, float)):
                continue
            if redline.get("op") == "min":
                low = max(low, float(value))
            elif redline.get("op") == "max":
                high = min(high, float(value))
        return (low, high)

    allowed = set(_option_ids(issue))
    for redline in redlines:
        if redline.get("op") == "in" and isinstance(redline.get("value"), list):
            allowed &= set(redline["value"])
    return allowed


def issue_feasibility(scenario: Mapping[str, Any], issue_id: str) -> dict[str, Any]:
    parties = _parties(scenario)
    if len(parties) != 2:
        raise ValueError(f"仅支持双边，实际 {len(parties)} 方")
    left, right = parties
    region_a = accept_region(scenario, left, issue_id)
    region_b = accept_region(scenario, right, issue_id)
    issue = _issues(scenario)[issue_id]

    if issue.get("type") == "numeric":
        low = max(region_a[0], region_b[0])
        high = min(region_a[1], region_b[1])
        feasible = low - _EPS <= high
        step = float((issue.get("range") or {}).get("step", 1) or 1)
        suggested = None
        if feasible:
            midpoint = (low + high) / 2
            suggested = low + round((midpoint - low) / step) * step
            suggested = min(max(suggested, low), high)
        return {
            "issue_id": issue_id, "type": "numeric", "feasible": feasible,
            "zopa": [low, high] if feasible else None,
            "suggested": suggested,
            "detail": f"{left}=[{region_a[0]:g},{region_a[1]:g}] ∩ {right}=[{region_b[0]:g},{region_b[1]:g}]",
        }

    common = region_a & region_b
    ordered = sorted(common, key=lambda opt: _order_of(issue, opt))
    return {
        "issue_id": issue_id, "type": "enumerated", "feasible": bool(common),
        "zopa": ordered, "suggested": ordered[0] if ordered else None,
        "detail": f"{left}={sorted(region_a)} ∩ {right}={sorted(region_b)}",
    }


def scenario_feasibility(scenario: Mapping[str, Any]) -> dict[str, Any]:
    per_issue = {iid: issue_feasibility(scenario, iid) for iid in _issues(scenario)}
    infeasible = [iid for iid, item in per_issue.items() if not item["feasible"]]
    return {"zopa_exists": not infeasible, "infeasible_issues": infeasible, "per_issue": per_issue}


def score(scenario: Mapping[str, Any], party_id: str, issue_id: str, value: Any) -> float:
    """该方在该议题上取某个值的得分，0~1。"""
    issue = _issues(scenario)[issue_id]
    parties = _parties(scenario)
    state = _state(scenario, party_id)
    goal = _goal(state, issue_id)
    if not goal:
        raise KeyError(f"{party_id} 没有覆盖 {issue_id} 的 goal")

    if issue.get("type") == "numeric":
        value_range = issue.get("range") or {}
        target = float(goal.get("target"))
        direction = goal.get("direction")
        redlines = _edge_redlines(state, issue_id)
        if direction == "higher_better":
            anchor = float(value_range.get("min", 0))
            for redline in redlines:
                if redline.get("op") == "min" and isinstance(redline.get("value"), (int, float)):
                    anchor = max(anchor, float(redline["value"]))
            numerator, denominator = float(value) - anchor, target - anchor
        elif direction == "lower_better":
            anchor = float(value_range.get("max", 0))
            for redline in redlines:
                if redline.get("op") == "max" and isinstance(redline.get("value"), (int, float)):
                    anchor = min(anchor, float(redline["value"]))
            numerator, denominator = anchor - float(value), anchor - target
        else:
            raise ValueError(f"{issue_id} 是 numeric，direction 不能是 {direction!r}")
        # 红线与目标重合（零容忍议题）：只有精确落在目标上才算满分。
        # 与引擎 `engine/indices.py::score` 保持同一处理，否则同一份方案
        # 会出现 App 给 1.0、QA 给 0.0 的分歧（backup 的「追溯适用期」就是这种）。
        if denominator == 0:
            return 1.0 if float(value) == target else 0.0
        return max(0.0, min(1.0, numerator / denominator))

    total = len(issue.get("options") or [])
    for option in issue.get("options") or []:
        if option.get("option_id") == value:
            scores = option.get("score_by_party")
            if isinstance(scores, Mapping):
                for key, candidate in scores.items():
                    if isinstance(key, str) and key.lower() == party_id.lower():
                        return float(candidate)
            break

    # 逐方按 target 位次衰减，与适配层 `_ranked_scores` 同一公式。
    option_ids = [
        item["option_id"]
        for item in sorted(
            issue.get("options") or [], key=lambda item: item.get("order", 1)
        )
    ]
    target = goal.get("target")
    if target in option_ids and value in option_ids:
        if total <= 1:
            return 1.0
        step = 1.0 / (total - 1)
        distance = abs(option_ids.index(value) - option_ids.index(target))
        return max(0.0, 1.0 - distance * step)

    # 数据不完整（target 不在选项里）时才退回 order 推导，并保持原方向约定。
    order = _order_of(issue, value)
    if party_id == parties[0]:
        return (total - order + 1) / total
    return order / total


def utility(scenario: Mapping[str, Any], party_id: str, deal: Mapping[str, Any]) -> float:
    """一份成交方案下该方的效用，0~100。未给出的议题不计分。"""
    total = 0.0
    for goal in _state(scenario, party_id).get("goals") or []:
        issue_id = goal["issue_id"]
        weight = float(goal.get("weight") or 0.0)
        if issue_id in deal:
            total += weight * score(scenario, party_id, issue_id, deal[issue_id])
    return round(100 * total, 2)


def evaluate_deal(scenario: Mapping[str, Any], deal: Mapping[str, Any]) -> dict[str, Any]:
    """依次算：效用、BATNA 比较、硬红线违反。"""
    result: dict[str, Any] = {"deal": dict(deal), "parties": {}}
    for party_id in _parties(scenario):
        state = _state(scenario, party_id)
        value = utility(scenario, party_id, deal)
        batna = float((state.get("batna") or {}).get("utility") or 0.0)
        violations = []
        for redline in state.get("redlines") or []:
            if not redline.get("hard"):
                continue
            issue_id = redline.get("issue_id")
            if issue_id not in deal:
                continue
            actual = deal[issue_id]
            op = redline.get("op")
            limit = redline.get("value")
            breached = False
            if op == "min" and isinstance(limit, (int, float)):
                breached = actual < limit
            elif op == "max" and isinstance(limit, (int, float)):
                breached = actual > limit
            elif op == "eq":
                breached = actual != limit
            elif op == "in" and isinstance(limit, list):
                breached = actual not in limit
            if breached:
                violations.append({"issue_id": issue_id, "op": op, "value": limit, "actual": actual})
        result["parties"][party_id] = {
            "utility": value, "batna": batna,
            "above_batna": value >= batna,
            "redline_violations": violations,
        }
    result["all_above_batna"] = all(item["above_batna"] for item in result["parties"].values())
    result["any_redline_violated"] = any(item["redline_violations"] for item in result["parties"].values())
    return result


def _deal_candidates(
    scenario: Mapping[str, Any], issue_id: str, item: Mapping[str, Any]
) -> list[Any]:
    """单个议题的候选取值：数值取可行区间端点/中点/建议点/双方理想值，枚举取交集。"""
    if item["type"] != "numeric":
        return list(item["zopa"])
    low, high = item["zopa"]
    points = {float(low), float(high), (float(low) + float(high)) / 2.0}
    if item["suggested"] is not None:
        points.add(float(item["suggested"]))
    for party in _parties(scenario):
        goal = _goal(_state(scenario, party), issue_id)
        target = goal.get("target")
        if isinstance(target, (int, float)) and low <= float(target) <= high:
            points.add(float(target))
    return sorted(points)


def suggest_deal(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """在可行域里取「双方最差效用最大」（max-min）的均衡方案，供自检与 Demo 使用。

    旧实现取每个议题 order 最小的选项，而 order=1 恒为「对 P1 最有利」，
    等于系统性偏袒 P1：backup 场景因此给出 63.75 / 28.33（P2 低于 BATNA 35），
    而同一可行域里存在 50.0 / 46.67 的均衡点。这里改为穷举可行组合取 max-min，
    并以效用和对 max-min 相同的组合做确定性 tie-break。
    """
    per_issue = scenario_feasibility(scenario)["per_issue"]
    feasible = {
        issue_id: item
        for issue_id, item in per_issue.items()
        if item["suggested"] is not None
    }
    if not feasible:
        return {}
    issue_ids = list(feasible)
    pools = [
        _deal_candidates(scenario, issue_id, feasible[issue_id])
        for issue_id in issue_ids
    ]
    parties = _parties(scenario)
    best_key: tuple[float, float] | None = None
    best_deal: dict[str, Any] = {}
    for combo in itertools.product(*pools):
        deal = dict(zip(issue_ids, combo))
        utils = [utility(scenario, party, deal) for party in parties]
        key = (min(utils), sum(utils))
        if best_key is None or key > best_key:
            best_key = key
            best_deal = deal
    return best_deal

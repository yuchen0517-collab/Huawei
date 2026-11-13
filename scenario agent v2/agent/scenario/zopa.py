"""ZOPA 与效用：交付给规则引擎的确定性参考实现。

回答两个问题：
1. 每个议题上，双方的可行区间有没有交集（ZOPA）
2. 任一份成交方案，双方效用是否都高于各自的 BATNA

只做纯计算，不调模型、不写状态。

口径（与 load_scenario.py 一致）：
· numeric：区间被红线收窄；有硬红线用硬红线，没有则退回软红线
· enumerated：可接受集合 = 全部选项减去红线禁用的选项
· 得分：numeric 线性归一到 0~1；enumerated 按 order，
  parties[0] 用 (N-order+1)/N、parties[1] 用 order/N
· 效用 = 100 × Σ(weight × score)
"""
from __future__ import annotations

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
            reservation = float(value_range.get("min", 0))
            for redline in redlines:
                if redline.get("op") == "min" and isinstance(redline.get("value"), (int, float)):
                    reservation = max(reservation, float(redline["value"]))
            raw = (float(value) - reservation) / (target - reservation) if target != reservation else 0.0
        elif direction == "lower_better":
            reservation = float(value_range.get("max", 0))
            for redline in redlines:
                if redline.get("op") == "max" and isinstance(redline.get("value"), (int, float)):
                    reservation = min(reservation, float(redline["value"]))
            raw = (reservation - float(value)) / (reservation - target) if reservation != target else 0.0
        else:
            raise ValueError(f"{issue_id} 是 numeric，direction 不能是 {direction!r}")
        return max(0.0, min(1.0, raw))

    total = len(issue.get("options") or [])
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


def suggest_deal(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """每个 feasible 议题取交集内的点，拼一份参考成交方案，供自检与 Demo 使用。"""
    deal: dict[str, Any] = {}
    for issue_id, item in scenario_feasibility(scenario)["per_issue"].items():
        if item["suggested"] is not None:
            deal[issue_id] = item["suggested"]
    return deal

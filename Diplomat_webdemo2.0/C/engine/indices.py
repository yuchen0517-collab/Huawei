# -*- coding: utf-8 -*-
"""三指数更新引擎 —— 对应成员A提供的《双方三指数更新规则》

设计立场（与手册 2.1 / 5.2 对齐）：
1. 模型只输出离散标签（action_type + magnitude），数值一律由本模块查表得出；
2. 所有更新写 public_events 留痕（before / after / delta / clamped），可回放、可审计；
3. 结算里没有随机数：delta = round(base × sensitivity)，同输入必同输出；
4. Interest 由条款实质决定（口头让步不算），Image 由行为合规性决定，Trust 由履约一致性决定；
5. 对方指数不受我方发言直接影响——模型无权改写对方事实（手册 2.1 权限边界）。
"""

from typing import Any, Dict, List, Optional
import copy

INDEX_FIELDS = ("interest", "image", "trust")
MAGNITUDES = ("slight", "moderate", "major")


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _clause_score(spec: dict, value: Any, ideal: Any) -> float:
    """单条款得分：离理想点越近越高，归一到 0~1。"""
    lo, hi = spec.get("range", [0, 1])
    if hi == lo or value is None or ideal is None:
        return 0.0
    span = hi - lo
    return max(0.0, 1.0 - abs(value - ideal) / span)


def initialize_indices(state, index_rules: dict) -> None:
    """按场景初值初始化双方三指数。没有配置时保持空 dict。"""
    state.indices = copy.deepcopy(index_rules.get("initial", {}) or {})


def resolve_delta(scenario: dict, party: str, action_type: str,
                  magnitude: str = "moderate") -> Dict[str, int]:
    """查表得到 (image, trust) 的 delta；幅度缺失时回落 moderate，再回落 any。

    返回值为 round(base × sensitivity)，保证同场景同输入必同输出。
    """
    rules = (scenario.get("index_rules") or {}).get("actions") or {}
    rule = rules.get(action_type)
    if not rule:
        return {}
    base: Dict[str, Any] = {}
    for idx in ("image", "trust"):
        table = rule.get(idx) or {}
        if "any" in table:
            base[idx] = table["any"]
        else:
            base[idx] = table.get(magnitude, table.get("moderate", 0))
    sens = ((scenario.get("index_rules") or {}).get("sensitivity") or {}).get(party) or {}
    out: Dict[str, int] = {}
    for idx, v in base.items():
        if v:
            out[idx] = round(float(v) * float(sens.get(idx, 1.0)))
    return out


def apply_round_effects(state, scenario: dict, effects: List[dict]) -> List[dict]:
    """把模型输出的 effect 标签转成指数变化并留痕。

    effects 示例：[{"action_type": "cooperative_winwin", "magnitude": "moderate",
                    "actor": "CN", "reason": "提出共同开发方案"}]

    只影响 actor 自己的 image / trust；对方指数不被模型改写。
    返回实际发生的 index_change 事件列表（已同时追加到 state.public_events）。
    """
    if not state.indices:
        initialize_indices(state, scenario.get("index_rules") or {})
    events: List[dict] = []
    for e in effects:
        actor = e.get("actor")
        if not actor:
            continue
        deltas = resolve_delta(scenario, actor, e.get("action_type", ""),
                               e.get("magnitude", "moderate"))
        if not deltas:
            continue
        party_idx = state.indices.setdefault(actor, {f: 50.0 for f in INDEX_FIELDS})
        for idx, delta in deltas.items():
            before = float(party_idx.get(idx, 50.0))
            after_raw = before + delta
            after = round(_clamp(after_raw), 1)
            ev = {
                "round": state.round,
                "type": "index_change",
                "party": actor,
                "index": idx,
                "before": before,
                "after": after,
                "delta": delta,
                "clamped": after != after_raw,
                "action_type": e.get("action_type"),
                "magnitude": e.get("magnitude"),
                "reason": e.get("reason", ""),
            }
            party_idx[idx] = after
            state.public_events.append(ev)
            events.append(ev)
    return events


def compute_interest_from_clauses(state, scenario: dict, party: str) -> float:
    """Interest 由条款实质决定：最新报价相对该方 ideal 的加权接近度（0-100）。

    - 尚无报价时回退场景初始值；
    - 口头让步（条款无变化）不会改变 interest，天然挡住"嘴上让步刷利益值"。
    """
    index_rules = scenario.get("index_rules") or {}
    fallback = float((index_rules.get("initial") or {}).get(party, {}).get("interest", 50.0))
    offer = state.latest_offer()
    if offer is None:
        return fallback
    party_spec = (scenario.get("parties") or {}).get(party, {})
    ideal = party_spec.get("ideal", {})
    acc, total_w = 0.0, 0.0
    for spec in scenario.get("clauses", []):
        name = spec["name"]
        if name not in offer.clauses:
            continue
        w = spec.get("weight", 1.0)
        total_w += w
        acc += w * _clause_score(spec, offer.clauses[name], ideal.get(name))
    if not total_w:
        return fallback
    return round(acc / total_w * 100.0, 1)


def refresh_interest(state, scenario: dict) -> None:
    """回合末/报价后调用：按最新条款重算双方 interest 并留痕（仅变化时）。"""
    if not state.indices:
        initialize_indices(state, scenario.get("index_rules") or {})
    for party in (state.indices.keys() or list((scenario.get("parties") or {}).keys())):
        before = float(state.indices.setdefault(party, {f: 50.0 for f in INDEX_FIELDS}).get("interest", 50.0))
        after = compute_interest_from_clauses(state, scenario, party)
        if after != before:
            state.indices[party]["interest"] = after
            state.public_events.append({
                "round": state.round,
                "type": "index_change",
                "party": party,
                "index": "interest",
                "before": before,
                "after": after,
                "delta": round(after - before, 1),
                "clamped": False,
                "action_type": "clause_settlement",
                "magnitude": None,
                "reason": "Interest 按最新报价相对 ideal 的条款距离重算",
            })


def replay_from_events(state, events: List[dict]) -> List[str]:
    """从存档 public_events 重放指数：只依赖事件流，不再调用模型或查表。

    事件流内部不一致（before 与上一事件 after 不连续）时返回错误列表，
    不一致的事件会被跳过，保证重放结果可审计、可追溯。
    """
    errors: List[str] = []
    for e in events:
        if e.get("type") != "index_change":
            continue
        party = e.get("party")
        idx = e.get("index")
        before = e.get("before")
        after = e.get("after")
        if party is None or idx is None or after is None:
            errors.append(f"事件缺字段：{e}")
            continue
        party_idx = state.indices.setdefault(party, {f: 50.0 for f in INDEX_FIELDS})
        current = float(party_idx.get(idx, 50.0))
        if before is not None and abs(current - float(before)) > 1e-6:
            errors.append(f"{party}.{idx} 不连续：当前 {current}，事件 before {before}")
            continue
        party_idx[idx] = float(after)
    return errors

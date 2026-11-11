# -*- coding: utf-8 -*-
"""终局判定与评价 —— 对应手册 5.2「终局判定与评价必须分开」

三层结构，绝不能合成一个分数：
  1) 谈判结果 terminal_type：完整协议 / 部分协议 / 主动退出 / 僵局 / 回合耗尽
  2) 协议质量 agreement_quality：红线、BATNA、条款完整性
  3) 学习表现 learning_performance：是否识别分歧、是否有条件交换、是否过度让步

核心立场：达成协议 ≠ 成功，退出 ≠ 失败。
"""

from typing import Any, Dict, Optional

TERMINAL_TYPES = {
    "FULL_AGREEMENT": "完整协议",
    "PARTIAL_AGREEMENT": "部分协议",
    "WITHDRAWAL": "主动退出",
    "DEADLOCK": "僵局终止",
    "ROUNDS_EXHAUSTED": "回合耗尽",
}


def check_terminal(state, scenario: dict, last_action: Optional[dict] = None) -> Optional[dict]:
    """返回终局结果 dict，未终结返回 None。顺序即优先级。"""
    if state.status == "ended":
        return state.terminal

    # 1. 协议类：签了，但要看签全了没有
    if state.agreement is not None:
        covered = set(state.agreement.clauses)
        missing = [c["name"] for c in scenario.get("clauses", []) if c["name"] not in covered]
        full = (not state.open_issues) and (not missing)
        t = "FULL_AGREEMENT" if full else "PARTIAL_AGREEMENT"
        reason = "双方接受同一版本 V%d" % state.agreement.version
        if missing:
            reason += "；未覆盖条款：" + "、".join(missing)
        return {"terminal_type": t, "label": TERMINAL_TYPES[t], "reason": reason,
                "version": state.agreement.version, "missing_clauses": missing}

    # 2. 主动退出
    if last_action and last_action.get("action_type") == "withdraw":
        return {"terminal_type": "WITHDRAWAL", "label": TERMINAL_TYPES["WITHDRAWAL"],
                "reason": "%s 主动退出谈判" % last_action.get("actor"), "version": state.current_version}

    # 3. 僵局（连续 N 轮没有任何新报价）
    deadlock_rounds = scenario.get("deadlock_rounds", 2)
    if state.rounds_without_offer >= deadlock_rounds:
        return {"terminal_type": "DEADLOCK", "label": TERMINAL_TYPES["DEADLOCK"],
                "reason": "连续 %d 轮无新报价，视为僵局" % state.rounds_without_offer,
                "version": state.current_version}

    # 4. 回合耗尽
    max_rounds = scenario.get("max_rounds", 12)
    if state.round > max_rounds:
        return {"terminal_type": "ROUNDS_EXHAUSTED", "label": TERMINAL_TYPES["ROUNDS_EXHAUSTED"],
                "reason": "已达最大回合 %d" % max_rounds, "version": state.current_version}

    return None


# ---------- 协议质量 ----------

def _clause_score(spec: dict, value: Any, ideal: Any) -> float:
    """单条款得分：离理想点越近越高，归一到 0~1。"""
    lo, hi = spec.get("range", [0, 1])
    if hi == lo or value is None or ideal is None:
        return 0.0
    span = hi - lo
    return max(0.0, 1.0 - abs(value - ideal) / span)


def evaluate_agreement(state, scenario: dict, actor: str) -> dict:
    """只评价协议本身，不评价人。"""
    if state.agreement is None:
        return {"available": False, "reason": "本局未达成协议"}

    clauses = state.agreement.clauses
    party = (scenario.get("parties") or {}).get(actor, {})
    ideal = party.get("ideal", {})
    redline = party.get("redline", {})

    # 红线检查：逐条给出违反项，不笼统说"违规"
    violations = []
    for name, red in redline.items():
        v = clauses.get(name)
        if not isinstance(v, (int, float)):
            continue
        if ("min" in red and v < red["min"]) or ("max" in red and v > red["max"]):
            violations.append({"clause": name, "value": v, "redline": red})

    # 加权得分
    total_w, acc = 0.0, 0.0
    for spec in scenario.get("clauses", []):
        name = spec["name"]
        if name not in clauses:
            continue
        w = spec.get("weight", 1.0)
        total_w += w
        acc += w * _clause_score(spec, clauses[name], ideal.get(name))
    score = round(acc / total_w, 3) if total_w else 0.0

    batna = party.get("batna", 0.0)
    return {
        "available": True,
        "version": state.agreement.version,
        "redline_ok": not violations,
        "redline_violations": violations,
        "score": score,
        "batna": batna,
        "batna_gap": round(score - batna, 3),
        "better_than_batna": score > batna,
        "missing_clauses": [c["name"] for c in scenario.get("clauses", []) if c["name"] not in clauses],
        "open_issues": list(state.open_issues),
        "index_final": dict(state.indices or {}),   # 终局指数终值（三指数维度）
    }


def evaluate(state, scenario: dict, actor: str, last_action: Optional[dict] = None) -> dict:
    """三层一起出，但分字段返回，UI 不许合成一个总分。"""
    terminal = state.terminal or check_terminal(state, scenario, last_action)
    quality = evaluate_agreement(state, scenario, actor)

    if terminal is None:
        return {"terminal": None, "agreement_quality": quality}

    t = terminal["terminal_type"]
    if t in ("FULL_AGREEMENT", "PARTIAL_AGREEMENT"):
        verdict = "协议达成，质量见下方红线与 BATNA 对比"
    elif t == "WITHDRAWAL":
        verdict = "主动退出：若 BATNA 优于可获方案，这是理性选择" if quality.get("batna_gap", 0) < 0 else "主动退出，但 BATNA 并未优于可获方案，属于过早放弃"
    elif t == "DEADLOCK":
        verdict = "僵局：需回看是议题无合作区间，还是策略选择失误"
    else:
        verdict = "回合耗尽：未收敛到可签署版本"

    return {
        "terminal": terminal,
        "agreement_quality": quality,
        "verdict": verdict,
        "task_hits": _task_hits(state),   # 只报事实（哪些学习任务条件命中），评价交给 D 的教练 Agent
        "learning_performance": {"note": "待接教练 Agent（D 负责）", "evidence_links": []},
    }


def _task_hits(state) -> list:
    """从 state 的隐藏任务中挑出已达成（done=True）的，只返回文本事实，不做评价。"""
    tasks = getattr(state, "tasks", None) or []
    return [t.get("text", "") for t in tasks if t.get("done")]

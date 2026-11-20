"""按运行时场景生成对手 Agent 的 System Prompt 与初始指数。

背景（BACKLOG #3）：`agents.json` 的 `_scenario` 与各方 `cfg` 都是《全球AI治理
框架公约》题材，`谈判对手Agent_prompt.md` 里的占位符也从那里取值。结果是加载
B 的芯片 / DST 场景时，对手仍以 AI 治理代表的口吻发言，初始三项指数也沿用
agents.json 的 50 / 70 / 65，与本场景在 `index_rules.initial` 里声明的数值不符。

本模块把 prompt 变量全部改为从**运行时场景**派生：
主题、议题、双方公开立场、目标权重排序、红线、BATNA、隐藏任务卡都取自场景本身，
并追加场景自带的事实与教学假设。默认场景（ai_governance）仍用原来的手写 prompt，
避免动到已经打磨过的演示文案。
"""
from __future__ import annotations

from typing import Any, Optional

FACT_TYPE_ORDER = ("背景", "立场", "行动", "数据", "事件")
MAX_FACTS = 12


def _party(scenario: dict, party_id: str) -> Optional[dict]:
    for item in scenario.get("parties") or []:
        if isinstance(item, dict) and item.get("id") == party_id:
            return item
    return None


def _clause_names(scenario: dict) -> list[str]:
    return [
        clause.get("name", "")
        for clause in scenario.get("clauses") or []
        if clause.get("name")
    ]


def _enum_target(clause: dict, side: str) -> Optional[str]:
    """枚举题的「目标选项」：该方评分最高的选项（适配层把它记在 options[].score）。"""
    best_id, best_score = None, 0.0
    for option in clause.get("options") or []:
        score = float((option.get("score") or {}).get(side, 0.0))
        if score > best_score:
            best_id, best_score = option.get("id"), score
    return best_id


def _format_target(clause: dict, value: Any) -> str:
    if value is None:
        return "未设定"
    if clause.get("type") == "numeric":
        number = float(value)
        text = str(int(number)) if number.is_integer() else f"{number:g}"
        unit = clause.get("unit") or ""
        return f"{text}{unit}"
    for option in clause.get("options") or []:
        if option.get("id") == value:
            return f"{option.get('label') or value}（{value}）"
    return str(value)


def _interest_lines(scenario: dict, side: str) -> str:
    ranked = []
    for clause in scenario.get("clauses") or []:
        weight = float((clause.get("weights") or {}).get(side, 0.0))
        if weight <= 0:
            continue
        ideal = (clause.get("positions") or {}).get(side, {}).get("ideal")
        if ideal is None and clause.get("type") != "numeric":
            ideal = _enum_target(clause, side)
        ranked.append((weight, clause, ideal))
    ranked.sort(key=lambda item: -item[0])
    if not ranked:
        return "（本场景未提供逐议题权重）"
    return "\n".join(
        f"{index}. 「{clause.get('name')}」权重 {weight:.2f}，目标 {_format_target(clause, ideal)}"
        for index, (weight, clause, ideal) in enumerate(ranked, start=1)
    )

def _redline_lines(scenario: dict, side: str) -> str:
    lines = []
    for clause in scenario.get("clauses") or []:
        position = (clause.get("positions") or {}).get(side) or {}
        redline = position.get("redline")
        if redline is not None:
            direction = position.get("redline_direction")
            bound = "不得低于" if direction == "below_is_violation" else "不得高于"
            unit = clause.get("unit") or ""
            number = float(redline)
            text = str(int(number)) if number.is_integer() else f"{number:g}"
            lines.append(f"- 「{clause.get('name')}」{bound} {text}{unit}")
        forbidden = (clause.get("redlines") or {}).get(side) or []
        if forbidden:
            labels = [
                _format_target(clause, option_id) for option_id in forbidden
            ]
            lines.append(
                f"- 「{clause.get('name')}」不得选择 {'、'.join(labels)}"
            )
    return "\n".join(lines) if lines else "（本场景未给该方设定硬红线）"


def scenario_prompt_vars(scenario: dict, side: str) -> dict[str, str]:
    """把运行时场景转成 prompt 占位符。所有值都是场景里的真实内容。"""
    me = _party(scenario, side) or {}
    others = [
        party
        for party in scenario.get("parties") or []
        if isinstance(party, dict) and party.get("id") != side
    ]
    opponent = others[0] if others else {}
    private = me.get("private") or {}
    scenario_type = scenario.get("scenario_type")
    venue = (
        "假设情境（教学模拟）的闭门双边磋商"
        if scenario_type == "hypothesis"
        else "资料驱动的闭门双边磋商"
    )
    batna_value = me.get("batna")
    batna_note = private.get("batna_note") or ""
    batna = (
        f"{batna_value} 分（0–100 标尺）"
        + (f"；{batna_note}" if batna_note else "")
        if batna_value is not None
        else batna_note or "（本场景未给出 BATNA）"
    )
    return {
        "negotiation_topic": scenario.get("title") or "",
        "negotiation_venue": venue,
        "negotiation_agenda": "、".join(_clause_names(scenario)),
        "agent_entity": me.get("name") or side.upper(),
        "agent_identity": f"{me.get('name') or side.upper()} 首席谈判代表",
        "agent_position": "首席谈判代表",
        "negotiation_style": "务实、克制，先确认条款口径再谈让步，不做无对价的表态。",
        "public_position": me.get("public_position") or "（本场景未给该方设置公开立场）",
        "core_interests_ranked": _interest_lines(scenario, side),
        "red_lines": _redline_lines(scenario, side),
        "batna": batna,
        "hidden_task_card": private.get("bottom_line") or "（本场景未给该方设置隐藏任务）",
        "player_entity": opponent.get("name") or "对方代表团",
        "player_position": "谈判代表",
    }


def facts_section(scenario: dict) -> str:
    """把场景的公开事实与教学假设拼成 prompt 附录（无事实时返回空串）。"""
    facts = [fact for fact in scenario.get("public_facts") or [] if isinstance(fact, dict)]
    assumptions = [
        item for item in scenario.get("assumptions") or [] if isinstance(item, str) and item.strip()
    ]
    if not facts and not assumptions:
        return ""
    facts.sort(
        key=lambda fact: FACT_TYPE_ORDER.index(fact.get("type"))
        if fact.get("type") in FACT_TYPE_ORDER
        else len(FACT_TYPE_ORDER)
    )
    lines = ["## 可引用的事实（唯一依据，不得编造）"]
    for fact in facts[:MAX_FACTS]:
        source = (fact.get("source") or {}).get("name") or "未标注来源"
        label = fact.get("type") or "事实"
        lines.append(f"- 【{label}】{fact.get('text', '')}（来源：{source}）")
    if assumptions:
        lines += ["", "## 教学假设（不是事实，不得当作现实依据）"]
        lines += [f"- {item}" for item in assumptions]
    lines += [
        "",
        "### 引用规则",
        "1. 数字、机构名与条款必须与上文一致，不得四舍五入或自行编造。",
        "2. 标注为「教学假设」的内容只能作为推演前提，不得说成既成事实。",
        "3. 没有依据的事改用定性表述（「我方关切」「有待评估」），不要给具体数字。",
    ]
    return "\n".join(lines)


def build_scenario_prompt(md: str, scenario: dict, side: str) -> str:
    """用场景变量填充 System Prompt 模板，并附上本场景的事实与假设。"""
    import neg_cli as neg  # 延迟导入，避免与 api.py 的导入顺序耦合

    text = neg.extract_system_prompt(md)
    for key, value in scenario_prompt_vars(scenario, side).items():
        token = "{" + key + "}"
        if token in text:
            text = text.replace(token, str(value))

    block = facts_section(scenario)
    if block:
        marker = "## 输出格式"
        if marker in text:
            text = text.replace(marker, block + "\n\n" + marker, 1)
        else:
            text = text.rstrip() + "\n\n" + block
    return text

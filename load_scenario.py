from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
AGENTS_PATH = BASE_DIR / "agents.json"
SCENARIO_ID = "ai_governance"
ENGINE_DIR_NAME = "C 11.12 三指数"
CLAUSE_NAMES = (
    "全球算力资源分配",
    "前沿模型评测门槛",
    "数据跨境流动",
)


def _resolve_engine_root() -> Path:
    candidates = (BASE_DIR / ENGINE_DIR_NAME, BASE_DIR.parent / ENGINE_DIR_NAME)
    for candidate in candidates:
        if (candidate / "engine" / "core.py").is_file():
            return candidate
    raise FileNotFoundError(f"未找到规则引擎源码目录：{ENGINE_DIR_NAME}")


ENGINE_ROOT = _resolve_engine_root()


def _enum_clause(name: str, initial: Any, option_ids: list[Any]) -> dict:
    return {
        "name": name,
        "type": "enum",
        "initial": initial,
        "options": [
            {"id": option, "score": {"cn": 1.0, "us": 1.0}}
            for option in option_ids
        ],
        "weights": {"cn": 1 / 6, "us": 1 / 6},
    }


def _numeric_clause(name: str, initial: int) -> dict:
    return {
        "name": name,
        "type": "numeric",
        "initial": initial,
        "range": [0, 100],
        "positions": {
            "cn": {"ideal": 50},
            "us": {"ideal": 50},
        },
        "weights": {"cn": 1 / 6, "us": 1 / 6},
    }


def _make_index_rules(player: dict, opponent: dict) -> dict:
    """初始值取自 agents.json，结算表（image_actions/trust_actions/sensitivity）
    借用引擎自带 demo_scenario 的整表，与 B 场景转换器同一来源。"""
    rules = _borrowed_index_rules()
    rules["initial"] = {
        "cn": {
            "image": int(player["initial_image"]),
            "trust": int(player["initial_trust"]),
        },
        "us": {
            "image": int(opponent["initial_image"]),
            "trust": int(opponent["initial_trust"]),
        },
    }
    return rules


def make_scenario(agents_path: str | Path | None = None) -> dict:
    source_path = Path(agents_path) if agents_path is not None else AGENTS_PATH
    agents = json.loads(source_path.read_text(encoding="utf-8-sig"))
    player = agents["_scenario"]["player"]
    opponent = agents["us"]
    clauses = [
        _enum_clause(
            "全球算力资源分配",
            "附带可核查机制",
            [
                "附带可核查机制",
                "以既有联盟实践为蓝本设立高风险 AI 出口管制的可核查机制",
                "接受联合国框架下的技术性通报，但监督机制须具备实际约束力",
            ],
        ),
        _numeric_clause("前沿模型评测门槛", 50),
        _enum_clause(
            "数据跨境流动",
            "白名单互认",
            [
                "白名单互认",
                "增加对发展中国家的能力建设投入",
                "在联合国框架下建立对称适用的数据跨境通报机制",
            ],
        ),
    ]
    return {
        "scenario_id": SCENARIO_ID,
        "parties": [
            {
                "id": "cn",
                "label": player["label"],
                "private": {
                    "hidden_tasks": copy.deepcopy(player.get("hidden_tasks", [])),
                    "strategy": copy.deepcopy(player.get("strategy", {})),
                },
            },
            {
                "id": "us",
                "label": opponent["label"],
                "private": {
                    "red_lines": opponent.get("red_lines", ""),
                    "batna": opponent.get("batna", ""),
                    "hidden_task_card": opponent.get("hidden_task_card", ""),
                    "strategy": copy.deepcopy(opponent.get("strategy", {})),
                },
            },
        ],
        "clauses": clauses,
        "action_points_per_round": 5,
        "max_rounds": 12,
        "deadlock_rounds": 2,
        "index_rules": _make_index_rules(player, opponent),
    }


def is_b_scenario(data: Any) -> bool:
    return isinstance(data, dict) and "issues" in data and "private_state_by_party" in data


def _goal(private_state: dict, issue_id: str) -> dict:
    for goal in private_state.get("goals") or []:
        if goal.get("issue_id") == issue_id:
            return goal
    return {}


def _hard_redline(private_state: dict, issue_id: str) -> dict | None:
    for redline in private_state.get("redlines") or []:
        if redline.get("issue_id") == issue_id and redline.get("hard"):
            return redline
    return None


def _weights(parties: list, alias: dict, private_by_party: dict, issue_id: str) -> dict:
    weights = {}
    for party in parties:
        goal = _goal(private_by_party.get(party) or {}, issue_id)
        weights[alias[party]] = round(float(goal.get("weight") or 0.0), 4)
    return weights


def _convert_numeric(issue: dict, parties: list, alias: dict, private_by_party: dict) -> dict:
    value_range = issue.get("range") or {}
    minimum = value_range.get("min", 0)
    maximum = value_range.get("max", minimum)
    positions = {}
    for party in parties:
        private_state = private_by_party.get(party) or {}
        target = _goal(private_state, issue["issue_id"]).get("target")
        ideal = target if target is not None else minimum
        redline = _hard_redline(private_state, issue["issue_id"])
        redline_value = redline.get("value") if redline else None
        positions[alias[party]] = {
            "ideal": ideal,
            "redline": redline_value if redline_value is not None else ideal,
        }
    return {
        "name": issue["name"],
        "type": "numeric",
        "unit": issue.get("unit") or "",
        "range": [minimum, maximum],
        "initial": minimum,
        "weights": _weights(parties, alias, private_by_party, issue["issue_id"]),
        "positions": positions,
    }


def _convert_enumerated(issue: dict, parties: list, alias: dict, private_by_party: dict) -> dict:
    options = issue.get("options") or []
    total = len(options)
    converted_options = []
    for option in options:
        order = option["order"]
        converted_options.append({
            "id": option["label"],
            "score": {
                alias[parties[0]]: round((total - order + 1) / total, 4),
                alias[parties[1]]: round(order / total, 4),
            },
        })
    redlines = {}
    for party in parties:
        private_state = private_by_party.get(party) or {}
        redline = _hard_redline(private_state, issue["issue_id"])
        allowed = None
        if redline and redline.get("op") == "in" and redline.get("value"):
            allowed = set(redline["value"])
        if allowed is None:
            redlines[alias[party]] = []
        else:
            redlines[alias[party]] = [
                option["label"] for option in options if option["option_id"] not in allowed
            ]
    return {
        "name": issue["name"],
        "type": "enum",
        "options": converted_options,
        "initial": options[0]["label"] if options else None,
        "weights": _weights(parties, alias, private_by_party, issue["issue_id"]),
        "redlines": redlines,
    }


def _borrowed_index_rules() -> dict:
    demo_path = ENGINE_ROOT / "scenarios" / "demo_scenario.json"
    demo = json.loads(demo_path.read_text(encoding="utf-8-sig"))
    return copy.deepcopy(demo["index_rules"])


def convert_b_scenario(data: dict) -> dict:
    party_list = data.get("parties") or []
    parties = [party["party_id"] for party in party_list]
    if len(parties) != 2:
        raise ValueError(f"B 场景仅支持双方谈判，实际参与方数量：{len(parties)}")
    alias = dict(zip(parties, ("cn", "us")))
    private_by_party = data.get("private_state_by_party") or {}
    clauses = []
    for issue in data.get("issues") or []:
        if issue.get("type") == "numeric":
            clauses.append(_convert_numeric(issue, parties, alias, private_by_party))
        else:
            clauses.append(_convert_enumerated(issue, parties, alias, private_by_party))
    converted_parties = []
    for party in party_list:
        private_state = private_by_party.get(party["party_id"]) or {}
        bottom_line = "；".join(
            redline["reason"]
            for redline in private_state.get("redlines") or []
            if redline.get("hard") and redline.get("reason")
        )
        converted_parties.append({
            "id": alias[party["party_id"]],
            "name": party.get("name") or "",
            "role": party.get("role_label") or "",
            "batna": (private_state.get("batna") or {}).get("utility"),
            "private": {
                "bottom_line": bottom_line,
                "notes": private_state.get("hidden_task") or "",
            },
        })
    terminal_rules = data.get("terminal_rules") or {}
    return {
        "scenario_id": data.get("scenario_id") or "b_scenario",
        "title": data.get("title") or "",
        "scenario_type": data.get("scenario_type") or "hypothesis",
        "background": data.get("background") or "",
        "assumptions": [
            assumption["text"]
            for assumption in data.get("assumptions") or []
            if assumption and assumption.get("text")
        ],
        "max_rounds": data.get("max_rounds") or 12,
        "deadlock_rounds": 2,
        "action_points_per_round": 3,
        "parties": converted_parties,
        "clauses": clauses,
        "index_rules": _borrowed_index_rules(),
        "terminal_rules": {
            "accept_requires_no_open_issues": terminal_rules.get(
                "accept_requires_no_open_issue", True
            )
        },
    }


def load_scenario(path: str | Path | None = None) -> dict:
    if path is None:
        return make_scenario()
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if is_b_scenario(data):
        return convert_b_scenario(data)
    return data
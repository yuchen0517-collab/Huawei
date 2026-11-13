from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
AGENTS_PATH = BASE_DIR / "agents.json"
SCENARIO_ID = "ai_governance"
CLAUSE_NAMES = (
    "全球算力资源分配",
    "前沿模型评测门槛",
    "数据跨境流动",
)


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
        "index_rules": {
            "initial": {
                "cn": {
                    "image": int(player["initial_image"]),
                    "trust": int(player["initial_trust"]),
                },
                "us": {
                    "image": int(opponent["initial_image"]),
                    "trust": int(opponent["initial_trust"]),
                },
            }
        },
    }


def load_scenario(path: str | Path | None = None) -> dict:
    if path is None:
        return make_scenario()
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))
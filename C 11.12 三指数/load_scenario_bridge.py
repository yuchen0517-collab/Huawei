"""成员A 场景加载入口的兼容桥：全项目唯一的 B→C 场景转换实现。

背景
----
成员A 的 `load_scenario.py` 原本自带一套 `convert_b_scenario()`（含
`_convert_numeric` / `_convert_enumerated` / `_weights` / `_goal` /
`_hard_redline`），与 `adapter/scenario_adapter.py` 功能重复且存在实质性缺陷
（枚举效用分忽略 `goals[].target`、无红线时填 ideal、丢弃 `op` 方向、
`terminal_rules` 只映射一个字段等）。

本模块提供与 A 原模块**同名同签名**的入口，`convert_b_scenario` 直接委托
`adapter.adapt_scenario`，不再自行映射任何字段。

`make_scenario()` 保留 A 的“agents.json → ai_governance 场景”逻辑，但把原先
`score: {"cn": 1.0, "us": 1.0}`、`ideal: 50` 这类让所有选项等效的占位分数，
替换为可追溯的常量设计表（见 `_ENUM_CLAUSES` / `_NUMERIC_CLAUSES`），并输出
`SCORES_DERIVED` 结构化 warning 提示“待 B/A 补结构化立场数据”。

所有 warning 都是 `{"code", "field", "message"}` 结构；最近一次的 warning 可通过
`get_last_warnings()` 取回（不写入场景 JSON，避免污染引擎入参）。
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from adapter import adapt_scenario

BASE_DIR = Path(__file__).resolve().parent
AGENTS_PATH = BASE_DIR / "agents.json"
SCENARIO_ID = "ai_governance"
ENGINE_DIR_NAME = "C 11.12 三指数"
CLAUSE_NAMES = (
    "全球算力资源分配",
    "前沿模型评测门槛",
    "数据跨境流动",
)

# 每方每个条款的权重。3 个条款均分，保证 sum(weights) == 1，
# 使 utility() 落在 0~1 区间、Interest 落在 0~100。
CLAUSE_WEIGHT = 1.0 / 3.0

# ---------------------------------------------------------------------------
# ai_governance 场景的常量设计表（人工映射，待 B/A 补结构化立场数据）
#
# 依据 agents.json 中可读到的真实立场字段：
#   _scenario.player.hidden_tasks
#     - “为发展中国家争取不低于 30% 的全球公共算力配额”
#     - “阻止「AI 安全联盟」成为全球标准制定机构”
#   us.hidden_task_card / us.red_lines / us.core_interests_ranked
#     - “推动「AI 安全联盟」成为全球 AI 治理的核心机制”
#     - “确保对中国的 AI 技术限制不被谈判决议削弱”
#     - “绝不接受把标准制定权交给联合国框架下的多数表决机制”
# 这些文本只能支撑“哪一方更偏好哪个选项”，无法给出精确到小数点的效用，
# 因此这里给出的是有序偏好（0.0 ~ 1.0）而非“真实”效用，并通过
# SCORES_DERIVED warning 明确标注。
# ---------------------------------------------------------------------------
_ENUM_CLAUSES = (
    {
        "name": "全球算力资源分配",
        "options": (
            {
                "id": "附带可核查机制",
                "order": 1,
                "score": {"cn": 0.6, "us": 0.8},
            },
            {
                "id": "以既有联盟实践为蓝本设立高风险 AI 出口管制的可核查机制",
                "order": 2,
                "score": {"cn": 0.2, "us": 1.0},
            },
            {
                "id": "接受联合国框架下的技术性通报，但监督机制须具备实际约束力",
                "order": 3,
                "score": {"cn": 1.0, "us": 0.2},
            },
        ),
    },
    {
        "name": "数据跨境流动",
        "options": (
            {
                "id": "白名单互认",
                "order": 1,
                "score": {"cn": 0.6, "us": 0.8},
            },
            {
                "id": "增加对发展中国家的能力建设投入",
                "order": 2,
                "score": {"cn": 1.0, "us": 0.3},
            },
            {
                "id": "在联合国框架下建立对称适用的数据跨境通报机制",
                "order": 3,
                "score": {"cn": 0.8, "us": 0.2},
            },
        ),
    },
)

# 评测门槛：0~100 的百分位量纲。us 主张对高风险模型严管 → 偏好高门槛；
# cn 反对扩大管制 → 偏好低门槛。初始值取双方理想点中点，避免开局偏向任一方。
_NUMERIC_CLAUSES = (
    {
        "name": "前沿模型评测门槛",
        "range": [0, 100],
        "initial": 55,
        "positions": {
            "cn": {"ideal": 40},
            "us": {"ideal": 70},
        },
    },
)

# 设计表中可由 agents.json 直接核对的声明值；其余项无法核对，
# make_scenario() 会逐项记 DESIGN_TABLE_UNVERIFIED。
_DESIGN_TABLE_INDICES = {
    "cn": {"initial_interest": 50, "initial_image": 70, "initial_trust": 65},
    "us": {"initial_interest": 50, "initial_image": 70, "initial_trust": 65},
}

_LAST_WARNINGS: List[dict] = []


def _warning(code: str, field: str, message: str) -> dict:
    return {"code": code, "field": field, "message": message}


def get_last_warnings() -> List[dict]:
    """返回最近一次 `make_scenario()` / `load_scenario()` 产生的结构化 warning。"""
    return [dict(item) for item in _LAST_WARNINGS]


def _set_warnings(items: List[dict]) -> None:
    global _LAST_WARNINGS
    _LAST_WARNINGS = list(items)


def _resolve_engine_root() -> Path:
    """解析引擎源码根目录。

    本模块通常就位于 `C 11.12 三指数/` 内，此时 BASE_DIR 即引擎根；
    若被复制到上层目录（如成员A 的仓库根），再按 A 原来的两个候选路径查找。
    """
    candidates = (
        BASE_DIR,
        BASE_DIR / ENGINE_DIR_NAME,
        BASE_DIR.parent / ENGINE_DIR_NAME,
    )
    for candidate in candidates:
        if (candidate / "engine" / "core.py").is_file():
            return candidate
    raise FileNotFoundError(f"未找到规则引擎源码目录：{ENGINE_DIR_NAME}")


ENGINE_ROOT = _resolve_engine_root()


def _resolve_agents_path() -> Tuple[Path, bool]:
    """返回 (agents.json 路径, 是否回落到 C 侧精简副本)。

    读取顺序：成员A 的完整注册表（`BASE_DIR.parent/agents.json`）优先；
    找不到才回落到本目录的精简副本，并由调用方记 AGENTS_FALLBACK_COPY warning。
    本模块若被复制到 A 的仓库根，`BASE_DIR.parent` 没有注册表，
    此时 `BASE_DIR/agents.json` 就是 A 的完整注册表，不算回落。
    """
    primary = BASE_DIR.parent / "agents.json"
    if primary.is_file():
        return primary, False
    fallback = BASE_DIR.name == ENGINE_DIR_NAME
    return BASE_DIR / "agents.json", fallback


def is_b_scenario(data: Any) -> bool:
    """判断是否为成员B 的场景契约格式（多议题 issues + 双方私有状态）。"""
    return isinstance(data, dict) and "issues" in data and "private_state_by_party" in data


def _alias_party_ids(scenario: dict) -> dict:
    """把适配结果的参与方 id 归一为 A 侧会话约定 cn/us。

    字段翻译全部由 adapter 完成；这里只按 parties 声明顺序重命名 id
    （第一方→cn，第二方→us），因为 A 侧的 index_rules 结算表、api.py
    （MY_ACTOR="cn"）与既有测试都以 cn/us 为口径。已经是 cn/us 时原样返回。
    """
    parties = scenario.get("parties") or []
    ids = [party.get("id") for party in parties if isinstance(party, dict)]
    if len(ids) != 2 or set(ids) == {"cn", "us"}:
        return scenario
    alias = dict(zip(ids, ("cn", "us")))

    def rekey(table: Any) -> Any:
        if not isinstance(table, dict):
            return table
        return {alias.get(key, key): value for key, value in table.items()}

    for party in parties:
        party["id"] = alias[party["id"]]
    for clause in scenario.get("clauses") or []:
        clause["weights"] = rekey(clause.get("weights"))
        clause["positions"] = rekey(clause.get("positions"))
        clause["redlines"] = rekey(clause.get("redlines"))
        clause["soft_redlines"] = rekey(clause.get("soft_redlines"))
        for option in clause.get("options") or []:
            option["score"] = rekey(option.get("score"))
    rules = scenario.get("index_rules") or {}
    for key in ("initial", "sensitivity"):
        if key in rules:
            rules[key] = rekey(rules[key])
    return scenario


def convert_b_scenario(data: dict) -> dict:
    """B 格式 → C 格式。字段翻译唯一实现是 adapter.adapt_scenario；
    本函数只做转发 + 参与方 id 的 cn/us 会话约定归一。"""
    return _alias_party_ids(adapt_scenario(data))


def evaluate_for(engine, viewer: str) -> dict:
    """A 侧对外评价入口：只暴露 viewer 自己的私有信息。

    内部先用 `engine.evaluate()` 取全量六字段，再用 `engine.public_state(viewer)`
    裁剪 `batna_comparison`：非 viewer 方的 `batna` / `net_gain` /
    `better_than_batna` 一律置 None，避免由 `net_gain` 反推对方底牌。
    `engine.evaluate()` 的签名保持原样，本函数是编排层的对外收口。
    """
    if not viewer:
        raise ValueError("viewer 不能为空：对外评价必须指定己方 party_id。")
    evaluation = deepcopy(engine.evaluate())
    public_private = (engine.public_state(viewer) or {}).get(
        "private_state_by_party", {}
    ) or {}
    comparison = evaluation.get("batna_comparison") or {}
    for party, entry in comparison.items():
        if party in public_private:
            continue
        entry["batna"] = None
        entry["net_gain"] = None
        entry["better_than_batna"] = None
    evaluation["batna_comparison"] = comparison
    return evaluation


def _verify_design_table(agents: dict, warnings: List[dict]) -> None:
    """校验常量设计表与 agents.json 的可对齐项，对齐不上的记 DESIGN_TABLE_UNVERIFIED。"""
    scenario_meta = agents.get("_scenario") or {}
    agenda = [
        item for item in (scenario_meta.get("agenda") or []) if isinstance(item, str)
    ]
    player = scenario_meta.get("player") or {}
    opponent = agents.get("us") or {}

    for party, source in (("cn", player), ("us", opponent)):
        for field, expected in _DESIGN_TABLE_INDICES[party].items():
            actual = source.get(field)
            if actual != expected:
                warnings.append(
                    _warning(
                        "DESIGN_TABLE_UNVERIFIED",
                        f"agents.{party}.{field}",
                        f"设计表声明 {party}.{field}={expected!r}，"
                        f"agents.json 实际为 {actual!r}；请以 agents.json 为准并同步常量表。",
                    )
                )

    for design in (*_ENUM_CLAUSES, *_NUMERIC_CLAUSES):
        name = design["name"]
        matched = any(name in item or item in name for item in agenda)
        if not matched:
            warnings.append(
                _warning(
                    "DESIGN_TABLE_UNVERIFIED",
                    f"clauses.{name}",
                    f"设计表条款「{name}」在 agents.json 的 agenda 中找不到对应议题，"
                    "偏好分与理想点均为人工设定，待 A/B 补结构化立场数据。",
                )
            )


def _borrowed_index_rules() -> Tuple[dict, List[dict]]:
    """借用 demo_scenario.json 的整张结算表，并明确记录这是借用。"""
    demo_path = ENGINE_ROOT / "scenarios" / "demo_scenario.json"
    demo = json.loads(demo_path.read_text(encoding="utf-8-sig"))
    rules = deepcopy(demo["index_rules"])
    warnings = [
        _warning(
            "INDEX_RULES_BORROWED",
            "index_rules",
            "agents.json 不含结算表，index_rules 整表借用 scenarios/demo_scenario.json；"
            "改表必须通知成员A 同步。",
        )
    ]
    return rules, warnings


def _make_index_rules(player: dict, opponent: dict) -> Tuple[dict, List[dict]]:
    rules, warnings = _borrowed_index_rules()
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
    return rules, warnings


def _enum_clause(design: dict, warnings: List[dict]) -> dict:
    options = sorted(design["options"], key=lambda item: item["order"])
    initial = options[0]["id"]
    warnings.append(
        _warning(
            "SCORES_DERIVED",
            f"clauses.{design['name']}.options[].score",
            f"条款「{design['name']}」的双方偏好分来自人工映射常量表"
            "（依据 agents.json 的 hidden_task / red_lines / core_interests_ranked），"
            "不是结构化立场数据，待 B/A 补充后替换。",
        )
    )
    return {
        "name": design["name"],
        "type": "enum",
        "initial": initial,
        "options": [
            {
                "id": option["id"],
                "order": option["order"],
                "score": dict(option["score"]),
            }
            for option in options
        ],
        "weights": {"cn": CLAUSE_WEIGHT, "us": CLAUSE_WEIGHT},
    }


def _numeric_clause(design: dict, warnings: List[dict]) -> dict:
    warnings.append(
        _warning(
            "SCORES_DERIVED",
            f"clauses.{design['name']}.positions",
            f"条款「{design['name']}」的双方理想点来自人工映射常量表，"
            "初始值取双方理想点中点，待 B/A 补充后替换。",
        )
    )
    return {
        "name": design["name"],
        "type": "numeric",
        "initial": design["initial"],
        "range": list(design["range"]),
        "positions": deepcopy(design["positions"]),
        "weights": {"cn": CLAUSE_WEIGHT, "us": CLAUSE_WEIGHT},
    }


def make_scenario_with_warnings(
    agents_path: Optional[str | Path] = None,
) -> Tuple[dict, List[dict]]:
    """从 agents.json 组装 ai_governance 场景，并返回结构化 warning 列表。"""
    if agents_path is not None:
        source_path = Path(agents_path)
        agents_fallback = False
    else:
        source_path, agents_fallback = _resolve_agents_path()
    agents = json.loads(source_path.read_text(encoding="utf-8-sig"))
    player = agents["_scenario"]["player"]
    opponent = agents["us"]

    warnings: List[dict] = []
    if agents_fallback:
        warnings.append(
            _warning(
                "AGENTS_FALLBACK_COPY",
                "agents.json",
                "未找到成员A 的完整 agents.json，已回落到 C 侧精简副本；"
                "A 扩展字段时需同步该副本或提供完整注册表。",
            )
        )
    _verify_design_table(agents, warnings)
    # 条款顺序固定跟随 CLAUSE_NAMES（A 侧 API 的 open_issues 等输出以此为口径），
    # 与 _ENUM_CLAUSES / _NUMERIC_CLAUSES 的分组顺序解耦。
    clause_by_name: Dict[str, dict] = {}
    for design in _ENUM_CLAUSES:
        clause = _enum_clause(design, warnings)
        clause_by_name[clause["name"]] = clause
    for design in _NUMERIC_CLAUSES:
        clause = _numeric_clause(design, warnings)
        clause_by_name[clause["name"]] = clause
    clauses: List[dict] = [
        clause_by_name[name] for name in CLAUSE_NAMES if name in clause_by_name
    ]
    index_rules, index_warnings = _make_index_rules(player, opponent)
    warnings.extend(index_warnings)

    scenario = {
        "scenario_id": SCENARIO_ID,
        "parties": [
            {
                "id": "cn",
                "label": player["label"],
                "private": {
                    "hidden_tasks": deepcopy(player.get("hidden_tasks", [])),
                    "strategy": deepcopy(player.get("strategy", {})),
                },
            },
            {
                "id": "us",
                "label": opponent["label"],
                "batna": None,
                "private": {
                    "red_lines": opponent.get("red_lines", ""),
                    "batna": opponent.get("batna", ""),
                    "hidden_task_card": opponent.get("hidden_task_card", ""),
                    "strategy": deepcopy(opponent.get("strategy", {})),
                },
            },
        ],
        "clauses": clauses,
        "action_points_per_round": 5,
        "max_rounds": 12,
        "deadlock_rounds": 2,
        "index_rules": index_rules,
    }
    _set_warnings(warnings)
    return scenario, warnings


def make_scenario(agents_path: Optional[str | Path] = None) -> dict:
    """保留成员A 的签名：只返回场景 dict。warning 用 get_last_warnings() 取。"""
    return make_scenario_with_warnings(agents_path)[0]


def load_scenario(path: Optional[str | Path] = None) -> dict:
    """统一入口。

    - `path is None`：回落 `make_scenario()`（agents.json → ai_governance）；
    - 文件是 B 契约：委托 `adapter.adapt_scenario`；
    - 文件已是 C 场景：原样返回。

    一律用 `utf-8-sig` 读取，兼容成员B 输出的 BOM。
    """
    if path is None:
        return make_scenario()
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if is_b_scenario(data):
        scenario = convert_b_scenario(data)
        _set_warnings([])
        return scenario
    return data
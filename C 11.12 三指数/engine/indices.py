"""三指数结算。

Interest：由条款效用计算，不由发言查表。
Image / Trust：只影响发言方，查表后乘该方敏感度。
模型只提供离散标签；数值由本模块算出并交给 state.apply_index_changes 写入。
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Dict, List, Tuple

from .state import NegotiationState
from .validator import (
    MAGNITUDES,
    clause_map,
    is_number,
    option_value,
    party_ids,
)

FALLBACK_LABELS = {
    "offer": ("constructive_proposal", "conditional_concession"),
    "counter_offer": ("constructive_proposal", "conditional_concession"),
    "conditional_exchange": ("constructive_proposal", "conditional_concession"),
    "final_offer": ("hardline_stance", "hardline_stance"),
    "accept": ("diplomatic_reframe", "keep_promise"),
    "reject": ("hardline_stance", "vague_stance"),
    "walk_away": ("hardline_stance", "betray_ally"),
    "probe": ("procedural", "procedural"),
    "statement": ("procedural", "procedural"),
}

INDEX_NAMES = ("interest", "image", "trust")
INDEX_RULE_TABLES = ("image_actions", "trust_actions")


class IndexRulesShapeError(ValueError):
    """场景 index_rules 非空、但形状不可识别时抛出。

    防静默失效：早期实现查不到表就返回 0，导致 B 契约 1.1 的原生形状
    （13 个标签平铺在顶层）在适配层未转换时被静默忽略，Image / Trust
    永远停在初值且不报错。现在只要表非空且既无 image_actions 也无
    trust_actions，就显式失败。空表（{} 或缺失）仍按「无表则 delta=0」
    处理，以兼容不带结算表的 demo / 老场景。
    """


def _shape_error(rules) -> IndexRulesShapeError:
    keys = sorted(rules.keys()) if isinstance(rules, dict) else type(rules).__name__
    return IndexRulesShapeError(
        "index_rules 形状不可识别：既无 image_actions 也无 trust_actions，"
        f"实际顶层键为 {keys}。请检查场景是否使用了未经适配层转换的 B 1.1 原生表。"
    )


def round_half_up(value: float) -> int:
    """四舍五入（0.5 远离零），避免 Python 银行家舍入在结算边界产生歧义。"""
    if value >= 0:
        return int(math.floor(value + 0.5))
    return int(math.ceil(value - 0.5))


def closeness(value: float, ideal: float, low: float, high: float) -> float:
    """偏离度：1 表示正好命中 ideal，0 表示落在区间端点。

    注意：协议质量与 BATNA 比较**不再**使用本函数。判分必须用「红线锚定」
    （见 `score`），否则踩在自己红线上仍能拿到 0.86 分，BATNA 比较会失真。
    本函数保留给需要「离理想值多远」这类展示型度量的场景。
    """
    span = float(high) - float(low)
    if span <= 0:
        return 1.0 if float(value) == float(ideal) else 0.0
    score = 1.0 - abs(float(value) - float(ideal)) / span
    return max(0.0, min(1.0, score))


def _numeric_direction(position: dict, ideal: float, low: float, high: float) -> str:
    """判定数值议题的偏好方向。

    优先级：场景声明的 `direction`（B 契约 goals[].direction，适配层透传）→
    红线方向 → ideal 相对区间中点。红线方向只在没有显式方向时才作为代理：
    「target 24 + 上限红线 30」是 higher_better，若按红线方向推断会得到
    lower_better，把「越高越好」判反（backup 场景的追溯适用期）。
    """
    direction = position.get("direction")
    if direction in ("higher_better", "lower_better"):
        return direction
    redline_direction = position.get("redline_direction")
    if redline_direction == "below_is_violation":
        return "higher_better"
    if redline_direction == "above_is_violation":
        return "lower_better"
    midpoint = (float(low) + float(high)) / 2.0
    return "higher_better" if float(ideal) >= midpoint else "lower_better"


def score(clause: dict, option, party: str) -> float:
    """统一打分接口，返回 0~1。未知 option 返回 0.0（由校验层报 UNKNOWN_OPTION）。

    数值条款用「红线锚定」：红线（无硬红线时退软红线，再无则退区间端点）为 0，
    目标值为 1，超过目标封顶 1.0。这样「踩红线 = 不谈」，BATNA 比较才有意义；
    旧实现按整个物理区间算 closeness，踩红线（800/1500）仍得 0.857，会得出
    “触碰红线的协议净赚”的错误结论。
    """
    if clause.get("type") == "numeric":
        position = (clause.get("positions") or {}).get(party, {})
        ideal = position.get("ideal", clause.get("initial"))
        low, high = clause.get("range", [0, 0])
        try:
            numeric = float(option)
        except (TypeError, ValueError):
            return 0.0
        if ideal is None:
            return 0.0
        target = float(ideal)
        direction = _numeric_direction(position, target, low, high)
        # 锚点取「该方向上的最差可接受值」：higher_better 从区间下界起算，
        # 只有同向红线下界才抬高锚点；反向红线（例如 higher_better 却设了上限）
        # 不参与锚定，否则会把越高越好判成越低越好。
        redline = position.get("redline")
        redline_direction = position.get("redline_direction")
        if direction == "higher_better":
            anchor = float(low)
            if redline is not None and redline_direction == "below_is_violation":
                anchor = max(anchor, float(redline))
        else:
            anchor = float(high)
            if redline is not None and redline_direction == "above_is_violation":
                anchor = min(anchor, float(redline))
        if target == anchor:
            return 1.0 if numeric == target else 0.0
        if direction == "higher_better":
            raw = (numeric - anchor) / (target - anchor)
        else:
            raw = (anchor - numeric) / (anchor - target)
        return max(0.0, min(1.0, raw))

    for item in clause.get("options", []):
        if item.get("id") == option:
            return float((item.get("score") or {}).get(party, 0.0))
    return 0.0


def initial_plan(scenario: dict) -> Dict[str, dict]:
    return {
        clause["name"]: {
            "option": clause.get("initial"),
            "note": "场景初始方案",
        }
        for clause in scenario.get("clauses", [])
    }


def _plan_option(plan: Dict[str, dict], clause: dict) -> object:
    entry = plan.get(clause["name"])
    if entry is None:
        return clause.get("initial")
    return option_value(entry)


def utility(plan: Dict[str, dict], party: str, scenario: dict) -> float:
    total = 0.0
    for clause in scenario.get("clauses", []):
        weight = float((clause.get("weights") or {}).get(party, 0.0))
        option = _plan_option(plan, clause)
        total += weight * score(clause, option, party)
    return total


def interest_value(plan: Dict[str, dict], party: str, scenario: dict) -> int:
    return round_half_up(utility(plan, party, scenario) * 100.0)


def initial_indices(scenario: dict) -> Dict[str, Dict[str, int]]:
    plan = initial_plan(scenario)
    rules = scenario.get("index_rules", {}) or {}
    initial = (rules.get("initial") if isinstance(rules, dict) else None) or {}
    # 兼容两种形状：
    #   1) 引擎原生（按参与方分层）{"cn": {"image": ..}, "us": {...}}；
    #   2) B 契约 1.1 原生（全场景一个值、双方共用）{"image": .., "trust": ..}。
    # 适配层会展开为形状 1；这里仍兼容形状 2，避免上游绕过适配层时静默回落 50。
    global_initial = (
        initial
        if isinstance(initial, dict)
        and not any(isinstance(initial.get(party), dict) for party in party_ids(scenario))
        else {}
    )
    result: Dict[str, Dict[str, int]] = {}
    for party in party_ids(scenario):
        values = initial.get(party, {}) or {}
        if not isinstance(values, dict):
            values = {}
        merged = dict(global_initial)
        merged.update(values)
        result[party] = {
            "interest": interest_value(plan, party, scenario),
            "image": int(merged.get("image", 50)),
            "trust": int(merged.get("trust", 50)),
        }
    return result


def derive_magnitude(
    action: dict, base_plan: Dict[str, dict], new_plan: Dict[str, dict], scenario: dict
) -> str:
    """路径2：由 action_type 映射标签，由条款实际变动幅度决定档位。"""
    patch = action.get("offer_patch") or {}
    if not patch:
        return "slight"

    clauses = clause_map(scenario)
    action_type = action.get("action_type")
    actor = action.get("actor")
    ratios: List[float] = []

    for name, entry in patch.items():
        clause = clauses.get(name)
        if clause is None:
            continue
        old_entry = base_plan.get(name, {"option": clause.get("initial")})
        old = option_value(old_entry)
        new = entry.get("option")

        if clause.get("type") == "numeric":
            low, high = clause.get("range", [0, 0])
            span = float(high) - float(low)
            try:
                ratio = abs(float(new) - float(old)) / span if span > 0 else 0.0
            except (TypeError, ValueError):
                ratio = 0.0
            if action_type == "final_offer":
                position = (clause.get("positions") or {}).get(actor, {})
                ideal = position.get("ideal", clause.get("initial"))
                far_endpoint = low if abs(float(ideal) - float(high)) >= abs(
                    float(ideal) - float(low)
                ) else high
                if float(new) == float(far_endpoint):
                    ratio = 1.0
        else:
            options = [item["id"] for item in clause.get("options", [])]
            span = len(options) - 1
            if span > 0 and old in options and new in options:
                ratio = abs(options.index(new) - options.index(old)) / span
            else:
                ratio = 0.0
            if action_type == "final_offer" and options:
                lowest = min(
                    options,
                    key=lambda item: score(clause, item, actor),
                )
                if new == lowest:
                    ratio = 1.0

        ratios.append(min(1.0, max(0.0, ratio)))

    ratio = max(ratios) if ratios else 0.0
    if ratio < 0.15:
        return "slight"
    if ratio < 0.45:
        return "moderate"
    return "major"


def resolve_labels(
    action: dict, base_plan: Dict[str, dict], new_plan: Dict[str, dict], scenario: dict
) -> Tuple[List[dict], str]:
    """路径1 优先；没有 effect_labels 时走路径2 兜底。"""
    raw = action.get("effect_labels")
    if raw:
        labels = []
        for item in raw:
            labels.append(
                {
                    "label": item["label"],
                    "magnitude": item["magnitude"],
                    "clause": item.get("clause"),
                    "reason": item.get("reason", ""),
                    "target": "both",
                }
            )
        return labels, "effect_labels"

    action_type = action.get("action_type")
    image_label, trust_label = FALLBACK_LABELS[action_type]
    magnitude = derive_magnitude(action, base_plan, new_plan, scenario)
    return (
        [
            {
                "label": image_label,
                "magnitude": magnitude,
                "clause": None,
                "reason": "由 action_type 与条款变动幅度推导",
                "target": "image",
            },
            {
                "label": trust_label,
                "magnitude": magnitude,
                "clause": None,
                "reason": "由 action_type 与条款变动幅度推导",
                "target": "trust",
            },
        ],
        "fallback",
    )


def _table_delta(
    table: dict,
    sensitivity: dict,
    index: str,
    label: str,
    magnitude: str,
    warnings: List[dict] | None = None,
) -> int:
    entry = table.get(label)
    if entry is None:
        return 0
    if not isinstance(entry, dict):
        if warnings is not None:
            warnings.append(
                {
                    "code": "INDEX_RULE_TABLE_INVALID",
                    "field": f"index_rules.{index}_actions.{label}",
                    "message": f"标签 {label!r} 的结算项不是对象，已按 0 处理。",
                }
            )
        return 0
    if magnitude not in entry:
        if warnings is not None:
            warnings.append(
                {
                    "code": "INDEX_RULE_MAGNITUDE_MISSING",
                    "field": f"index_rules.{index}_actions.{label}.{magnitude}",
                    "message": (
                        f"标签 {label!r} 缺少档位 {magnitude!r}，"
                        "已按 0 处理；请补全 slight/moderate/major 三档。"
                    ),
                }
            )
        return 0
    base = entry.get(magnitude)
    if base is None:
        return 0
    factor = float((sensitivity or {}).get(index, 1.0))
    return round_half_up(float(base) * factor)


def behaviour_delta(
    actor: str,
    item: dict,
    scenario: dict,
    warnings: List[dict] | None = None,
) -> Dict[str, int]:
    """计算一次发言标签对 image / trust 的增量。

    - 结构性自检：`index_rules` 非空但既无 `image_actions` 也无
      `trust_actions` 时抛 `IndexRulesShapeError`，不再静默返回 0；
    - 表为空时保持旧行为（delta=0），兼容不带结算表的场景；
    - 表中有该标签但缺当前档位时，若传入 `warnings` 列表则写入
      结构化 warning `INDEX_RULE_MAGNITUDE_MISSING`，否则按 0 处理
      （默认不传，保持 `apply_effects` 的既有调用与状态结构不变）。
    """
    rules = scenario.get("index_rules", {}) or {}
    if rules and (
        not isinstance(rules, dict)
        or not any(key in rules for key in INDEX_RULE_TABLES)
    ):
        raise _shape_error(rules)

    sensitivity = (rules.get("sensitivity") or {}).get(actor, {}) or {}
    image_table = rules.get("image_actions", {}) or {}
    trust_table = rules.get("trust_actions", {}) or {}

    label = item["label"]
    magnitude = item["magnitude"]
    target = item.get("target", "both")
    deltas = {"image": 0, "trust": 0}

    if target in ("image", "both"):
        deltas["image"] = _table_delta(
            image_table, sensitivity, "image", label, magnitude, warnings
        )
    if target in ("trust", "both"):
        deltas["trust"] = _table_delta(
            trust_table, sensitivity, "trust", label, magnitude, warnings
        )
    return deltas


def apply_effects(
    state: NegotiationState,
    scenario: dict,
    action: dict,
    base_plan: Dict[str, dict],
    new_plan: Dict[str, dict],
) -> Tuple[List[dict], dict]:
    """整批标签先算后写；任何异常都发生在写状态之前。"""
    labels, mode = resolve_labels(action, base_plan, new_plan, scenario)
    actor = action["actor"]

    new_interest = {
        party: interest_value(new_plan, party, scenario)
        for party in party_ids(scenario)
    }

    interest_changes: List[Tuple[str, str, int]] = []
    for party in party_ids(scenario):
        before = int(state.indices[party]["interest"])
        delta = new_interest[party] - before
        if delta != 0:
            interest_changes.append((party, "interest", delta))

    behaviour_total = {"image": 0, "trust": 0}
    for item in labels:
        deltas = behaviour_delta(actor, item, scenario)
        behaviour_total["image"] += deltas["image"]
        behaviour_total["trust"] += deltas["trust"]

    events: List[dict] = []
    action_id = action["action_id"]

    if interest_changes:
        events.extend(
            state.apply_index_changes(
                interest_changes,
                reason="条款效用重算",
                source=action_id,
            )
        )

    if behaviour_total["image"] != 0:
        events.extend(
            state.apply_index_changes(
                [(actor, "image", behaviour_total["image"])],
                reason="发言标签：" + "/".join(
                    f"{item['label']}:{item['magnitude']}" for item in labels
                ),
                source=action_id,
            )
        )
    if behaviour_total["trust"] != 0:
        events.extend(
            state.apply_index_changes(
                [(actor, "trust", behaviour_total["trust"])],
                reason="发言标签：" + "/".join(
                    f"{item['label']}:{item['magnitude']}" for item in labels
                ),
                source=action_id,
            )
        )

    entry = {
        "action_id": action_id,
        "actor": actor,
        "round": int(state.round),
        "action_type": action.get("action_type"),
        "label_mode": mode,
        "labels": deepcopy(labels),
        "deltas": deepcopy(behaviour_total),
        "clause_changes": [
            {
                "clause": name,
                "before": option_value(base_plan.get(name, {})),
                "after": option_value(new_plan.get(name, {})),
            }
            for name in (action.get("offer_patch") or {})
        ],
    }
    state.behavior_log.append(entry)
    return events, entry


def replay_indices(events: List[dict], indices: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
    """纯函数：只消费 index_change 事件，不修改入参。"""
    result = deepcopy(indices)
    for event in events:
        if event.get("type") != "index_change":
            continue
        party = event["party"]
        index = event["index"]
        requested = int(event.get("requested_delta", event.get("delta", 0)))
        bucket = result.setdefault(party, {})
        before = int(bucket.get(index, 0))
        bucket[index] = max(0, min(100, before + requested))
    return result


def clamp_delta(before: int, requested_delta: int) -> int:
    return max(0, min(100, int(before) + int(requested_delta))) - int(before)
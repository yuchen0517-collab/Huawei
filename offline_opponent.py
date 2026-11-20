"""离线对手：不联网也能在**任意场景**里给出合法、且能收敛的报价。

背景
----
旧实现的离线对手是 `neg_cli.OFFLINE_RESPONSES` 里写死的三手 AI 治理报价
（条款名「全球算力资源分配」「数据跨境流动」）。一旦换成芯片 / DST 场景，
引擎直接判 `UNKNOWN_CLAUSE`，`auto_step` 停在 paused，离线演示等于不可用。

本模块改为**从场景本身推导**取值，因此：

- 换场景不用改代码：条款名、取值范围、选项 id、红线全部读场景；
- 生成的取值同时满足**双方**硬红线 —— 这是硬要求：我方 auto 决策只要
  `open_issues` 为空就会 accept，若对手给的方案踩了我方红线，这次 accept
  会被引擎拒绝，整局卡住；
- 分轮推进：第 1 手只谈数值条款，之后逐条补齐，最后我方 accept 收口，
  离线也能看到「报价 → 还价 → 成交」的过程，而不是一手就成交。

原则
----
- 只读公开条款定义（range / step / options / redlines / weights），不碰私有状态；
- 纯函数：同样的场景 + 同一个 cursor 永远得到同一个行动，便于测试与复现；
- 不编造条款：patch 的键只来自场景里真实存在的条款名。

与真模型的关系
--------------
离线对手不是「智能体」，它是**确定性的兜底**，只用于演示链路与测试；
在线模式下对手仍由 `neg.call_with_retry` 走真实模型，本模块不参与。
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

__all__ = [
    "bridge_plan",
    "build_offline_turn",
    "transition_action",
    "auto_speech",
    "ACCEPT_SPEECH",
]

# 枚举条款在同分时的稳定兜底：按选项 id 升序，保证可复现。
_OPTION_ORDER = ("O1", "O2", "O3", "O4", "O5", "O6")

# 过渡卡优先级：与 api.build_auto_action 同一张表，保证两边行为一致。
TRANSITION_PREFERENCE = (
    "public_commitment", "probe_priority", "demand_basis",
    "verify_capacity", "adjourn", "mediation",
)


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _parties(scenario: Mapping[str, Any]) -> list[str]:
    return [
        str(party.get("id"))
        for party in scenario.get("parties") or []
        if isinstance(party, Mapping) and party.get("id")
    ]


# ---------------------------------------------------------------------------
# 数值条款：求双方都能接受的点
# ---------------------------------------------------------------------------
def _numeric_bounds(clause: Mapping[str, Any]) -> tuple[float, float]:
    """取条款自身的允许区间；场景没写 range 时退化成 [-inf, inf] 的可用范围。"""
    span = _as_list(clause.get("range"))
    low = float(span[0]) if len(span) >= 1 else float("-inf")
    high = float(span[1]) if len(span) >= 2 else float("inf")
    return low, high


def _numeric_bridge(clause: Mapping[str, Any]) -> float | None:
    """双方可接受区间的中点，按 step 对齐；无重叠时退回区间中点。

    方向判定与引擎 `validator._numeric_redline_hit` 同口径：
    优先读显式 `redline_direction`，缺省时由 ideal 与 redline 的大小关系推断。
    """
    low, high = _numeric_bounds(clause)
    positions = clause.get("positions") or {}

    for party, position in positions.items():
        if not isinstance(position, Mapping) or "redline" not in position:
            continue
        try:
            redline = float(position["redline"])
        except (TypeError, ValueError):
            continue
        direction = position.get("redline_direction")
        if direction is None:
            try:
                ideal = float(position.get("ideal"))
            except (TypeError, ValueError):
                continue
            direction = "below_is_violation" if ideal > redline else "above_is_violation"
        if direction == "below_is_violation":
            low = max(low, redline)   # 不能低于红线 → 抬高下界
        else:
            high = min(high, redline)  # 不能高于红线 → 压低上界

    if low == float("-inf") and high == float("inf"):
        return None
    if low == float("-inf"):
        low = high
    if high == float("inf"):
        high = low
    if low > high:
        # 没有合作区间：退回条款允许区间中点，让演示仍能推进（终局会判僵局/部分协议）。
        low, high = _numeric_bounds(clause)
        if low == float("-inf") or high == float("inf"):
            return None

    value = (low + high) / 2
    step = clause.get("step")
    if isinstance(step, (int, float)) and step > 0:
        value = low + round((value - low) / float(step)) * float(step)
        value = max(low, min(high, value))

    return int(value) if float(value).is_integer() else round(float(value), 4)


# ---------------------------------------------------------------------------
# 枚举条款：取双方得分之和最高、且不触任何一方红线的选项
# ---------------------------------------------------------------------------
def _enum_bridge(clause: Mapping[str, Any], parties: Iterable[str]) -> str | None:
    options = [opt for opt in _as_list(clause.get("options")) if isinstance(opt, Mapping)]
    if not options:
        return None

    redlines = clause.get("redlines") or {}
    banned: set[str] = set()
    for party in parties:
        banned.update(str(item) for item in _as_list(redlines.get(party)))

    best: tuple[float, float, int, str] | None = None
    for order, option in enumerate(options):
        option_id = option.get("id")
        if option_id is None or str(option_id) in banned:
            continue
        scores = option.get("score") or {}
        values = []
        for party in parties:
            try:
                values.append(float(scores.get(party, 0.0)))
            except (TypeError, ValueError):
                values.append(0.0)
        total = sum(values)
        worst = min(values) if values else 0.0
        # 先比总分，再比「最差一方」的小分，最后按选项原始顺序稳定兜底。
        key = (total, worst, -order, str(option_id))
        if best is None or key > best:
            best = key

    return best[3] if best else None


# ---------------------------------------------------------------------------
# 分轮方案
# ---------------------------------------------------------------------------
def _round_schedule(scenario: Mapping[str, Any]) -> list[list[str]]:
    """把条款切成 3 批：先数值，再逐条补齐。场景只有 1~2 条时自动收缩。"""
    names = [
        str(clause.get("name"))
        for clause in scenario.get("clauses") or []
        if isinstance(clause, Mapping) and clause.get("name")
    ]
    numeric = [
        str(clause.get("name"))
        for clause in scenario.get("clauses") or []
        if isinstance(clause, Mapping) and clause.get("name") and clause.get("type") == "numeric"
    ]
    others = [name for name in names if name not in numeric]

    batches: list[list[str]] = []
    if numeric:
        batches.append(numeric[:1])
        numeric = numeric[1:]
        if numeric:
            batches.append(numeric)
    for name in others:
        batches.append([name])
    return batches or ([names] if names else [])


def _value_for(clause: Mapping[str, Any], parties: list[str]) -> Any:
    if clause.get("type") == "numeric":
        return _numeric_bridge(clause)
    return _enum_bridge(clause, parties)


def _option_label(clause: Mapping[str, Any], option_id: Any) -> str:
    for option in _as_list(clause.get("options")):
        if isinstance(option, Mapping) and option.get("id") == option_id:
            label = option.get("label")
            if label:
                return str(label)
    return str(option_id)


def _describe(scenario: Mapping[str, Any], names: Iterable[str], patch: Mapping[str, dict]) -> str:
    clauses = {
        str(clause.get("name")): clause
        for clause in scenario.get("clauses") or []
        if isinstance(clause, Mapping) and clause.get("name")
    }
    pieces = []
    for name in names:
        clause = clauses.get(name)
        entry = patch.get(name) or {}
        option = entry.get("option")
        if clause is None or option is None:
            continue
        if clause.get("type") == "numeric":
            unit = clause.get("unit") or ""
            pieces.append(f"「{name}」按 {option}{unit}")
        else:
            pieces.append(f"「{name}」采用「{_option_label(clause, option)}」")
    return "；".join(pieces)


def bridge_plan(scenario: Mapping[str, Any], cursor: int = 0) -> dict[str, dict]:
    """离线对手在 `cursor` 这一手要提交的完整（累积）方案。

    返回的是**这一手新提的**条款集合（引擎会把新 patch 合并进该方上一版报价，
    所以早先提过的条款不会丢）。
    """
    parties = _parties(scenario)
    schedule = _round_schedule(scenario)
    if not schedule:
        return {}

    index = min(max(int(cursor), 0), len(schedule) - 1)
    # 累积：前几手的条款也要重提一遍，保证「最新报价」覆盖全部已谈条款。
    names = [name for batch in schedule[: index + 1] for name in batch]

    clauses = {
        str(clause.get("name")): clause
        for clause in scenario.get("clauses") or []
        if isinstance(clause, Mapping) and clause.get("name")
    }

    patch: dict[str, dict] = {}
    for name in names:
        clause = clauses.get(name)
        if clause is None:
            continue
        value = _value_for(clause, parties)
        if value is None:
            continue
        patch[name] = {
            "option": value,
            "note": "离线演示对手按双方红线取可接受值，不调用模型。",
        }
    return patch


def transition_action(
    scenario: Mapping[str, Any],
    state: Any,
    actor: str,
    text: str,
    opponent: str | None = None,
) -> dict | None:
    """挑一张当前可用的过渡卡，构造一个「不表态」的合法行动。

    为什么需要它：规则引擎的响应闭包规定「报价方在对方表态前不得再次改版」。
    我方如果打出一张探询/立场卡（过渡行动），窗口仍然挂在我方身上，此时对手
    若还硬报新价就会被 `SELF_REVISION_LOCKED` 拒掉——旧离线对手正是这么卡死的。
    离线对手应当和真人玩家一样：窗口不在自己手上时，用过渡卡把这一手让过去。
    """
    import negotiation_rules

    registry = negotiation_rules.load_registry()
    specs = {
        str(card.get("id")): card
        for card in registry.get("cards", [])
        if isinstance(card, Mapping) and card.get("id")
    }
    availability = {
        str(card.get("id")): bool(card.get("available"))
        for card in negotiation_rules.available_cards(actor, state, registry)
    }
    for card_id in TRANSITION_PREFERENCE:
        if not availability.get(card_id):
            continue
        spec = specs.get(card_id) or {}
        kind = (spec.get("payload") or {}).get("kind")
        if kind == "probe":
            payload = {"target": opponent or ""}
        elif kind == "procedure":
            payload = {"option": f"{spec.get('name')}：{text}"}
        else:
            payload = {"text": text}
        return {
            "action_type": (spec.get("action_types") or ["statement"])[0],
            "card_id": card_id,
            "card_payload": payload,
        }
    return None


def build_offline_turn(
    scenario: Mapping[str, Any],
    cursor: int = 0,
    state: Any = None,
    actor: str = "us",
) -> dict:
    """构造这一手对手的完整返回（与真模型输出同形，交给同一套校验）。

    返回值故意**不含** `indexes_update` / `speaker_score`：v2 契约里指数与评分
    由规则引擎结算，模型侧不再输出，离线对手也遵守同一契约。

    给了 `state` 时会先看表态窗口：如果对手是报价方而对方还没表态，就改走过渡卡，
    避免被响应闭包判 `SELF_REVISION_LOCKED`（这正是人工打探询卡时会走到的路径）。
    """
    if state is not None:
        import negotiation_rules

        pending = negotiation_rules.pending_response(state, scenario)
        if pending and pending.get("offeror") == actor:
            text = auto_speech(scenario, int(getattr(state, "round", 1) or 1))
            turn = transition_action(scenario, state, actor, text, pending.get("responder"))
            if turn is not None:
                return {
                    "action": {
                        "action_type": turn["action_type"],
                        "card_id": turn["card_id"],
                        "card_payload": turn["card_payload"],
                        "offer_patch": {},
                        "conditions": [],
                        "expected_effect": "在对方表态前先作程序性说明。",
                    },
                    "public_message": (
                        "我方注意到贵方的表态。在贵方给出明确回应前，我方先就程序作出说明，"
                        "暂不调整现有方案的条款取值。"
                    ),
                    "mood": "等待回应",
                    "round_summary": "离线对手在待表态窗口内让出一手，未改版。",
                }

    patch = bridge_plan(scenario, cursor)
    if not patch:
        return {
            "action": {
                "action_type": "statement",
                "offer_patch": {},
                "conditions": [],
                "expected_effect": "本场景没有可自动推导的条款取值，先作原则性表态。",
            },
            "public_message": "我方愿在现有议题上继续磋商，具体条款取值有待进一步评估。",
            "mood": "审慎观望",
            "round_summary": "离线对手未推导出可报的条款取值，本轮仅作表态。",
        }

    action_type = "offer" if cursor == 0 else "counter_offer"
    detail = _describe(scenario, patch.keys(), patch)
    return {
        "action": {
            "action_type": action_type,
            "offer_patch": patch,
            "conditions": [],
            "expected_effect": "以双方红线内可接受的取值缩小分歧。",
            "reason_public": "我方按可核验的取值给出方案，愿意在此基础上继续磋商。",
        },
        "public_message": (
            f"我方就{detail}提出具体安排。这些取值兼顾了双方的安全关切与执行能力，"
            "愿在此基础上继续磋商，并把剩余分歧逐条对表。"
        ),
        "mood": "务实推进",
        "round_summary": f"离线对手就{detail}给出可接受取值。",
    }


# ---------------------------------------------------------------------------
# 我方（自动推演时）的公开话术
# ---------------------------------------------------------------------------
ACCEPT_SPEECH = "我方接受当前协议，确认达成完全一致。"

_SPEECH_TEMPLATES = (
    "我方认为，{first}与{second}是本次磋商的核心，愿在兼顾双方安全关切的前提下寻求可核查的安排。",
    "我方注意到贵方在{first}上的表态。我方主张双方就剩余分歧逐条对表，避免以单边措施替代协商。",
    "我方愿在{first}上展现灵活性，前提是贵方在{second}上给出对等安排。",
)


def auto_speech(scenario: Mapping[str, Any], round_no: int = 1) -> str:
    """我方自动行动时的公开表达：按场景条款名生成，不再念写死的 AI 治理台词。"""
    names = [
        str(clause.get("name"))
        for clause in scenario.get("clauses") or []
        if isinstance(clause, Mapping) and clause.get("name")
    ]
    if not names:
        return "我方愿在本次议题上继续磋商。"
    first = names[(max(int(round_no), 1) - 1) % len(names)]
    second = names[max(int(round_no), 1) % len(names)] if len(names) > 1 else first
    template = _SPEECH_TEMPLATES[(max(int(round_no), 1) - 1) % len(_SPEECH_TEMPLATES)]
    return template.format(first=first, second=second)

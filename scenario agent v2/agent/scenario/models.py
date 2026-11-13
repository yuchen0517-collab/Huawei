"""谈判场景数据模型与业务规则校验（R1-R7）。

只做模型定义与校验；不包含生成逻辑，不调用模型 API。
校验一律返回 Problem 列表，不抛出异常。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import re
from typing import Any, Mapping

SCENARIO_TYPE_VALUES = ("documented", "hypothesis")
ISSUE_TYPE_VALUES = ("numeric", "enumerated")
FACT_TYPE_VALUES = ("立场", "行动", "数字", "引用", "智库")
CONFIDENCE_VALUES = ("A", "B", "C")
DIRECTION_VALUES = ("higher_better", "lower_better", "ranked")
REDLINE_OP_VALUES = ("min", "max", "eq", "in")
VERDICT_VALUES = ("direct", "needs_narrowing", "unsupported")

WEIGHT_TOLERANCE = 0.001
MAX_RANGE_STEPS = 100
MIN_OPTIONS = 3
FLOAT_TOLERANCE = 1e-9

__all__ = [
    "Problem",
    "IssueRange",
    "Option",
    "Issue",
    "Party",
    "FactSource",
    "PublicFact",
    "Assumption",
    "Goal",
    "Redline",
    "Batna",
    "PrivateState",
    "TerminalRules",
    "Negotiability",
    "Scenario",
    "validate_scenario",
]


@dataclass(frozen=True)
class Problem:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass
class IssueRange:
    min: float
    max: float
    step: float


@dataclass
class Option:
    option_id: str
    label: str
    order: int


@dataclass
class Issue:
    issue_id: str
    name: str
    type: str
    unit: str
    range: IssueRange | None = None
    options: list[Option] = field(default_factory=list)
    description: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Issue":
        item = data if isinstance(data, Mapping) else {}
        raw_range = item.get("range")
        return cls(
            issue_id=_text(item.get("issue_id")),
            name=_text(item.get("name")),
            type=_text(item.get("type")),
            unit=_text(item.get("unit")),
            range=IssueRange(
                min=_number_or_zero(raw_range.get("min")),
                max=_number_or_zero(raw_range.get("max")),
                step=_number_or_zero(raw_range.get("step")),
            ) if isinstance(raw_range, Mapping) else None,
            options=[
                Option(
                    option_id=_text(option.get("option_id")),
                    label=_text(option.get("label")),
                    order=_int_or_zero(option.get("order")),
                )
                for option in _dict_list(item.get("options"))
            ],
            description=item.get("description") if isinstance(item.get("description"), str) else None,
        )


@dataclass
class Party:
    party_id: str
    name: str
    role_label: str
    public_position: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Party":
        item = data if isinstance(data, Mapping) else {}
        return cls(
            party_id=_text(item.get("party_id")),
            name=_text(item.get("name")),
            role_label=_text(item.get("role_label")),
            public_position=_text(item.get("public_position")),
        )


@dataclass
class FactSource:
    name: str
    url: str
    published_at: str
    confidence: str


@dataclass
class PublicFact:
    fact_id: str
    text: str
    type: str
    source: FactSource
    applies_to: list[str]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PublicFact":
        item = data if isinstance(data, Mapping) else {}
        raw_source = item.get("source")
        source = raw_source if isinstance(raw_source, Mapping) else {}
        return cls(
            fact_id=_text(item.get("fact_id")),
            text=_text(item.get("text")),
            type=_text(item.get("type")),
            source=FactSource(
                name=_text(source.get("name")),
                url=_text(source.get("url")),
                published_at=_text(source.get("published_at")),
                confidence=_text(source.get("confidence")),
            ),
            applies_to=_str_list(item.get("applies_to")),
        )


@dataclass
class Assumption:
    assumption_id: str
    text: str
    reason: str
    affects: list[str]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Assumption":
        item = data if isinstance(data, Mapping) else {}
        return cls(
            assumption_id=_text(item.get("assumption_id")),
            text=_text(item.get("text")),
            reason=_text(item.get("reason")),
            affects=_str_list(item.get("affects")),
        )


@dataclass
class Goal:
    issue_id: str
    target: float | str
    weight: float
    direction: str


@dataclass
class Redline:
    issue_id: str
    op: str
    value: float | str | list[float | str]
    hard: bool
    reason: str


@dataclass
class Batna:
    utility: float
    description: str
    basis: str


@dataclass
class PrivateState:
    goals: list[Goal] = field(default_factory=list)
    redlines: list[Redline] = field(default_factory=list)
    batna: Batna | None = None
    hidden_task: str = ""
    priority_ranking: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PrivateState":
        item = data if isinstance(data, Mapping) else {}
        raw_batna = item.get("batna")
        return cls(
            goals=[
                Goal(
                    issue_id=_text(goal.get("issue_id")),
                    target=goal.get("target", 0),
                    weight=_number_or_zero(goal.get("weight")),
                    direction=_text(goal.get("direction")),
                )
                for goal in _dict_list(item.get("goals"))
            ],
            redlines=[
                Redline(
                    issue_id=_text(redline.get("issue_id")),
                    op=_text(redline.get("op")),
                    value=redline.get("value", 0),
                    hard=bool(redline.get("hard", False)),
                    reason=_text(redline.get("reason")),
                )
                for redline in _dict_list(item.get("redlines"))
            ],
            batna=Batna(
                utility=_number_or_zero(raw_batna.get("utility")),
                description=_text(raw_batna.get("description")),
                basis=_text(raw_batna.get("basis")),
            ) if isinstance(raw_batna, Mapping) else None,
            hidden_task=_text(item.get("hidden_task")),
            priority_ranking=_str_list(item.get("priority_ranking")),
        )


@dataclass
class TerminalRules:
    allow_walk_away: bool
    accept_requires_no_open_issue: bool
    partial_agreement_allowed: bool

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TerminalRules":
        item = data if isinstance(data, Mapping) else {}
        return cls(
            allow_walk_away=bool(item.get("allow_walk_away", False)),
            accept_requires_no_open_issue=bool(item.get("accept_requires_no_open_issue", False)),
            partial_agreement_allowed=bool(item.get("partial_agreement_allowed", False)),
        )


@dataclass
class Negotiability:
    verdict: str
    zopa_exists: bool
    notes: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Negotiability":
        item = data if isinstance(data, Mapping) else {}
        return cls(
            verdict=_text(item.get("verdict")),
            zopa_exists=bool(item.get("zopa_exists", False)),
            notes=_text(item.get("notes")),
        )


@dataclass
class Scenario:
    scenario_id: str
    title: str
    scenario_type: str
    background: str
    assumptions: list[Assumption] = field(default_factory=list)
    parties: list[Party] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    public_facts: list[PublicFact] = field(default_factory=list)
    private_state_by_party: dict[str, PrivateState] = field(default_factory=dict)
    max_rounds: int = 1
    terminal_rules: TerminalRules | None = None
    negotiability: Negotiability | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Scenario":
        item = data if isinstance(data, Mapping) else {}
        raw_private = item.get("private_state_by_party")
        private_state = {
            key: PrivateState.from_dict(value)
            for key, value in raw_private.items()
            if isinstance(key, str) and isinstance(value, Mapping)
        } if isinstance(raw_private, Mapping) else {}
        raw_terminal = item.get("terminal_rules")
        raw_negotiability = item.get("negotiability")
        return cls(
            scenario_id=_text(item.get("scenario_id")),
            title=_text(item.get("title")),
            scenario_type=_text(item.get("scenario_type")),
            background=_text(item.get("background")),
            assumptions=[Assumption.from_dict(entry) for entry in _dict_list(item.get("assumptions"))],
            parties=[Party.from_dict(entry) for entry in _dict_list(item.get("parties"))],
            issues=[Issue.from_dict(entry) for entry in _dict_list(item.get("issues"))],
            public_facts=[PublicFact.from_dict(entry) for entry in _dict_list(item.get("public_facts"))],
            private_state_by_party=private_state,
            max_rounds=_int_or_zero(item.get("max_rounds")) or 1,
            terminal_rules=TerminalRules.from_dict(raw_terminal) if isinstance(raw_terminal, Mapping) else None,
            negotiability=Negotiability.from_dict(raw_negotiability) if isinstance(raw_negotiability, Mapping) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return float(value)


def _number_or_zero(value: Any) -> float:
    number = _number(value)
    return number if number is not None else 0.0


def _int_or_zero(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _dict_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_mapping(obj: Scenario | Mapping[str, Any]) -> Mapping[str, Any] | None:
    if isinstance(obj, Scenario):
        return asdict(obj)
    if isinstance(obj, Mapping):
        return obj
    return None


def _issue_index(data: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for item in _dict_list(data.get("issues")):
        issue_id = item.get("issue_id")
        if isinstance(issue_id, str) and issue_id not in index:
            index[issue_id] = item
    return index


def _state_index(data: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = data.get("private_state_by_party")
    if not isinstance(raw, Mapping):
        return {}
    return {key: value for key, value in raw.items() if isinstance(key, str) and isinstance(value, Mapping)}


def _option_ids(issue: Mapping[str, Any]) -> set[str]:
    return {
        option_id
        for option in _dict_list(issue.get("options"))
        if isinstance((option_id := option.get("option_id")), str)
    }


def _check_r1_weight_sum(data: Mapping[str, Any]) -> list[Problem]:
    problems: list[Problem] = []
    for party_id, state in _state_index(data).items():
        goals = _dict_list(state.get("goals"))
        total = 0.0
        invalid = 0
        for goal in goals:
            weight = _number(goal.get("weight"))
            if weight is None:
                invalid += 1
            else:
                total += weight
        path = f"private_state_by_party.{party_id}.goals"
        if invalid:
            problems.append(Problem("R1_weight_sum", path, f"有 {invalid} 个 goal 的 weight 不是数值"))
        if goals and abs(total - 1.0) > WEIGHT_TOLERANCE:
            problems.append(Problem("R1_weight_sum", path, f"goals.weight 之和为 {total:.6f}，应为 1（容差 {WEIGHT_TOLERANCE}）"))
    return problems


def _check_r2_target_in_range(data: Mapping[str, Any]) -> list[Problem]:
    problems: list[Problem] = []
    issues = _issue_index(data)
    for party_id, state in _state_index(data).items():
        redlines = _dict_list(state.get("redlines"))
        for goal_index, goal in enumerate(_dict_list(state.get("goals"))):
            issue_id = goal.get("issue_id")
            path = f"private_state_by_party.{party_id}.goals[{goal_index}]"
            issue = issues.get(issue_id) if isinstance(issue_id, str) else None
            if issue is None:
                problems.append(Problem("R2_target_in_range", f"{path}.issue_id", f"issue_id {issue_id!r} 不在 issues 中"))
                continue
            target = goal.get("target")
            if issue.get("type") == "numeric":
                number = _number(target)
                if number is None:
                    problems.append(Problem("R2_target_in_range", f"{path}.target", "numeric 议题的 target 必须是数值"))
                    continue
                raw_range = _mapping(issue.get("range"))
                low = _number(raw_range.get("min"))
                high = _number(raw_range.get("max"))
                if low is None or high is None:
                    problems.append(Problem("R2_target_in_range", f"{path}.target", "议题缺少合法 range，无法判断 target"))
                    continue
                if number < low or number > high:
                    problems.append(Problem("R2_target_in_range", f"{path}.target", f"target {number:g} 超出 range [{low:g}, {high:g}]"))
                for redline_index, redline in enumerate(redlines):
                    if redline.get("issue_id") != issue_id:
                        continue
                    boundary = _number(redline.get("value"))
                    if boundary is not None and math.isclose(boundary, number, rel_tol=0.0, abs_tol=FLOAT_TOLERANCE):
                        problems.append(Problem(
                            "R2_target_in_range",
                            f"{path}.target",
                            f"target {number:g} 等于本方红线边界 {boundary:g}（redlines[{redline_index}]），目标应落在红线内侧",
                        ))
            elif issue.get("type") == "enumerated":
                if not isinstance(target, str):
                    problems.append(Problem("R2_target_in_range", f"{path}.target", "enumerated 议题的 target 必须是 option_id 字符串"))
                    continue
                if target not in _option_ids(issue):
                    problems.append(Problem("R2_target_in_range", f"{path}.target", f"target {target!r} 不是该议题的合法 option_id"))
    return problems


def _check_r3_range_sane(data: Mapping[str, Any]) -> list[Problem]:
    problems: list[Problem] = []
    for issue_index, issue in enumerate(_dict_list(data.get("issues"))):
        base = f"issues[{issue_index}]"
        issue_type = issue.get("type")
        if issue_type == "numeric":
            raw_range = _mapping(issue.get("range"))
            low = _number(raw_range.get("min"))
            high = _number(raw_range.get("max"))
            step = _number(raw_range.get("step"))
            if low is None or high is None or step is None:
                problems.append(Problem("R3_range_sane", f"{base}.range", "numeric 议题必须提供数值型的 min/max/step"))
                continue
            if not low < high:
                problems.append(Problem("R3_range_sane", f"{base}.range", f"min({low:g}) 必须小于 max({high:g})"))
            if step <= 0:
                problems.append(Problem("R3_range_sane", f"{base}.range.step", f"step({step:g}) 必须大于 0"))
            elif low < high and (high - low) / step > MAX_RANGE_STEPS:
                problems.append(Problem(
                    "R3_range_sane",
                    f"{base}.range.step",
                    f"区间跨度 {high - low:g} 除以 step {step:g} 超过 {MAX_RANGE_STEPS} 格",
                ))
        elif issue_type == "enumerated":
            options = _dict_list(issue.get("options"))
            if len(options) < MIN_OPTIONS:
                problems.append(Problem("R3_range_sane", f"{base}.options", f"enumerated 选项数为 {len(options)}，至少要 {MIN_OPTIONS} 个"))
            orders: list[int] = []
            for option_index, option in enumerate(options):
                order = option.get("order")
                if isinstance(order, bool) or not isinstance(order, int):
                    problems.append(Problem("R3_range_sane", f"{base}.options[{option_index}].order", f"order {order!r} 不是整数"))
                else:
                    orders.append(order)
            if orders and len(orders) == len(options) and sorted(orders) != list(range(1, len(options) + 1)):
                problems.append(Problem(
                    "R3_range_sane",
                    f"{base}.options",
                    f"order 必须从 1 开始连续不重复，实际为 {sorted(orders)}",
                ))
    return problems


def _check_r4_redline_consistency(data: Mapping[str, Any]) -> list[Problem]:
    problems: list[Problem] = []
    issues = _issue_index(data)
    for party_id, state in _state_index(data).items():
        for redline_index, redline in enumerate(_dict_list(state.get("redlines"))):
            issue_id = redline.get("issue_id")
            path = f"private_state_by_party.{party_id}.redlines[{redline_index}]"
            issue = issues.get(issue_id) if isinstance(issue_id, str) else None
            if issue is None:
                problems.append(Problem("R4_redline_consistency", f"{path}.issue_id", f"issue_id {issue_id!r} 不在 issues 中"))
                continue
            if issue.get("type") != "enumerated" or redline.get("op") != "in":
                continue
            values = redline.get("value")
            if not isinstance(values, list):
                problems.append(Problem("R4_redline_consistency", f"{path}.value", "op 为 in 时 value 必须是数组"))
                continue
            allowed = _option_ids(issue)
            for value_index, value in enumerate(values):
                if not isinstance(value, str) or value not in allowed:
                    problems.append(Problem(
                        "R4_redline_consistency",
                        f"{path}.value[{value_index}]",
                        f"{value!r} 不是该议题的合法 option_id",
                    ))
    problems.extend(_check_r4_numeric_public_claims(data, issues))
    return problems


_PUBLIC_DIRECTION_PATTERNS = (
    (re.compile(r"(?:不低于|不少于|至少|最低)\s*(\d+(?:\.\d+)?)"), "min"),
    (re.compile(r"(?:不高于|不超过|至多|最高)\s*(\d+(?:\.\d+)?)"), "max"),
)


def _check_r4_numeric_public_claims(
    data: Mapping[str, Any],
    issues: Mapping[str, Mapping[str, Any]],
) -> list[Problem]:
    problems: list[Problem] = []
    parties = {
        party.get("party_id"): party
        for party in _dict_list(data.get("parties"))
        if isinstance(party.get("party_id"), str)
    }
    for party_id, state in _state_index(data).items():
        text = _text(_mapping(parties.get(party_id)).get("public_position"))
        if not text:
            continue
        for issue_id, issue in issues.items():
            if issue.get("type") != "numeric":
                continue
            name = _text(issue.get("name"))
            if not name:
                continue
            name_index = text.find(name)
            if name_index < 0:
                continue
            window = text[name_index:name_index + len(name) + 40]
            redlines = [
                (index, redline)
                for index, redline in enumerate(_dict_list(state.get("redlines")))
                if redline.get("issue_id") == issue_id
            ]
            if not redlines:
                continue
            for pattern, direction in _PUBLIC_DIRECTION_PATTERNS:
                match = pattern.search(window)
                if match is None:
                    continue
                claimed = float(match.group(1))
                for redline_index, redline in redlines:
                    op = redline.get("op")
                    if op not in ("min", "max"):
                        continue
                    boundary = _number(redline.get("value"))
                    path = f"private_state_by_party.{party_id}.redlines[{redline_index}]"
                    if op != direction:
                        problems.append(Problem(
                            "R4_redline_consistency",
                            path,
                            f"公开立场表述为「{match.group(0)}」，与本条红线方向 {op} 不一致",
                        ))
                    elif boundary is None:
                        continue
                    elif direction == "min" and boundary < claimed - FLOAT_TOLERANCE:
                        problems.append(Problem(
                            "R4_redline_consistency",
                            path,
                            f"公开立场承诺不低于 {claimed:g}，但红线 min={boundary:g} 允许更低",
                        ))
                    elif direction == "max" and boundary > claimed + FLOAT_TOLERANCE:
                        problems.append(Problem(
                            "R4_redline_consistency",
                            path,
                            f"公开立场承诺不高于 {claimed:g}，但红线 max={boundary:g} 允许更高",
                        ))
    return problems


def _check_r5_batna_sane(data: Mapping[str, Any]) -> list[Problem]:
    problems: list[Problem] = []
    for party_id, state in _state_index(data).items():
        path = f"private_state_by_party.{party_id}.batna"
        batna = state.get("batna")
        if not isinstance(batna, Mapping):
            problems.append(Problem("R5_batna_sane", path, "缺少 BATNA 对象"))
            continue
        utility = _number(batna.get("utility"))
        if utility is None:
            problems.append(Problem("R5_batna_sane", f"{path}.utility", "utility 必须是数值"))
        elif not 0 < utility < 100:
            problems.append(Problem("R5_batna_sane", f"{path}.utility", f"utility {utility:g} 必须位于开区间 (0, 100)"))
        if not _text(batna.get("description")).strip():
            problems.append(Problem("R5_batna_sane", f"{path}.description", "description 不能为空"))
    return problems


def _check_r6_priority_ranking(data: Mapping[str, Any]) -> list[Problem]:
    problems: list[Problem] = []
    issue_ids = list(_issue_index(data).keys())
    for party_id, state in _state_index(data).items():
        path = f"private_state_by_party.{party_id}.priority_ranking"
        ranking = state.get("priority_ranking")
        if not isinstance(ranking, list):
            problems.append(Problem("R6_priority_ranking", path, "priority_ranking 必须是数组"))
            continue
        seen: list[str] = []
        duplicates: list[str] = []
        for item in ranking:
            if not isinstance(item, str):
                problems.append(Problem("R6_priority_ranking", path, f"包含非字符串项 {item!r}"))
                continue
            if item in seen:
                duplicates.append(item)
            else:
                seen.append(item)
        missing = [issue_id for issue_id in issue_ids if issue_id not in seen]
        unknown = [issue_id for issue_id in seen if issue_id not in issue_ids]
        if duplicates:
            problems.append(Problem("R6_priority_ranking", path, f"存在重复 issue_id：{duplicates}"))
        if missing:
            problems.append(Problem("R6_priority_ranking", path, f"缺少 issue_id：{missing}"))
        if unknown:
            problems.append(Problem("R6_priority_ranking", path, f"包含未知 issue_id：{unknown}"))
    return problems


def _check_r7_every_issue_covered(data: Mapping[str, Any]) -> list[Problem]:
    covered: set[str] = set()
    for state in _state_index(data).values():
        for goal in _dict_list(state.get("goals")):
            issue_id = goal.get("issue_id")
            if isinstance(issue_id, str):
                covered.add(issue_id)
    problems: list[Problem] = []
    for issue_id in _issue_index(data):
        if issue_id not in covered:
            problems.append(Problem("R7_every_issue_covered", f"issues.{issue_id}", f"议题 {issue_id} 没有任何一方的 goal 覆盖"))
    return problems


def _check_r0_required_fields(data: Mapping[str, Any]) -> list[Problem]:
    problems: list[Problem] = []
    for field_name in ("scenario_id", "title", "scenario_type", "background"):
        if field_name not in data:
            problems.append(Problem("R0_required_fields", field_name, f"缺少字段 {field_name}"))
            continue
        value = data.get(field_name)
        if isinstance(value, str) and not value:
            problems.append(Problem("R0_required_fields", field_name, f"{field_name} 不能为空字符串"))
        elif not isinstance(value, str):
            problems.append(Problem(
                "R0_required_fields",
                field_name,
                f"{field_name} 类型应为非空字符串，实际为 {type(value).__name__}",
            ))
    for field_name in ("assumptions", "parties", "issues", "public_facts"):
        if field_name not in data:
            problems.append(Problem("R0_required_fields", field_name, f"缺少字段 {field_name}"))
            continue
        value = data.get(field_name)
        if not isinstance(value, list):
            problems.append(Problem(
                "R0_required_fields",
                field_name,
                f"{field_name} 类型应为 list，实际为 {type(value).__name__}",
            ))
    if "private_state_by_party" not in data:
        problems.append(Problem("R0_required_fields", "private_state_by_party", "缺少字段 private_state_by_party"))
    elif not isinstance(data.get("private_state_by_party"), dict):
        problems.append(Problem(
            "R0_required_fields",
            "private_state_by_party",
            f"private_state_by_party 类型应为 dict，实际为 {type(data.get('private_state_by_party')).__name__}",
        ))
    if "max_rounds" not in data:
        problems.append(Problem("R0_required_fields", "max_rounds", "缺少字段 max_rounds"))
    else:
        value = data.get("max_rounds")
        if isinstance(value, bool) or not isinstance(value, int):
            problems.append(Problem(
                "R0_required_fields",
                "max_rounds",
                f"max_rounds 类型应为 int，实际为 {type(value).__name__}",
            ))
        elif value < 1:
            problems.append(Problem("R0_required_fields", "max_rounds", f"max_rounds 必须 >= 1，实际为 {value}"))
    if "terminal_rules" not in data:
        problems.append(Problem("R0_required_fields", "terminal_rules", "缺少字段 terminal_rules"))
    elif not isinstance(data.get("terminal_rules"), dict):
        problems.append(Problem(
            "R0_required_fields",
            "terminal_rules",
            f"terminal_rules 类型应为 dict，实际为 {type(data.get('terminal_rules')).__name__}",
        ))
    issues = data.get("issues")
    if isinstance(issues, list) and not issues:
        problems.append(Problem("R0_required_fields", "issues", "issues 不能为空"))
    parties = data.get("parties")
    if isinstance(parties, list) and len(parties) < 2:
        problems.append(Problem("R0_required_fields", "parties", f"parties 至少需要 2 个，实际为 {len(parties)} 个"))
    return problems


def _check_r8_enum_values(data: Mapping[str, Any]) -> list[Problem]:
    problems: list[Problem] = []

    def check(path: str, value: Any, allowed: tuple[str, ...]) -> None:
        if value not in allowed:
            problems.append(Problem(
                "R8_enum_values",
                path,
                f"实际值 {value!r} 不在允许值列表 {list(allowed)} 中",
            ))

    if "scenario_type" in data:
        check("scenario_type", data.get("scenario_type"), SCENARIO_TYPE_VALUES)

    raw_issues = data.get("issues")
    if isinstance(raw_issues, list):
        for index, issue in enumerate(raw_issues):
            if isinstance(issue, Mapping) and "type" in issue:
                check(f"issues[{index}].type", issue.get("type"), ISSUE_TYPE_VALUES)

    raw_facts = data.get("public_facts")
    if isinstance(raw_facts, list):
        for index, fact in enumerate(raw_facts):
            if not isinstance(fact, Mapping):
                continue
            if "type" in fact:
                check(f"public_facts[{index}].type", fact.get("type"), FACT_TYPE_VALUES)
            source = fact.get("source")
            if isinstance(source, Mapping) and "confidence" in source:
                check(f"public_facts[{index}].source.confidence", source.get("confidence"), CONFIDENCE_VALUES)

    for party_id, state in _state_index(data).items():
        raw_goals = state.get("goals")
        if isinstance(raw_goals, list):
            for index, goal in enumerate(raw_goals):
                if isinstance(goal, Mapping) and "direction" in goal:
                    check(
                        f"private_state_by_party.{party_id}.goals[{index}].direction",
                        goal.get("direction"),
                        DIRECTION_VALUES,
                    )
        raw_redlines = state.get("redlines")
        if isinstance(raw_redlines, list):
            for index, redline in enumerate(raw_redlines):
                if isinstance(redline, Mapping) and "op" in redline:
                    check(
                        f"private_state_by_party.{party_id}.redlines[{index}].op",
                        redline.get("op"),
                        REDLINE_OP_VALUES,
                    )

    negotiability = data.get("negotiability")
    if isinstance(negotiability, Mapping) and "verdict" in negotiability:
        check("negotiability.verdict", negotiability.get("verdict"), VERDICT_VALUES)

    return problems


_RULES = (
    _check_r0_required_fields,
    _check_r8_enum_values,
    _check_r1_weight_sum,
    _check_r2_target_in_range,
    _check_r3_range_sane,
    _check_r4_redline_consistency,
    _check_r5_batna_sane,
    _check_r6_priority_ranking,
    _check_r7_every_issue_covered,
)


def validate_scenario(obj: Scenario | Mapping[str, Any]) -> list[Problem]:
    data = _as_mapping(obj)
    if data is None:
        return [Problem("E_INPUT", "", "场景必须是 Scenario 对象或 dict")]
    problems: list[Problem] = []
    for rule in _RULES:
        try:
            problems.extend(rule(data))
        except Exception as exc:
            problems.append(Problem("E_INTERNAL", "", f"{rule.__name__} 执行失败：{type(exc).__name__}: {exc}"))
    return problems
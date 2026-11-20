"""成员B 场景契约 → 成员C 引擎场景的单向只读适配层。

设计约束：
- 不改 B 的契约（urn:diplomat:schema:scenario:1.0），不改引擎核心逻辑；
- B 侧字段名一律不改，只在中间层翻译成引擎已冻结的 C 侧格式；
- 转换过程完全确定，不使用随机、时间、UUID、网络或 LLM；
- 所有 warning 都是结构化 dict：{"code", "field", "message"}。
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Dict, List, Tuple

B_REQUIRED_FIELDS = (
    "scenario_id",
    "title",
    "scenario_type",
    "background",
    "assumptions",
    "parties",
    "issues",
    "public_facts",
    "private_state_by_party",
    "max_rounds",
    "terminal_rules",
)

B_SCENARIO_TYPES = ("documented", "hypothesis", "assumption")
B_ISSUE_TYPES = ("numeric", "enumerated")
B_DIRECTIONS = ("higher_better", "lower_better", "ranked")
B_NUMERIC_OPS = ("min", "max")
B_ENUM_OPS = ("in", "not_in")

DEFAULT_DEADLOCK_ROUNDS = 2
DEFAULT_ACTION_POINTS_PER_ROUND = 3

# B 契约 1.1 的 13 个行为标签与三档幅度；与 engine/validator.py 的
# LABELS / MAGNITUDES 完全一致。适配层不 import 引擎，故在此复述一份，
# tests/test_index_rules_v1.py 有守卫测试防止两处漂移。
INDEX_RULE_LABELS = (
    "constructive_proposal",
    "cite_rules",
    "hardline_stance",
    "broken_promise",
    "personal_attack",
    "redline_provoke",
    "procedural",
    "diplomatic_reframe",
    "protect_ally",
    "keep_promise",
    "betray_ally",
    "vague_stance",
    "conditional_concession",
)
INDEX_RULE_MAGNITUDES = ("slight", "moderate", "major")
INDEX_RULE_ENGINE_KEYS = frozenset(
    {"scale", "initial", "sensitivity", "image_actions", "trust_actions"}
)

# 默认查表：口径与 scenarios/demo_scenario.json 的 index_rules 完全一致。
# 结算表的唯一源头是 demo_scenario.json；改表时必须同步本常量，
# tests/test_adapter.py 中有一条守卫测试防止漂移。
# 仅在输入场景未自带 index_rules 时注入；上游若已补整表则原样保留。
DEFAULT_INDEX_RULES = {
    "scale": [0, 100],
    "initial": {
        "cn": {"image": 60, "trust": 45},
        "us": {"image": 55, "trust": 40},
    },
    "sensitivity": {
        "cn": {"image": 0.9, "trust": 1.2},
        "us": {"image": 1.1, "trust": 0.9},
    },
    "image_actions": {
        "constructive_proposal": {"slight": 2, "moderate": 3, "major": 5},
        "cite_rules": {"slight": 1, "moderate": 2, "major": 3},
        "hardline_stance": {"slight": -1, "moderate": -2, "major": -3},
        "broken_promise": {"slight": -5, "moderate": -6, "major": -8},
        "personal_attack": {"slight": -5, "moderate": -7, "major": -10},
        "redline_provoke": {"slight": -3, "moderate": -4, "major": -5},
        "procedural": {"slight": 0, "moderate": 0, "major": 1},
        "diplomatic_reframe": {"slight": 3, "moderate": 4, "major": 5},
        "protect_ally": {"slight": 1, "moderate": 2, "major": 3},
        "keep_promise": {"slight": 1, "moderate": 2, "major": 3},
        "betray_ally": {"slight": -4, "moderate": -5, "major": -7},
        "vague_stance": {"slight": -1, "moderate": -2, "major": -3},
        "conditional_concession": {"slight": 0, "moderate": 1, "major": 2},
    },
    "trust_actions": {
        "constructive_proposal": {"slight": 1, "moderate": 2, "major": 3},
        "cite_rules": {"slight": 1, "moderate": 2, "major": 3},
        "hardline_stance": {"slight": 2, "moderate": 3, "major": 4},
        "broken_promise": {"slight": -5, "moderate": -6, "major": -8},
        "personal_attack": {"slight": -4, "moderate": -6, "major": -8},
        "redline_provoke": {"slight": -1, "moderate": -2, "major": -2},
        "procedural": {"slight": 0, "moderate": 0, "major": 1},
        "diplomatic_reframe": {"slight": 2, "moderate": 3, "major": 4},
        "protect_ally": {"slight": 3, "moderate": 4, "major": 6},
        "keep_promise": {"slight": 2, "moderate": 3, "major": 4},
        "betray_ally": {"slight": -5, "moderate": -7, "major": -10},
        "vague_stance": {"slight": -2, "moderate": -3, "major": -4},
        "conditional_concession": {"slight": 0, "moderate": 0, "major": 1},
    },
}


class ScenarioContractError(Exception):
    """B 侧场景不满足冻结契约时抛出，消息包含字段路径与期望值。"""


def _warning(code: str, field: str, message: str) -> dict:
    return {"code": code, "field": field, "message": message}


def _delta_value(band: dict, key: str, warnings: List[dict], field: str) -> int:
    """取一个行为增量；缺失按 0，非数值记 warning 并按 0。"""
    if key not in band:
        return 0
    value = band[key]
    if not _is_number(value):
        warnings.append(
            _warning(
                "INDEX_RULE_DELTA_INVALID",
                field,
                f"{key} 必须为数值，实际为 {value!r}，已按 0 处理。",
            )
        )
        return 0
    return int(value)


def _normalize_index_rules(
    raw: dict, party_ids: List[str]
) -> Tuple[dict, List[dict]]:
    """把 B 契约 1.1 的 index_rules 无损转换为引擎可读形状。

    B 1.1 形状（13 个标签平铺在顶层，每档含 interest_delta / image_delta /
    trust_delta）与引擎期望形状（image_actions / trust_actions 两张表）不同，
    而适配层对 index_rules 是「自带则原样保留」，若不转换会导致 image/trust
    静默归零。本函数只做结构搬移，不改变任何数值语义：

    - image_actions[label][magnitude] = raw[label][magnitude]["image_delta"]
    - trust_actions[label][magnitude] = raw[label][magnitude]["trust_delta"]
    - initial：B 是全局 {image, trust}，展开到每个参与方；已分层则原样保留
    - scale：B 无此键，补 [0, 100]
    - sensitivity：B 无此键，**不编造**，省略并按 1.0 等权处理 + warning
    - interest_delta：引擎无落点，忽略并记 INTEREST_DELTA_UNSUPPORTED

    输入若已是引擎原生形状（含 image_actions / trust_actions），原样深拷贝返回。
    """
    warnings: List[dict] = []

    if not isinstance(raw, dict) or not raw:
        return deepcopy(DEFAULT_INDEX_RULES), warnings

    # 1) 已是引擎原生形状：原样保留，不再改任何数值。
    if any(key in raw for key in ("image_actions", "trust_actions")):
        warnings.append(
            _warning(
                "INDEX_RULES_ALREADY_NATIVE",
                "$.index_rules",
                "输入 index_rules 已是引擎原生形状（含 image_actions / trust_actions），"
                "适配层原样保留。",
            )
        )
        return deepcopy(raw), warnings

    # 2) 形状不可识别：非空但既不是引擎形状，也没有任何 B 1.1 标签。
    if not any(label in raw for label in INDEX_RULE_LABELS) and "initial" not in raw:
        raise ScenarioContractError(
            "$.index_rules: 形状不可识别：既无 image_actions / trust_actions，"
            f"也不含 B 契约 1.1 的 13 个行为标签，实际顶层键为 {sorted(raw)}。"
        )

    image_actions: Dict[str, Dict[str, int]] = {}
    trust_actions: Dict[str, Dict[str, int]] = {}
    interest_ignored: List[str] = []

    for label in INDEX_RULE_LABELS:
        entry = raw.get(label)
        if not isinstance(entry, dict):
            warnings.append(
                _warning(
                    "INDEX_RULE_LABEL_MISSING",
                    f"$.index_rules.{label}",
                    f"B 1.1 结算表缺少标签 {label!r}，已补全三档为 0。",
                )
            )
            entry = {}

        image_actions[label] = {}
        trust_actions[label] = {}
        for magnitude in INDEX_RULE_MAGNITUDES:
            band = entry.get(magnitude)
            if not isinstance(band, dict):
                image_actions[label][magnitude] = 0
                trust_actions[label][magnitude] = 0
                continue
            image_actions[label][magnitude] = _delta_value(
                band,
                "image_delta",
                warnings,
                f"$.index_rules.{label}.{magnitude}.image_delta",
            )
            trust_actions[label][magnitude] = _delta_value(
                band,
                "trust_delta",
                warnings,
                f"$.index_rules.{label}.{magnitude}.trust_delta",
            )
            if "interest_delta" in band:
                interest_ignored.append(f"{label}.{magnitude}")

    if interest_ignored:
        warnings.append(
            _warning(
                "INTEREST_DELTA_UNSUPPORTED",
                "$.index_rules.*.*.interest_delta",
                "引擎的 interest 由条款效用计算，行为标签没有 interest 结算通道；"
                f"已忽略 {len(interest_ignored)} 个 interest_delta（待与 B / 队长裁决，"
                "见 docs/INDEX_RULES_V1_GAP.md）。",
            )
        )

    # 3) 未知顶层键：忽略并记 warning，保持加法兼容（不抛错）。
    for key in raw:
        if key not in INDEX_RULE_LABELS and key not in INDEX_RULE_ENGINE_KEYS:
            warnings.append(
                _warning(
                    "INDEX_RULE_LABEL_UNKNOWN",
                    f"$.index_rules.{key}",
                    f"未知的行为标签 {key!r}，不在 13 个合法标签内，已忽略。",
                )
            )

    # 4) initial：全局值展开到每个参与方；已是分层形状则原样保留。
    raw_initial = raw.get("initial")
    raw_initial = raw_initial if isinstance(raw_initial, dict) else {}
    layered = any(
        isinstance(raw_initial.get(party), dict) for party in party_ids
    )
    initial: Dict[str, Dict[str, int]] = {}
    for party in party_ids:
        if layered:
            values = raw_initial.get(party) or {}
            if not isinstance(values, dict):
                values = {}
        else:
            values = raw_initial
        initial[party] = {
            "image": int(values.get("image", 50)),
            "trust": int(values.get("trust", 50)),
        }

    # 5) scale：B 无此键，补引擎默认量纲。
    raw_scale = raw.get("scale")
    if (
        isinstance(raw_scale, list)
        and len(raw_scale) == 2
        and all(_is_number(item) for item in raw_scale)
    ):
        scale = list(raw_scale)
    else:
        scale = [0, 100]

    rules: Dict[str, object] = {
        "scale": scale,
        "initial": initial,
        "image_actions": image_actions,
        "trust_actions": trust_actions,
    }

    # 6) sensitivity：B 1.1 未提供，不编造；省略该键等价于全体 1.0 敏感度。
    raw_sensitivity = raw.get("sensitivity")
    if isinstance(raw_sensitivity, dict) and raw_sensitivity:
        rules["sensitivity"] = deepcopy(raw_sensitivity)
    else:
        warnings.append(
            _warning(
                "SENSITIVITY_ABSENT",
                "$.index_rules.sensitivity",
                "B 契约 1.1 未提供参与方敏感度，引擎按 1.0 处理（各方等权）。",
            )
        )

    return rules, warnings


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _normalized_private_state(raw) -> dict:
    """private_state_by_party 的键按小写归一。

    parties[].party_id 在本层一律小写归一（见 validate_b_contract），
    但 B 的交付文件可能使用 P1/P2 等大写 id 作为私有状态的键；
    不归一时校验与映射会漏配。重复键（大小写不同）保留先出现者。
    """
    normalized: Dict[str, object] = {}
    for key, value in _as_dict(raw).items():
        if isinstance(key, str):
            normalized.setdefault(key.lower(), value)
    return normalized


def validate_b_contract(b_scenario) -> List[str]:
    """校验 B 侧必填字段与枚举合法性，返回错误列表（不抛异常）。"""
    errors: List[str] = []
    if not isinstance(b_scenario, dict):
        return ["$: 场景必须是 JSON 对象。"]

    for name in B_REQUIRED_FIELDS:
        if name not in b_scenario:
            errors.append(f"$.{name}: 缺少必填字段。")

    for name in ("scenario_id", "title", "background"):
        if name in b_scenario and not _require_text(b_scenario[name]):
            errors.append(f"$.{name}: 必须是非空字符串。")

    scenario_type = b_scenario.get("scenario_type")
    if "scenario_type" in b_scenario and scenario_type not in B_SCENARIO_TYPES:
        errors.append(
            "$.scenario_type: 期望 documented/hypothesis/assumption 之一，"
            f"实际为 {scenario_type!r}。"
        )

    for name in ("assumptions", "public_facts"):
        if name in b_scenario and not isinstance(b_scenario[name], list):
            errors.append(f"$.{name}: 必须是数组。")

    max_rounds = b_scenario.get("max_rounds")
    if "max_rounds" in b_scenario and (
        not isinstance(max_rounds, int)
        or isinstance(max_rounds, bool)
        or max_rounds < 1
    ):
        errors.append("$.max_rounds: 必须是 >=1 的整数。")

    terminal_rules = b_scenario.get("terminal_rules")
    if "terminal_rules" in b_scenario and not isinstance(terminal_rules, dict):
        errors.append("$.terminal_rules: 必须是对象。")
    elif isinstance(terminal_rules, dict):
        # B 契约 1.1 冻结语义：三个布尔只接受 JSON true/false，缺失或非布尔
        # 一律视为契约错误，引擎不得用 bool() 兜底。
        for key in ("allow_walk_away", "partial_agreement_allowed"):
            if key not in terminal_rules:
                errors.append(
                    f"$.terminal_rules.{key}: 缺少必填布尔（B 契约 1.1 要求必填）。"
                )
        if (
            "accept_requires_no_open_issue" not in terminal_rules
            and "accept_requires_no_open_issues" not in terminal_rules
        ):
            errors.append(
                "$.terminal_rules.accept_requires_no_open_issue: "
                "缺少必填布尔（B 契约 1.1 要求必填；复数兼容键亦可）。"
            )
        # B 契约用单数 accept_requires_no_open_issue，C 场景用复数。
        # 两者都接受，单数优先；同时出现且取值冲突视为契约错误。
        for key in (
            "allow_walk_away",
            "accept_requires_no_open_issue",
            "accept_requires_no_open_issues",
            "partial_agreement_allowed",
        ):
            if key in terminal_rules and not isinstance(terminal_rules[key], bool):
                errors.append(f"$.terminal_rules.{key}: 必须是布尔值。")
        singular = terminal_rules.get("accept_requires_no_open_issue")
        plural = terminal_rules.get("accept_requires_no_open_issues")
        if singular is not None and plural is not None and singular != plural:
            errors.append(
                "$.terminal_rules: accept_requires_no_open_issue 与 "
                "accept_requires_no_open_issues 同时出现且取值冲突。"
            )

        # deadlock_rounds 位于 terminal_rules 内部（B 1.1），而非顶层。
        if "deadlock_rounds" in terminal_rules:
            deadlock = terminal_rules["deadlock_rounds"]
            if (
                not isinstance(deadlock, int)
                or isinstance(deadlock, bool)
                or deadlock < 2
                or deadlock > 10
            ):
                errors.append(
                    "$.terminal_rules.deadlock_rounds: 期望 2~10 的整数，"
                    f"实际为 {deadlock!r}。"
                )
            elif (
                isinstance(max_rounds, int)
                and not isinstance(max_rounds, bool)
                and deadlock > max_rounds
            ):
                errors.append(
                    "$.terminal_rules.deadlock_rounds: 不得大于 max_rounds="
                    f"{max_rounds}，实际为 {deadlock}。"
                )

    # runtime 块：其中字段都必须被引擎显式读取，禁止在适配层写死。
    if "runtime" in b_scenario:
        runtime = b_scenario["runtime"]
        if not isinstance(runtime, dict):
            errors.append("$.runtime: 必须是对象。")
        else:
            for key in runtime:
                if key != "action_points_per_round":
                    errors.append(f"$.runtime.{key}: 未定义的运行参数。")
            if "action_points_per_round" in runtime:
                points = runtime["action_points_per_round"]
                if (
                    not isinstance(points, int)
                    or isinstance(points, bool)
                    or points < 1
                    or points > 5
                ):
                    errors.append(
                        "$.runtime.action_points_per_round: 期望 1~5 的整数，"
                        f"实际为 {points!r}。"
                    )

    parties = b_scenario.get("parties")
    party_ids: List[str] = []
    if "parties" in b_scenario:
        if not isinstance(parties, list) or not parties:
            errors.append("$.parties: 必须是非空数组。")
        else:
            seen = set()
            for position, party in enumerate(parties):
                path = f"$.parties[{position}]"
                if not isinstance(party, dict):
                    errors.append(f"{path}: 必须是对象。")
                    continue
                party_id = party.get("party_id")
                if not _require_text(party_id):
                    errors.append(f"{path}.party_id: 必须是非空字符串。")
                else:
                    normalized = party_id.lower()
                    if normalized in seen:
                        errors.append(f"{path}.party_id: 与前面的参与方重复。")
                    seen.add(normalized)
                    party_ids.append(normalized)
                if "name" in party and not _require_text(party["name"]):
                    errors.append(f"{path}.name: 必须是非空字符串。")

    issues = b_scenario.get("issues")
    issue_map: Dict[str, dict] = {}
    if "issues" in b_scenario:
        if not isinstance(issues, list) or not issues:
            errors.append("$.issues: 必须是非空数组。")
        else:
            names = set()
            for position, issue in enumerate(issues):
                path = f"$.issues[{position}]"
                if not isinstance(issue, dict):
                    errors.append(f"{path}: 必须是对象。")
                    continue
                issue_id = issue.get("issue_id")
                if not _require_text(issue_id):
                    errors.append(f"{path}.issue_id: 必须是非空字符串。")
                else:
                    issue_map[issue_id] = issue
                name = issue.get("name")
                if not _require_text(name):
                    errors.append(f"{path}.name: 必须是非空字符串。")
                elif name in names:
                    errors.append(
                        f"{path}.name: 条款名 {name!r} 在同一场景内重复，引擎以 name 为键。"
                    )
                else:
                    names.add(name)

                issue_type = issue.get("type")
                if issue_type not in B_ISSUE_TYPES:
                    errors.append(
                        f"{path}.type: 期望 numeric/enumerated 之一，"
                        f"实际为 {issue_type!r}。"
                    )
                elif issue_type == "numeric":
                    range_value = issue.get("range")
                    if not isinstance(range_value, dict):
                        errors.append(f"{path}.range: 必须是包含 min/max 的对象。")
                    else:
                        low = range_value.get("min")
                        high = range_value.get("max")
                        if not _is_number(low) or not _is_number(high):
                            errors.append(f"{path}.range: min/max 必须是数值。")
                        elif float(low) >= float(high):
                            errors.append(f"{path}.range: 期望 min < max。")
                        else:
                            step = range_value.get("step")
                            if step is not None and (
                                not _is_number(step) or float(step) <= 0
                            ):
                                errors.append(
                                    f"{path}.range.step: 必须是正数，实际为 {step!r}。"
                                )
                            elif "initial" in issue:
                                initial = issue["initial"]
                                if not _is_number(initial):
                                    errors.append(
                                        f"{path}.initial: 数值议题的初始值必须是数值。"
                                    )
                                elif float(initial) < float(low) or float(
                                    initial
                                ) > float(high):
                                    errors.append(
                                        f"{path}.initial: 初始值 {initial!r} "
                                        f"不在 [{low}, {high}] 内。"
                                    )
                                elif step is not None:
                                    ratio = (
                                        float(initial) - float(low)
                                    ) / float(step)
                                    if abs(ratio - round(ratio)) > 1e-9:
                                        errors.append(
                                            f"{path}.initial: 初始值 {initial!r} 不是 "
                                            f"step={step} 的整数倍"
                                            f"（(value-min)/step={ratio!r}）。"
                                        )
                else:
                    options = issue.get("options")
                    if not isinstance(options, list) or not options:
                        errors.append(f"{path}.options: 必须是非空数组。")
                    else:
                        option_ids = set()
                        orders = set()
                        for option_position, option in enumerate(options):
                            option_path = f"{path}.options[{option_position}]"
                            if not isinstance(option, dict):
                                errors.append(f"{option_path}: 必须是对象。")
                                continue
                            option_id = option.get("option_id")
                            if not _require_text(option_id):
                                errors.append(
                                    f"{option_path}.option_id: 必须是非空字符串。"
                                )
                            elif option_id in option_ids:
                                errors.append(
                                    f"{option_path}.option_id: 与前面的选项重复。"
                                )
                            else:
                                option_ids.add(option_id)
                            order = option.get("order")
                            if not isinstance(order, int) or isinstance(order, bool):
                                errors.append(f"{option_path}.order: 必须是整数。")
                            elif order in orders:
                                errors.append(
                                    f"{option_path}.order: 排序号重复，无法推导初始值。"
                                )
                            else:
                                orders.add(order)
                        if "initial" in issue:
                            initial = issue["initial"]
                            if not _require_text(initial) or initial not in option_ids:
                                errors.append(
                                    f"{path}.initial: 初始值必须是该议题的 option_id 之一，"
                                    f"实际为 {initial!r}。"
                                )

                # initial_ref：可选；填写时必须能在同场景的 public_facts[].fact_id
                # 或 assumptions[].assumption_id 中解析到。
                if "initial_ref" in issue:
                    ref = issue["initial_ref"]
                    if not _require_text(ref):
                        errors.append(
                            f"{path}.initial_ref: 必须是非空字符串，实际为 {ref!r}。"
                        )
                    else:
                        resolvable = set()
                        for fact in _as_list(b_scenario.get("public_facts")):
                            if isinstance(fact, dict) and _require_text(
                                fact.get("fact_id")
                            ):
                                resolvable.add(fact["fact_id"])
                        for assumption in _as_list(b_scenario.get("assumptions")):
                            if isinstance(assumption, dict) and _require_text(
                                assumption.get("assumption_id")
                            ):
                                resolvable.add(assumption["assumption_id"])
                        if ref not in resolvable:
                            errors.append(
                                f"{path}.initial_ref: 无法在 public_facts[].fact_id "
                                f"或 assumptions[].assumption_id 中解析到 {ref!r}。"
                            )

    private_state = b_scenario.get("private_state_by_party")
    if "private_state_by_party" in b_scenario:
        if not isinstance(private_state, dict):
            errors.append("$.private_state_by_party: 必须是对象。")
        else:
            private_state = _normalized_private_state(private_state)
            for party_id in party_ids:
                path = f"$.private_state_by_party.{party_id}"
                if party_id not in private_state:
                    errors.append(f"{path}: 缺少该参与方的私有状态。")
                    continue
                entry = private_state[party_id]
                if not isinstance(entry, dict):
                    errors.append(f"{path}: 必须是对象。")
                    continue
                goals = entry.get("goals")
                if not isinstance(goals, list):
                    errors.append(f"{path}.goals: 必须是数组。")
                    continue
                for goal_position, goal in enumerate(goals):
                    goal_path = f"{path}.goals[{goal_position}]"
                    if not isinstance(goal, dict):
                        errors.append(f"{goal_path}: 必须是对象。")
                        continue
                    issue_id = goal.get("issue_id")
                    if issue_id not in issue_map:
                        errors.append(
                            f"{goal_path}.issue_id: 引用了不存在的议题 {issue_id!r}。"
                        )
                        continue
                    weight = goal.get("weight")
                    if not _is_number(weight):
                        errors.append(f"{goal_path}.weight: 必须是数值。")
                    direction = goal.get("direction")
                    if direction not in B_DIRECTIONS:
                        errors.append(
                            f"{goal_path}.direction: 期望 higher_better/"
                            f"lower_better/ranked 之一，实际为 {direction!r}。"
                        )
                        continue
                    issue = issue_map[issue_id]
                    if issue.get("type") == "numeric" and direction == "ranked":
                        errors.append(
                            f"{goal_path}.direction: 数值议题不能使用 ranked。"
                        )
                    if issue.get("type") == "enumerated" and direction != "ranked":
                        errors.append(
                            f"{goal_path}.direction: 枚举议题必须使用 ranked。"
                        )
                    if "target" not in goal:
                        errors.append(f"{goal_path}.target: 缺少目标值。")
                    elif direction == "ranked":
                        allowed = {
                            option.get("option_id")
                            for option in _as_list(issue.get("options"))
                            if isinstance(option, dict)
                        }
                        if goal["target"] not in allowed:
                            errors.append(
                                f"{goal_path}.target: {goal['target']!r} "
                                "不是该枚举议题的 option_id。"
                            )
                    elif not _is_number(goal["target"]):
                        errors.append(f"{goal_path}.target: 数值议题的目标必须是数值。")

                redlines = entry.get("redlines")
                if redlines is not None and not isinstance(redlines, list):
                    errors.append(f"{path}.redlines: 必须是数组。")
                    continue
                for redline_position, redline in enumerate(_as_list(redlines)):
                    redline_path = f"{path}.redlines[{redline_position}]"
                    if not isinstance(redline, dict):
                        errors.append(f"{redline_path}: 必须是对象。")
                        continue
                    issue_id = redline.get("issue_id")
                    if issue_id not in issue_map:
                        errors.append(
                            f"{redline_path}.issue_id: 引用了不存在的议题 {issue_id!r}。"
                        )
                        continue
                    issue_type = issue_map[issue_id].get("type")
                    op = redline.get("op")
                    if issue_type == "numeric" and op not in B_NUMERIC_OPS:
                        errors.append(
                            f"{redline_path}.op: 数值议题期望 min/max，"
                            f"实际为 {op!r}。"
                        )
                    elif issue_type == "enumerated" and op not in B_ENUM_OPS:
                        errors.append(
                            f"{redline_path}.op: 枚举议题期望 in/not_in，"
                            f"实际为 {op!r}。"
                        )
                    if "value" not in redline:
                        errors.append(f"{redline_path}.value: 缺少红线取值。")
                    elif issue_type == "numeric" and not _is_number(redline["value"]):
                        errors.append(f"{redline_path}.value: 数值红线必须是数值。")
                    elif issue_type == "enumerated" and not isinstance(
                        redline.get("value"), list
                    ):
                        errors.append(f"{redline_path}.value: 枚举红线必须是数组。")
                    if "hard" in redline and not isinstance(redline["hard"], bool):
                        errors.append(f"{redline_path}.hard: 必须是布尔值。")

    return errors


def _assumption_text(item) -> str:
    if isinstance(item, dict):
        text = item.get("text", "")
        assumption_id = item.get("assumption_id")
        if assumption_id:
            return f"[{assumption_id}] {text}"
        return text
    return str(item)


def _party_goals(private_entry: dict) -> Dict[str, dict]:
    goals = {}
    for goal in _as_list(private_entry.get("goals")):
        if isinstance(goal, dict) and isinstance(goal.get("issue_id"), str):
            goals[goal["issue_id"]] = goal
    return goals


def _ranked_scores(option_ids: List[str], target: str) -> Dict[str, float]:
    """以 target 为 1.0，其余按 order 位次差线性衰减，步长 1/(n-1)。"""
    count = len(option_ids)
    if count <= 1:
        return {option_id: 1.0 for option_id in option_ids}
    target_index = option_ids.index(target)
    step = 1.0 / (count - 1)
    return {
        option_id: max(0.0, 1.0 - abs(index - target_index) * step)
        for index, option_id in enumerate(option_ids)
    }



def _enum_redlines(
    redline_items: List[dict], option_ids: List[str]
) -> Tuple[List[str], List[str]]:
    hard: List[str] = []
    soft: List[str] = []
    for item in redline_items:
        op = item.get("op")
        value = item.get("value")
        if op == "in":
            allowed = set(value or [])
            targets = [option_id for option_id in option_ids if option_id not in allowed]
        elif op == "not_in":
            targets = [option_id for option_id in value or [] if option_id in option_ids]
        else:
            continue
        bucket = hard if item.get("hard", True) is not False else soft
        for option_id in targets:
            if option_id not in bucket:
                bucket.append(option_id)
    return hard, soft


def _adapt_enum_clause(
    issue: dict,
    party_ids: List[str],
    private_state: dict,
    raw_weights: Dict[str, Dict[str, float]],
    warnings: List[dict],
) -> dict:
    issue_id = issue["issue_id"]
    name = issue["name"]
    options = sorted(
        [option for option in issue.get("options", []) if isinstance(option, dict)],
        key=lambda option: option["order"],
    )
    option_ids = [option["option_id"] for option in options]

    clause_options = [
        {
            "id": option["option_id"],
            "label": option.get("label", option["option_id"]),
            "order": option["order"],
            "score": {},
        }
        for option in options
    ]

    hard_redlines = {party: [] for party in party_ids}
    soft_redlines = {party: [] for party in party_ids}

    for party in party_ids:
        entry = _as_dict(private_state.get(party))
        goal = _party_goals(entry).get(issue_id)
        if goal is None:
            warnings.append(
                _warning(
                    "GOAL_MISSING",
                    f"private_state_by_party.{party}.goals",
                    f"参与方 {party} 未对议题「{name}」给出 goal，效用分按 0 处理。",
                )
            )
            for item in clause_options:
                item["score"][party] = 0.0
        else:
            scores = _ranked_scores(option_ids, goal["target"])
            for item in clause_options:
                item["score"][party] = scores[item["id"]]
            raw_weights[party][name] = float(goal["weight"])

        redline_items = [
            item
            for item in _as_list(entry.get("redlines"))
            if isinstance(item, dict) and item.get("issue_id") == issue_id
        ]
        hard, soft = _enum_redlines(redline_items, option_ids)
        hard_redlines[party] = hard
        soft_redlines[party] = soft

    if "initial" in issue:
        initial = issue["initial"]
    else:
        initial = option_ids[0]
        warnings.append(
            _warning(
                "INITIAL_DERIVED",
                f"issues[{issue_id}].initial",
                f"枚举议题「{name}」缺少初始值，已取 order 最小的选项 "
                f"{option_ids[0]!r}，建议 B 补充。",
            )
        )

    result = {
        "name": name,
        "issue_id": issue_id,
        "type": "enum",
        "unit": issue.get("unit", ""),
        "options": clause_options,
        "initial": initial,
        "weights": {},
        "redlines": hard_redlines,
    }
    if isinstance(issue.get("initial_ref"), str) and issue["initial_ref"]:
        result["initial_ref"] = issue["initial_ref"]
        warnings.append(
            _warning(
                "INITIAL_REF_RESOLVED",
                f"issues[{issue_id}].initial_ref",
                f"初始值依据 {issue['initial_ref']!r} 已解析并保留在 "
                f"clauses[{issue_id}].initial_ref，供审计追溯。",
            )
        )
    if any(soft_redlines.values()):
        result["soft_redlines"] = soft_redlines
    return result


def _derived_initial(
    positions: Dict[str, dict], low: float, high: float
) -> Tuple[float, Optional[str]]:
    """由双方 ideal 中点推导初始值，再夹逼到双方硬红线可行域。

    返回 (初始值, 诊断码)。诊断码为 None 表示夹逼成功；
    IDEALS_INCOMPLETE 表示 ideal 不足两方，已回退 low；
    REDLINE_RANGE_EMPTY 表示双方硬红线可行域为空，已取中点交给审计暴露。
    """
    ideals = [
        position["ideal"] for position in positions.values() if "ideal" in position
    ]
    if len(ideals) != 2:
        return float(low), "IDEALS_INCOMPLETE"

    mid = (float(ideals[0]) + float(ideals[1])) / 2.0
    lo = max(
        [
            float(position["redline"])
            for position in positions.values()
            if position.get("redline_direction") == "below_is_violation"
            and "redline" in position
        ],
        default=float(low),
    )
    hi = min(
        [
            float(position["redline"])
            for position in positions.values()
            if position.get("redline_direction") == "above_is_violation"
            and "redline" in position
        ],
        default=float(high),
    )
    if lo > hi:
        return mid, "REDLINE_RANGE_EMPTY"
    return min(max(mid, lo), hi), None


def _resolve_numeric_initial(
    issue: dict,
    positions: Dict[str, dict],
    low: float,
    high: float,
    warnings: List[dict],
    name: str,
) -> float:
    """显式 initial 优先；否则按双方 ideal 中点 + 硬红线可行域夹逼推导。"""
    issue_id = issue["issue_id"]
    if "initial" in issue:
        # 契约校验已保证类型与范围，此处直接采用 B 的显式值并跳过推导告警。
        return float(issue["initial"])

    derived, code = _derived_initial(positions, low, high)
    if code == "IDEALS_INCOMPLETE":
        warnings.append(
            _warning(
                "IDEALS_INCOMPLETE",
                f"issues[{issue_id}].initial",
                f"数值议题「{name}」的 ideal 不足两方，无法取中点，"
                f"已回退 range.min={low}。",
            )
        )
    elif code == "REDLINE_RANGE_EMPTY":
        warnings.append(
            _warning(
                "REDLINE_RANGE_EMPTY",
                f"issues[{issue_id}].initial",
                f"数值议题「{name}」双方硬红线可行域为空（lo > hi），"
                f"已取中点 {derived!r}，请审计关注。",
            )
        )
    warnings.append(
        _warning(
            "INITIAL_DERIVED",
            f"issues[{issue_id}].initial",
            f"数值议题「{name}」缺少初始值，已取双方 ideal 中点并按硬红线可行域夹逼，"
            f"建议 B 补充（当前推导值 {derived!r}）。",
        )
    )
    return derived


def _adapt_numeric_clause(
    issue: dict,
    party_ids: List[str],
    private_state: dict,
    raw_weights: Dict[str, Dict[str, float]],
    warnings: List[dict],
) -> dict:
    issue_id = issue["issue_id"]
    name = issue["name"]
    range_value = issue["range"]
    low = range_value["min"]
    high = range_value["max"]

    positions: Dict[str, dict] = {}
    for party in party_ids:
        entry = _as_dict(private_state.get(party))
        goal = _party_goals(entry).get(issue_id)
        position: Dict[str, object] = {}
        if goal is None:
            warnings.append(
                _warning(
                    "GOAL_MISSING",
                    f"private_state_by_party.{party}.goals",
                    f"参与方 {party} 未对议题「{name}」给出 goal，效用分按 0 处理。",
                )
            )
        else:
            position["ideal"] = float(goal["target"])
            raw_weights[party][name] = float(goal["weight"])

        redline_items = [
            item
            for item in _as_list(entry.get("redlines"))
            if isinstance(item, dict) and item.get("issue_id") == issue_id
        ]
        hard_item = next(
            (item for item in redline_items if item.get("hard", True) is not False),
            None,
        )
        soft_item = next(
            (item for item in redline_items if item.get("hard", True) is False),
            None,
        )
        chosen = hard_item or soft_item
        if chosen is not None:
            position["redline"] = float(chosen["value"])
            position["redline_direction"] = (
                "below_is_violation" if chosen["op"] == "min" else "above_is_violation"
            )
            if hard_item is None:
                position["soft"] = True

        if len(redline_items) > 1:
            warnings.append(
                _warning(
                    "MULTIPLE_NUMERIC_REDLINES",
                    f"private_state_by_party.{party}.redlines",
                    f"参与方 {party} 对数值议题「{name}」给出 {len(redline_items)} 条红线，"
                    "引擎单条款只保留一条硬红线（无硬红线时保留第一条软红线），其余未映射。",
                )
            )

        if position:
            positions[party] = position

    initial = _resolve_numeric_initial(issue, positions, low, high, warnings, name)

    result = {
        "name": name,
        "issue_id": issue_id,
        "type": "numeric",
        "unit": issue.get("unit", ""),
        "range": [low, high],
        "step": range_value.get("step"),
        "initial": initial,
        "weights": {},
        "positions": positions,
    }
    if isinstance(issue.get("initial_ref"), str) and issue["initial_ref"]:
        result["initial_ref"] = issue["initial_ref"]
        warnings.append(
            _warning(
                "INITIAL_REF_RESOLVED",
                f"issues[{issue_id}].initial_ref",
                f"初始值依据 {issue['initial_ref']!r} 已解析并保留在 "
                f"clauses[{issue_id}].initial_ref，供审计追溯。",
            )
        )
    return result


def _apply_weights(
    clauses: List[dict],
    party_ids: List[str],
    raw_weights: Dict[str, Dict[str, float]],
    warnings: List[dict],
) -> None:
    """按参与方分别归一化条款权重，再回填到每个条款。"""
    for party in party_ids:
        weights = raw_weights[party]
        total = sum(weights.values())
        normalized = weights
        if abs(total - 1.0) > 0.01:
            warnings.append(
                _warning(
                    "WEIGHT_NORMALIZED",
                    f"private_state_by_party.{party}.goals",
                    f"参与方 {party} 的权重之和为 {total:.4f}，偏差超过 0.01，"
                    "已按比例归一化。",
                )
            )
            if total == 0:
                normalized = {name: 0.0 for name in weights}
            else:
                normalized = {name: value / total for name, value in weights.items()}
        for clause in clauses:
            clause["weights"][party] = normalized.get(clause["name"], 0.0)


def _adapt_clause_roles(b_scenario: dict) -> dict:
    """B 契约的 clause_roles 指向 issue_id；转 C 契约时映射为条款名。

    C 引擎的 offer_patch 以条款名为键，`negotiation_rules.check_card_action`
    与前端 `target_clause` 都按条款名比对，所以只在适配层做这一次映射，
    其余各层（引擎、API、UI）统一只认条款名。缺省返回空字典，由
    `scenario_overrides.apply_overrides` 决定是否回落到内置映射。
    """
    raw = b_scenario.get("clause_roles") or {}
    if not raw:
        return {}
    issues = [item for item in b_scenario.get("issues", []) if isinstance(item, dict)]
    name_by_issue_id = {
        issue.get("issue_id"): issue.get("name")
        for issue in issues
        if issue.get("issue_id")
    }
    known_names = {issue.get("name") for issue in issues if issue.get("name")}
    roles: Dict[str, str] = {}
    for role, value in raw.items():
        name = name_by_issue_id.get(value, value)
        if name not in known_names:
            raise ValueError(
                f"clause_roles.{role} 指向不存在的条款：{value!r}。"
                "应为 issues[].issue_id 或 issues[].name 之一。"
            )
        roles[role] = name
    return roles


def _adapt(b_scenario: dict) -> Tuple[dict, List[dict]]:
    errors = validate_b_contract(b_scenario)
    if errors:
        raise ScenarioContractError("；".join(errors))

    warnings: List[dict] = []

    scenario_type = b_scenario["scenario_type"]
    if scenario_type == "assumption":
        warnings.append(
            _warning(
                "SCENARIO_TYPE_NORMALIZED",
                "$.scenario_type",
                "B 的枚举只有 documented/hypothesis，assumption 已归一化为 hypothesis。",
            )
        )
        scenario_type = "hypothesis"

    parties_source = b_scenario["parties"]
    party_ids = [party["party_id"].lower() for party in parties_source]
    private_state = _normalized_private_state(b_scenario["private_state_by_party"])

    parties: List[dict] = []
    for party in parties_source:
        party_id = party["party_id"].lower()
        private_entry = _as_dict(private_state.get(party_id))
        batna_value = _as_dict(private_entry.get("batna")).get("utility")
        if not _is_number(batna_value):
            batna_value = None
            warnings.append(
                _warning(
                    "BATNA_MISSING",
                    f"private_state_by_party.{party_id}.batna.utility",
                    f"参与方 {party_id} 缺少可用 BATNA 效用值，parties[].batna 置为 null。",
                )
            )

        batna_note_parts = [
            text.rstrip("。")
            for text in (
                _as_dict(private_entry.get("batna")).get("description"),
                _as_dict(private_entry.get("batna")).get("basis"),
            )
            if _require_text(text)
        ]

        hidden_task = private_entry.get("hidden_task")
        if not _require_text(hidden_task):
            hidden_task = ""
            warnings.append(
                _warning(
                    "HIDDEN_TASK_MISSING",
                    f"private_state_by_party.{party_id}.hidden_task",
                    f"参与方 {party_id} 缺少 hidden_task，"
                    "private.bottom_line 置为空字符串。",
                )
            )

        priority_ranking = private_entry.get("priority_ranking")
        if not isinstance(priority_ranking, list):
            priority_ranking = []
            warnings.append(
                _warning(
                    "PRIORITY_RANKING_MISSING",
                    f"private_state_by_party.{party_id}.priority_ranking",
                    f"参与方 {party_id} 缺少 priority_ranking，置为空数组。",
                )
            )

        parties.append(
            {
                "id": party_id,
                "name": party.get("name", party_id),
                "role": party.get("role_label", ""),
                "batna": batna_value,
                "public_position": party.get("public_position", ""),
                "private": {
                    "bottom_line": hidden_task,
                    "priority_ranking": list(priority_ranking),
                    "batna_note": "；".join(batna_note_parts),
                },
            }
        )

    raw_weights: Dict[str, Dict[str, float]] = {party: {} for party in party_ids}
    clauses: List[dict] = []
    for issue in b_scenario["issues"]:
        if issue["type"] == "numeric":
            clauses.append(
                _adapt_numeric_clause(
                    issue, party_ids, private_state, raw_weights, warnings
                )
            )
        else:
            clauses.append(
                _adapt_enum_clause(
                    issue, party_ids, private_state, raw_weights, warnings
                )
            )
    _apply_weights(clauses, party_ids, raw_weights, warnings)

    terminal_rules_source = _as_dict(b_scenario["terminal_rules"])
    # 单数键（B 契约）优先；复数键（C 场景）兼容。契约校验已排除两者冲突。
    # 三布尔已在 validate_b_contract 中强制必填，此处不再用 .get(..., True) 兜底。
    if "accept_requires_no_open_issue" in terminal_rules_source:
        accept_no_open = terminal_rules_source["accept_requires_no_open_issue"]
    else:
        accept_no_open = terminal_rules_source["accept_requires_no_open_issues"]
    terminal_rules = {
        "allow_walk_away": terminal_rules_source["allow_walk_away"],
        "accept_requires_no_open_issues": accept_no_open,
        "partial_agreement_allowed": terminal_rules_source[
            "partial_agreement_allowed"
        ],
    }

    # runtime：字段必须显式读取，缺省才回落默认值并记 warning。
    runtime_source = _as_dict(b_scenario.get("runtime"))
    if "action_points_per_round" in runtime_source:
        action_points_per_round = runtime_source["action_points_per_round"]
    else:
        action_points_per_round = DEFAULT_ACTION_POINTS_PER_ROUND
        warnings.append(
            _warning(
                "RUNTIME_ACTION_POINTS_DEFAULTED",
                "$.runtime.action_points_per_round",
                "B 场景未提供 runtime.action_points_per_round，已回落默认值 "
                f"{DEFAULT_ACTION_POINTS_PER_ROUND}。",
            )
        )

    # deadlock_rounds 位于 terminal_rules 内部（B 1.1），缺省 2。
    if "deadlock_rounds" in terminal_rules_source:
        deadlock_rounds = terminal_rules_source["deadlock_rounds"]
    else:
        deadlock_rounds = DEFAULT_DEADLOCK_ROUNDS
        warnings.append(
            _warning(
                "DEADLOCK_ROUNDS_DEFAULTED",
                "$.terminal_rules.deadlock_rounds",
                "B 场景未提供 terminal_rules.deadlock_rounds，已回落默认值 "
                f"{DEFAULT_DEADLOCK_ROUNDS}。",
            )
        )

    provided_index_rules = b_scenario.get("index_rules")
    if isinstance(provided_index_rules, dict) and provided_index_rules:
        # B 1.1 原生表是 13 标签平铺形状，必须转换为引擎的
        # image_actions / trust_actions 两张表，否则结算会静默归零。
        index_rules, index_warnings = _normalize_index_rules(
            provided_index_rules, party_ids
        )
        warnings.extend(index_warnings)
        warnings.append(
            _warning(
                "INDEX_RULES_PRESERVED",
                "$.index_rules",
                "输入场景自带 index_rules，适配层已归一为引擎可读形状"
                "（原生形状原样保留），不使用默认查表。",
            )
        )
    else:
        index_rules = deepcopy(DEFAULT_INDEX_RULES)
        warnings.append(
            _warning(
                "DEFAULT_INDEX_RULES",
                "$.index_rules",
                "B 契约没有 index_rules，已注入 docs/index_rules.md 的默认查表与 50/50 初值、"
                "1.0 敏感度；如需场景专用口径，需上游组装层补充。",
            )
        )

    scenario = {
        "scenario_id": b_scenario["scenario_id"],
        "title": b_scenario["title"],
        "scenario_type": scenario_type,
        "background": b_scenario["background"],
        "assumptions": [_assumption_text(item) for item in b_scenario["assumptions"]],
        # 旁路键：原样保留 B 的结构化假设，供审计/复盘做“假设—条款”追溯；
        # 引擎只读 assumptions（字符串数组），全程忽略本键。
        "assumptions_detail": deepcopy(b_scenario["assumptions"]),
        "max_rounds": b_scenario["max_rounds"],
        "deadlock_rounds": deadlock_rounds,
        "action_points_per_round": action_points_per_round,
        "parties": parties,
        "clauses": clauses,
        "clause_roles": _adapt_clause_roles(b_scenario),
        "index_rules": index_rules,
        "terminal_rules": terminal_rules,
        "allow_accept_with_open_issues": not terminal_rules[
            "accept_requires_no_open_issues"
        ],
        "public_facts": deepcopy(b_scenario["public_facts"]),
    }
    return scenario, warnings


def adapt_scenario(b_scenario: dict) -> dict:
    """B 格式 → C 格式，返回可直接喂给 RulesEngine 的 dict。"""
    return _adapt(b_scenario)[0]


def adapt_scenario_with_warnings(b_scenario: dict) -> Tuple[dict, List[dict]]:
    """同上，但同时返回结构化 warning 列表。"""
    return _adapt(b_scenario)


def load_and_adapt(path: str) -> Tuple[dict, List[dict]]:
    """读取 B 侧场景文件（带 BOM）并适配，返回 (scenario, warnings)。"""
    with open(path, "r", encoding="utf-8-sig") as handle:
        source = json.load(handle)
    return _adapt(source)
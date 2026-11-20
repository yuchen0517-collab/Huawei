from __future__ import annotations

import copy

ACTION_CONTRACT_VERSION = 2
DEFAULT_ACTION_POINTS = 4
MULTI_ISSUE_ACTION_POINTS = 5
DEADLOCK_ROUNDS = 3

# 优先选语义贴合且有预置 options 的 enum 条款，便于前端选择和双方比对；
# numeric 仅在语义更贴切时使用，不为了类型牺牲条款语义。
CLAUSE_ROLES_BY_SCENARIO = {
    "scn-chip-controls-0001": {
        "condition": "第三国再出口限制",
        "performance": "许可审批时限",
        "exit": "关键矿产出口安排",
    },
    "scn-chip-controls-nozopa-0001": {
        "condition": "第三国再出口限制",
        "performance": "许可审批时限",
        "exit": "关键矿产出口安排",
    },
    "scn-dst-cn-us-0001": {
        "condition": "征税门槛",
        "performance": "追溯适用期",
        "exit": "加征关税去留",
    },
}


def apply_overrides(scenario: dict) -> dict:
    """返回补齐契约元数据的新场景字典，不修改调用方持有的对象。"""
    result = copy.deepcopy(scenario)
    scenario_id = result.get("scenario_id")
    if not result.get("clause_roles"):
        roles = CLAUSE_ROLES_BY_SCENARIO.get(scenario_id)
        if roles is not None:
            clause_names = [clause["name"] for clause in result.get("clauses", [])]
            for role, clause_name in roles.items():
                if clause_name not in clause_names:
                    raise ValueError(
                        f"场景 {scenario_id!r} 的 clause_roles.{role} "
                        f"指向不存在的条款 {clause_name!r}"
                    )
            result["clause_roles"] = dict(roles)

    issue_count = len(result.get("clauses", []))
    result["action_points_per_round"] = (
        MULTI_ISSUE_ACTION_POINTS if issue_count >= 4 else DEFAULT_ACTION_POINTS
    )
    result["deadlock_rounds"] = DEADLOCK_ROUNDS
    result["action_contract_version"] = ACTION_CONTRACT_VERSION
    return result


def role_clause(scenario: dict, role: str) -> str | None:
    return (scenario.get("clause_roles") or {}).get(role)
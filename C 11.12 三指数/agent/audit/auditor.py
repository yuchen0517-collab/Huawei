"""协议审计：只出意见，绝不自动修改协议。

五项检查一次报全：
- clause_missing / version_mismatch / redline_conflict → blocking
- vague_condition / unverifiable_condition → warning
"""

from __future__ import annotations

from typing import List, Optional

from engine.validator import (
    clause_map,
    clause_names,
    is_redline_violation,
    option_value,
    party_ids,
)

VAGUE_WORDS = (
    "另行商定",
    "视情况",
    "适当",
    "尽量",
    "酌情",
    "原则上",
    "有关方面",
    "相关方",
)

VERIFIABLE_VERBS = (
    "核查",
    "报告",
    "提交",
    "评估",
    "期限",
    "验收",
    "审计",
    "披露",
    "通报",
    "公布",
)


def _issue(
    check: str,
    severity: str,
    message: str,
    clause: Optional[str] = None,
    party: Optional[str] = None,
) -> dict:
    item = {"check": check, "severity": severity, "message": message}
    if clause is not None:
        item["clause"] = clause
    if party is not None:
        item["party"] = party
    return item


def audit_agreement(state, scenario: dict, agreement=None) -> dict:
    """对协议做五项检查。state / scenario / agreement 均为只读。"""
    if agreement is None:
        agreement = state.agreement

    issues: List[dict] = []

    if agreement is None:
        issues.append(
            _issue("clause_missing", "blocking", "尚未签署协议，没有可审计的条款。")
        )
    else:
        clauses = agreement.clauses or {}
        names = clause_names(scenario)

        for name in names:
            if name not in clauses:
                issues.append(
                    _issue(
                        "clause_missing",
                        "blocking",
                        f"协议缺少议题「{name}」。",
                        clause=name,
                    )
                )

        if int(agreement.version) != int(state.current_version):
            issues.append(
                _issue(
                    "version_mismatch",
                    "blocking",
                    f"协议引用版本 V{agreement.version}，最新版本是 V{state.current_version}。",
                )
            )

        scenario_clauses = clause_map(scenario)
        for name, entry in clauses.items():
            clause = scenario_clauses.get(name)
            if clause is None:
                continue
            option = option_value(entry)
            for party in party_ids(scenario):
                if is_redline_violation(clause, option, party):
                    issues.append(
                        _issue(
                            "redline_conflict",
                            "blocking",
                            f"条款「{name}」的取值 {option!r} 触碰 {party} 红线。",
                            clause=name,
                            party=party,
                        )
                    )

        for condition in agreement.conditions or []:
            if any(word in condition for word in VAGUE_WORDS):
                issues.append(
                    _issue(
                        "vague_condition",
                        "warning",
                        f"履约条件含模糊表述：{condition}",
                    )
                )
                continue

            has_digit = any(char.isdigit() for char in condition)
            has_verb = any(verb in condition for verb in VERIFIABLE_VERBS)
            if not has_digit and not has_verb:
                issues.append(
                    _issue(
                        "unverifiable_condition",
                        "warning",
                        f"履约条件没有数字或可核验动作：{condition}",
                    )
                )

    blocking = sum(1 for item in issues if item["severity"] == "blocking")
    warning = sum(1 for item in issues if item["severity"] == "warning")

    return {
        "ok": blocking == 0,
        "issues": issues,
        "summary": {"blocking": blocking, "warning": warning},
    }
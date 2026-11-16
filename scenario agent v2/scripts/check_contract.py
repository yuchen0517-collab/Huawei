#!/usr/bin/env python3
"""契约 1.1 自检：schema 语法 + 场景实例校验 + 开局指数试算。

用法：
    py.bat scripts\\check_contract.py
    py.bat scripts\\check_contract.py data\\scenarios\\main_chip_controls.json

检查内容：
1. docs/contracts/scenario.schema.json 本身是合法 JSON Schema（Draft 2020-12）
2. docs/contracts/index_rules.v1.json 覆盖 13 个 effect label × 三档强度
3. 目标场景能通过 schema 校验（结构 / 类型 / 值域）
4. 目标场景能通过 validate_scenario（R0–R15 业务规则）
5. 若每个 issue 都带 initial，用 zopa.utility 试算双方开局 Interest
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    sys.exit("缺少依赖：pip install jsonschema")

from agent.scenario import zopa  # noqa: E402
from agent.scenario.models import validate_index_rules, validate_scenario  # noqa: E402

SCHEMA_PATH = ROOT / "docs" / "contracts" / "scenario.schema.json"
INDEX_RULES_PATH = ROOT / "docs" / "contracts" / "index_rules.v1.json"
DEFAULT_TARGETS = [
    ROOT / "docs" / "contracts" / "scenario.example.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_validator() -> Draft202012Validator:
    schema = load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def initial_deal(scenario: dict) -> tuple[dict, list[str]]:
    deal: dict = {}
    missing: list[str] = []
    for issue in scenario.get("issues") or []:
        issue_id = issue.get("issue_id")
        if "initial" in issue:
            deal[issue_id] = issue["initial"]
        else:
            missing.append(str(issue_id))
    return deal, missing


def print_initial_interest(scenario: dict) -> None:
    deal, missing = initial_deal(scenario)
    if missing:
        print("    开局指数：跳过（缺少 initial：%s）" % "、".join(missing))
        return
    print("    开局指数（zopa.utility）：")
    for party in scenario.get("parties") or []:
        party_id = party.get("party_id")
        try:
            value = zopa.utility(scenario, party_id, deal)
        except Exception as exc:  # noqa: BLE001
            print("      %-6s 计算失败：%s: %s" % (party_id, type(exc).__name__, exc))
            continue
        print("      %-6s %-12s Interest=%3d" % (party_id, party.get("name", "")[:12], round(value)))


def check_index_rules(path: Path) -> bool:
    print("\n== %s" % path)
    if not path.exists():
        print("    [FAIL] 文件不存在")
        return False
    try:
        table = load_json(path)
    except Exception as exc:  # noqa: BLE001
        print("    [FAIL] 读取失败：%s: %s" % (type(exc).__name__, exc))
        return False

    problems = validate_index_rules(table)
    if problems:
        print("    [FAIL] %d 处" % len(problems))
        for problem in problems[:8]:
            print("      %s  %s  %s" % (problem.code, problem.path, problem.message))
        return False

    labels = [key for key in table if key != "initial"]
    print("    [OK]   13 个 effect label × slight/moderate/major，initial=%s" % (table.get("initial"),))
    print("           labels: %s" % ", ".join(sorted(labels)))
    return True


def check_one(path: Path, validator: Draft202012Validator) -> bool:
    print("\n== %s" % path)
    try:
        data = load_json(path)
    except Exception as exc:  # noqa: BLE001
        print("    [FAIL] 读取失败：%s: %s" % (type(exc).__name__, exc))
        return False

    ok = True
    schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if schema_errors:
        ok = False
        print("    [FAIL] schema：%d 处" % len(schema_errors))
        for error in schema_errors[:8]:
            print("      %s  %s" % ("/".join(map(str, error.path)) or "<root>", error.message))
    else:
        print("    [OK]   schema")

    problems = validate_scenario(data)
    if problems:
        ok = False
        print("    [FAIL] 业务规则：%d 处" % len(problems))
        for problem in problems[:8]:
            print("      %s  %s  %s" % (problem.code, problem.path, problem.message))
    else:
        print("    [OK]   业务规则 R0–R15")

    rules = data.get("terminal_rules") or {}
    print(
        "    terminal_rules  walk_away=%s accept_no_open=%s partial=%s deadlock_rounds=%s"
        % (
            rules.get("allow_walk_away"),
            rules.get("accept_requires_no_open_issue"),
            rules.get("partial_agreement_allowed"),
            rules.get("deadlock_rounds", 2),
        )
    )
    print_initial_interest(data)
    return ok


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    validator = build_validator()
    print("schema: %s" % SCHEMA_PATH)
    print("$id   : %s" % load_json(SCHEMA_PATH).get("$id"))

    results = [check_index_rules(INDEX_RULES_PATH)]
    if argv:
        targets = [Path(item).resolve() for item in argv]
    else:
        targets = list(DEFAULT_TARGETS)
        targets += sorted((ROOT / "data" / "scenarios").glob("*.json"))

    results += [check_one(path, validator) for path in targets if path.exists()]
    print("\n%d/%d 通过" % (sum(results), len(results)))
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
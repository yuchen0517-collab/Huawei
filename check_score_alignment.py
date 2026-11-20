"""口径一致性检查：B 的 `zopa`（QA/测试口径）与引擎（App 口径）必须算出同一份效用。

背景：11-20 之前两边是两套算法——enumerated 一个按 order、一个按 target；
numeric 一个按「红线→目标」比例、一个按整段物理区间 closeness。结果同一份方案
会得出相反结论（no_zopa 变体：zopa 说双方都该退出，引擎说双方都大赚）。
现已统一为「红线锚定 + 逐方 target 位次」，本脚本用于防止两边再次漂移。

运行：
    .venv\\Scripts\\python.exe check_score_alignment.py

退出码 0 = 完全一致；1 = 存在不一致（会打印明细）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
ENGINE_DIR = ROOT / "C 11.12 三指数"
B_DIR = ROOT / "scenario agent v2"
SCENARIO_DIR = B_DIR / "data" / "scenarios"
SCENARIO_FILES = (
    "main_chip_controls.json",
    "no_zopa_variant.json",
    "backup_dst_bilateral.json",
)

if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from engine.terminal import package_utility  # noqa: E402
from load_scenario_bridge import load_scenario  # noqa: E402


def _load_zopa():
    """按文件路径加载 B 的 zopa，避开 `agent` 包名在两棵树里冲突。"""
    spec = importlib.util.spec_from_file_location(
        "b_zopa_module", B_DIR / "agent" / "scenario" / "zopa.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


zopa = _load_zopa()


def _deal_as_plan(raw: dict, adapted: dict) -> tuple[dict, dict]:
    """把 B 口径的 issue_id 方案翻译成引擎口径的条款名方案，并给出参与方别名。"""
    issue_to_clause = {issue["issue_id"]: issue["name"] for issue in raw["issues"]}
    deal = zopa.suggest_deal(raw)
    plan = {
        issue_to_clause[issue_id]: {"option": value}
        for issue_id, value in deal.items()
        if issue_id in issue_to_clause
    }
    return plan, deal


def compare_scenario(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    adapted = load_scenario(path)
    plan, deal = _deal_as_plan(raw, adapted)
    engine_parties = [party["id"] for party in adapted["parties"]]
    raw_parties = [party["party_id"] for party in raw["parties"]]
    batna = {party["id"]: party.get("batna") for party in adapted["parties"]}

    rows = []
    for engine_party, raw_party in zip(engine_parties, raw_parties):
        engine_value = round(100 * package_utility(plan, adapted, engine_party), 2)
        zopa_value = round(zopa.utility(raw, raw_party, deal), 2)
        rows.append(
            {
                "scenario": path.name,
                "party": engine_party,
                "engine": engine_value,
                "zopa": zopa_value,
                "delta": round(engine_value - zopa_value, 2),
                "match": abs(engine_value - zopa_value) < 0.05,
                "batna": batna.get(engine_party),
                "engine_above_batna": engine_value >= float(batna.get(engine_party) or 0),
                "zopa_above_batna": zopa_value >= float(batna.get(engine_party) or 0),
            }
        )
    return rows


def compare_all() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for filename in SCENARIO_FILES:
        rows.extend(compare_scenario(SCENARIO_DIR / filename))
    return rows


def main() -> int:
    rows = compare_all()
    mismatches = [row for row in rows if not row["match"]]
    verdict_mismatches = [
        row for row in rows if row["engine_above_batna"] != row["zopa_above_batna"]
    ]
    for row in rows:
        flag = "OK " if row["match"] and row["engine_above_batna"] == row["zopa_above_batna"] else "BAD"
        print(
            f"[{flag}] {row['scenario']:<26} {row['party']:<3} "
            f"engine={row['engine']:>6} zopa={row['zopa']:>6} "
            f"batna={row['batna']} "
            f"engine_above={row['engine_above_batna']} zopa_above={row['zopa_above_batna']}"
        )
    print(
        json.dumps(
            {
                "comparisons": len(rows),
                "value_mismatches": len(mismatches),
                "verdict_mismatches": len(verdict_mismatches),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not mismatches and not verdict_mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())

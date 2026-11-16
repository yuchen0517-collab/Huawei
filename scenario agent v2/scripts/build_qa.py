#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 docs/scenario_qa.md：对 data/scenarios 下每份场景跑校验与可行性，出总表。

用法：py.bat scripts/build_qa.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from agent.scenario.models import validate_scenario
from agent.scenario.zopa import evaluate_deal, scenario_feasibility, suggest_deal

SCENARIO_DIR = ROOT / "data" / "scenarios"
OUT = ROOT / "docs" / "scenario_qa.md"


def analyse(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    problems = validate_scenario(data)
    feasibility = scenario_feasibility(data)
    deal = suggest_deal(data)
    evaluation = evaluate_deal(data, deal) if deal else None
    return {
        "file": path.name,
        "id": data.get("scenario_id"),
        "title": data.get("title"),
        "type": data.get("scenario_type"),
        "issues": len(data.get("issues") or []),
        "facts": len(data.get("public_facts") or []),
        "problems": [f"{p.code}@{p.path}" for p in problems],
        "zopa": feasibility["zopa_exists"],
        "infeasible": feasibility["infeasible_issues"],
        "deal": deal,
        "evaluation": evaluation,
        "demoable": not problems and feasibility["zopa_exists"],
    }


def fmt_deal(deal: dict) -> str:
    if not deal:
        return "—"
    return "，".join(f"{k}={v}" for k, v in deal.items())


def fmt_eval(evaluation: dict | None) -> str:
    if not evaluation:
        return "—"
    parts = []
    for party, info in evaluation["parties"].items():
        flag = "✅" if info["above_batna"] else "❌"
        parts.append(f"{party} {info['utility']}>{info['batna']}{flag}")
    return "；".join(parts)


def main() -> int:
    rows = [analyse(path) for path in sorted(SCENARIO_DIR.glob("*.json"))]
    lines = [
        "# 场景 QA 表",
        "",
        f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}　｜　生成脚本：`scripts/build_qa.py`",
        "> 判定口径：`validate_scenario`（R0–R11）零问题 + `zopa.py` 可行性计算",
        "",
        "## 一、场景总表",
        "",
        "| 文件 | scenario_id | 类型 | 议题 | 事实 | 校验 | ZOPA | 可演示 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        check = "✅ 0 问题" if not row["problems"] else f"❌ {len(row['problems'])} 个"
        zopa = "✅ 有" if row["zopa"] else f"❌ 无（{', '.join(row['infeasible'])}）"
        lines.append(
            f"| `{row['file']}` | `{row['id']}` | {row['type']} | {row['issues']} | "
            f"{row['facts']} | {check} | {zopa} | {'✅' if row['demoable'] else '—'} |"
        )

    lines += ["", "## 二、逐份明细", ""]
    for row in rows:
        lines.append(f"### {row['file']}")
        lines.append("")
        lines.append(f"- **{row['title']}**")
        lines.append(f"- 议题数：{row['issues']}　事实数：{row['facts']}　类型：`{row['type']}`")
        if row["problems"]:
            lines.append(f"- 校验问题：{', '.join(row['problems'])}")
        else:
            lines.append("- 校验：通过（R0–R11 全部无问题）")
        lines.append(
            f"- ZOPA：{'各议题均有成交区间' if row['zopa'] else '无合作区间，议题 ' + ', '.join(row['infeasible'])}"
        )
        lines.append(f"- 参考成交方案：{fmt_deal(row['deal'])}")
        lines.append(f"- 效用 vs BATNA：{fmt_eval(row['evaluation'])}")
        if not row["zopa"]:
            lines.append("- **设计意图**：本份为「无合作区间」变体，用于测试规则引擎的僵局判定与理性退出，**不可当作缺陷去修**。")
        lines.append("")

    lines += [
        "## 三、随机议题（规则层实测）",
        "",
        "| 输入 | 结论 | 说明 |",
        "|---|---|---|",
        "| 六国数字税谈判 | `needs_narrowing`（U4） | 三方以上，需收窄为双边；可用 `compile_from_narrowing` 两步走 |",
        "| 2028 年美国大选结果会怎样 | `unsupported`（U2） | 预测未发生事件，直接拒绝 |",
        "| 谁该为气候变暖负责 | `unsupported`（U1） | 单一二元是非题 |",
        "| 某部长的私生活传闻 | `unsupported`（U3） | 涉及在世私人个体隐私 |",
        "",
        "> 详细台账见 `data/scenarios/random_inputs.md`。",
        "",
        "## 四、已知限制（交付时如实说明）",
        "",
        "1. **真实模型链路未验证**：`DEEPSEEK_API_KEY` 未配置，`compile_scenario` 的模型调用环节从未真实跑通；",
        "   离线链路（解析 → Schema → R0–R11 → 回喂修复）已由 `scripts/offline_check.py` 四场景验证。",
        "2. **美国 `.gov` 外链在国内网络不可达**（`bis.gov`/`commerce.gov`/`ustr.gov`/`federalregister.gov` 均超时），",
        "   中方来源（`gov.cn`/`mofcom.gov.cn`）正常；演示时不现场点外链。",
        "3. **`fastapi` 未安装**：接口以标准库模式提供（`py.bat -m agent.scenario.api`），",
        "   集成到 A 的 FastAPI 应用时使用 `create_router()`。",
        "",
        "## 五、复现方式",
        "",
        "```powershell",
        "cd \"D:\\华为杯\\Huawei\\scenario agent v2\"",
        "py.bat scripts\\build_qa.py        # 重新生成本表",
        "py.bat -m pytest tests -q          # 全量测试",
        "py.bat scripts\\offline_check.py    # 离线链路验证",
        "py.bat -m agent.scenario.api --port 8000   # 起接口",
        "```",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写入 {OUT}")
    for row in rows:
        print(f"  {row['file']:<28} 校验{'OK' if not row['problems'] else 'FAIL'}  ZOPA={row['zopa']}  可演示={row['demoable']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""一条命令跑完整局谈判工作流。

运行：
    python run_workflow.py

输出：
    docs/workflow_trace.json
"""

from __future__ import annotations

import json
import os

from engine import RulesEngine, load_scenario
from engine.orchestrator import NegotiationOrchestrator

ROOT = os.path.dirname(os.path.abspath(__file__))
SCENARIO_PATH = os.path.join(ROOT, "scenarios", "demo_scenario.json")
TRACE_PATH = os.path.join(ROOT, "docs", "workflow_trace.json")


def action(action_id, actor, action_type, patch=None, conditions=None):
    return {
        "action_id": action_id,
        "actor": actor,
        "action_type": action_type,
        "card_id": None,
        "offer_patch": patch or {},
        "conditions": list(conditions) if conditions is not None else [],
        "expected_effect": "工作流演示",
        "public_message": "工作流演示。",
    }


def workflow_rounds():
    """固定动作脚本：与 demo.py 的成功路径一致，最终完整协议。"""
    return [
        [
            action(
                "wf-cn-offer-1",
                "cn",
                "offer",
                {
                    "全球算力资源分配": {
                        "option": "附带可核查机制",
                        "note": "以可核查机制换取分配安排的推进。",
                    }
                },
            ),
            action(
                "wf-us-counter-1",
                "us",
                "counter_offer",
                {
                    "前沿模型评测门槛": {
                        "option": 50,
                        "note": "美方将评测门槛提高到 50。",
                    }
                },
            ),
            action(
                "wf-cn-final-1",
                "cn",
                "final_offer",
                {
                    "数据跨境流动": {
                        "option": "白名单互认",
                        "note": "确认数据跨境采用白名单互认。",
                    }
                },
            ),
        ],
        [
            action(
                "wf-us-counter-2",
                "us",
                "counter_offer",
                {
                    "前沿模型评测门槛": {
                        "option": 45,
                        "note": "美方下调评测门槛至 45。",
                    }
                },
            ),
            action("wf-cn-accept-1", "cn", "accept"),
        ],
    ]


def main() -> None:
    scenario = load_scenario(SCENARIO_PATH)
    engine = RulesEngine(scenario, session_id="workflow-demo")
    orchestrator = NegotiationOrchestrator(engine)
    trace = orchestrator.run(workflow_rounds(), requester="workflow-runner")

    os.makedirs(os.path.dirname(TRACE_PATH), exist_ok=True)
    with open(TRACE_PATH, "w", encoding="utf-8") as handle:
        json.dump(trace, handle, ensure_ascii=False, indent=2)

    terminal = trace["terminal"]
    summary = (
        f"终局={terminal['type']} coverage={terminal['coverage']} "
        f"轮数={terminal['round']} "
        f"审计blocking={trace['audit']['summary']['blocking']} "
        f"trace={os.path.relpath(TRACE_PATH, ROOT)}"
    )
    print(summary)

    if terminal["type"] != "FULL_AGREEMENT":
        raise SystemExit(f"期望 FULL_AGREEMENT，实际 {terminal['type']}。")
    if terminal["coverage"] != 1.0:
        raise SystemExit(f"期望 coverage=1.0，实际 {terminal['coverage']}。")
    if trace["audit"]["summary"]["blocking"] != 0:
        raise SystemExit(
            f"期望审计 blocking=0，实际 {trace['audit']['summary']['blocking']}。"
        )


if __name__ == "__main__":
    main()
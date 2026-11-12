"""演示一局完整谈判，并把真实状态写入 docs/。

运行：python demo.py
"""

from __future__ import annotations

import json
import os

from agent.audit import audit_agreement
from engine import RulesEngine, load_scenario

ROOT = os.path.dirname(os.path.abspath(__file__))
SCENARIO_PATH = os.path.join(ROOT, "scenarios", "demo_scenario.json")
STATE_PATH = os.path.join(ROOT, "docs", "state.example.json")
EVALUATION_PATH = os.path.join(ROOT, "docs", "evaluation.example.json")


def make_action(
    action_id,
    actor,
    action_type,
    patch=None,
    conditions=None,
    labels=None,
    expected_effect="",
    public_message="",
):
    action = {
        "action_id": action_id,
        "actor": actor,
        "action_type": action_type,
        "card_id": None,
        "offer_patch": patch or {},
        "conditions": conditions or [],
        "expected_effect": expected_effect,
        "public_message": public_message,
    }
    if labels is not None:
        action["effect_labels"] = labels
    return action


def show(engine, label, result):
    ok, code, message, events = result
    status = "通过" if ok else f"拦截 {code}"
    print(f"[{label}] {status} | {message or '状态已更新'}")
    print(
        "  version={} phase={} points={} open_issues={}".format(
            engine.state.current_version,
            engine.state.phase,
            engine.state.action_points,
            engine.state.open_issues,
        )
    )
    print(
        "  indices={} events={}".format(
            json.dumps(engine.state.indices, ensure_ascii=False),
            len(events),
        )
    )
    return ok


def main() -> None:
    scenario = load_scenario(SCENARIO_PATH)
    engine = RulesEngine(scenario, session_id="demo-ai-governance-2026")

    print("=" * 72)
    print(scenario["title"])
    print("参与方：", " / ".join(party["name"] for party in scenario["parties"]))
    print("初始指数：", json.dumps(engine.state.indices, ensure_ascii=False))
    print("初始未决条款：", engine.state.open_issues)
    print("=" * 72)

    show(
        engine,
        "V1 cn 提案",
        engine.submit_action(
            make_action(
                "cn-offer-0001",
                "cn",
                "offer",
                patch={
                    "全球算力资源分配": {
                        "option": "附带可核查机制",
                        "note": "以可核查机制换取分配安排的推进。",
                    }
                },
                labels=[
                    {"label": "constructive_proposal", "magnitude": "moderate"}
                ],
                expected_effect="推动算力分配从自愿分享转向可核查安排。",
                public_message="中方建议在算力资源分配中加入可核查机制，兼顾各方关切。",
            )
        ),
    )

    show(
        engine,
        "V2 us 还价",
        engine.submit_action(
            make_action(
                "us-counter-0001",
                "us",
                "counter_offer",
                patch={
                    "前沿模型评测门槛": {
                        "option": 50,
                        "note": "美方将评测门槛从 30 提高到 50。",
                    }
                },
                labels=[{"label": "hardline_stance", "magnitude": "slight"}],
                expected_effect="以更高评测门槛回应中方提案。",
                public_message="美方同意讨论可核查机制，但评测门槛必须提高。",
            )
        ),
    )

    early_accept = engine.submit_action(
        make_action(
            "cn-accept-0000",
            "cn",
            "accept",
            expected_effect="试图在还有未决条款时接受。",
            public_message="中方希望立即接受当前方案。",
        )
    )
    if early_accept[0]:
        raise SystemExit("未决条款拦截失败：还有未决条款时 accept 被放行。")
    print("[重点] cn 在「数据跨境流动」未决时尝试 accept → 被拦截")
    print(f"  错误码={early_accept[1]} 说明={early_accept[2]}")
    print(
        "  状态未变：version={} open_issues={}".format(
            engine.state.current_version, engine.state.open_issues
        )
    )

    show(
        engine,
        "V3 cn 最后报价",
        engine.submit_action(
            make_action(
                "cn-final-0001",
                "cn",
                "final_offer",
                patch={
                    "数据跨境流动": {
                        "option": "白名单互认",
                        "note": "确认数据跨境采用白名单互认。",
                    }
                },
                labels=[{"label": "hardline_stance", "magnitude": "slight"}],
                expected_effect="锁定中方最后立场。",
                public_message="这是中方的最后报价：白名单互认，不再修改。",
            )
        ),
    )

    print("[回合推进] 本轮行动点用尽，进入下一轮")
    print("  ", engine.next_round())

    show(
        engine,
        "V4 us 还价",
        engine.submit_action(
            make_action(
                "us-counter-0002",
                "us",
                "counter_offer",
                patch={
                    "前沿模型评测门槛": {
                        "option": 45,
                        "note": "美方下调评测门槛至 45。",
                    }
                },
                labels=[{"label": "conditional_concession", "magnitude": "slight"}],
                expected_effect="以小幅让步换取协议。",
                public_message="美方可以将门槛下调到 45，但这是有条件的让步。",
            )
        ),
    )

    locked_ok = engine.submit_action(
        make_action(
            "cn-offer-0002",
            "cn",
            "offer",
            patch={
                "前沿模型评测门槛": {
                    "option": 40,
                    "note": "试图在声明最后报价后继续修改。",
                }
            },
            expected_effect="再次修改条款。",
            public_message="中方希望再调整评测门槛。",
        )
    )
    if locked_ok[0]:
        raise SystemExit("final_offer 拦截失败：本应拒绝的行动被接受了。")
    print("[重点] cn 声明最后报价后再提 offer → 被拦截")
    print(f"  错误码={locked_ok[1]} 说明={locked_ok[2]}")
    print(
        "  状态未变：version={} indices={}".format(
            engine.state.current_version,
            json.dumps(engine.state.indices, ensure_ascii=False),
        )
    )

    show(
        engine,
        "V5 cn 接受",
        engine.submit_action(
            make_action(
                "cn-accept-0001",
                "cn",
                "accept",
                conditions=[],
                labels=[{"label": "diplomatic_reframe", "magnitude": "slight"}],
                expected_effect="接受美方还价，达成协议。",
                public_message="中方接受美方还价，谈判达成协议。",
            )
        ),
    )

    evaluation = engine.evaluate()
    audit = audit_agreement(engine.state, scenario)
    replay = engine.replay()

    print("-" * 72)
    print("终局：", engine.state.terminal["type"], engine.state.terminal["label"])
    print("协议覆盖：", evaluation["agreement_quality"])
    print("BATNA 对比：", json.dumps(evaluation["batna_comparison"], ensure_ascii=False))
    print("红线检查：", json.dumps(evaluation["redline_check"], ensure_ascii=False))
    print("审计：", json.dumps(audit, ensure_ascii=False))
    print("replay 一致：", replay["consistent"])
    print("-" * 72)

    if engine.state.terminal["type"] != "FULL_AGREEMENT":
        raise SystemExit("期望 FULL_AGREEMENT，实际为 " + engine.state.terminal["type"])
    if evaluation["agreement_quality"]["coverage"] != 1.0:
        raise SystemExit("期望 coverage=1.0")
    if not all(
        item["better_than_batna"]
        for item in evaluation["batna_comparison"].values()
    ):
        raise SystemExit("期望双方 better_than_batna 均为 true")
    if audit["summary"] != {"blocking": 0, "warning": 0}:
        raise SystemExit("期望审计 blocking=0 warning=0")
    if not replay["consistent"]:
        raise SystemExit("replay 不一致")

    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    engine.dump(STATE_PATH)
    with open(EVALUATION_PATH, "w", encoding="utf-8") as handle:
        json.dump(evaluation, handle, ensure_ascii=False, indent=2)

    print("已写入：")
    print("  " + os.path.relpath(STATE_PATH, ROOT))
    print("  " + os.path.relpath(EVALUATION_PATH, ROOT))


if __name__ == "__main__":
    main()
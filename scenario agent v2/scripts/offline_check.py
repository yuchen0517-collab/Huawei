#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线验证编译链路：不调模型、不花钱、不需要 key。

用四个"假模型"分别模拟：
  一、一次通过
  二、第一次被校验拦下 → 回喂修复 → 通过
  三、连续不合格 → 抛出异常，拒绝返回半成品
  四、预测类议题 → 规则层直接拦下，模型一次都不调

产物写到 proof/offline_*.txt，可直接作为"生成—校验失败—修复"的过程证据。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from agent.scenario.compiler import ScenarioCompileError, compile_scenario

EXAMPLE = json.loads((ROOT / "docs" / "contracts" / "scenario.example.json").read_text(encoding="utf-8"))
TOPIC = "中美先进计算芯片的许可门槛与审批时限"
OUT_DIR = ROOT / "proof"


def fake_llm(*payloads):
    """按顺序返回假输出，并记录每次收到的消息，便于断言。"""
    calls = []

    def caller(messages, **_kwargs):
        calls.append(messages)
        index = min(len(calls) - 1, len(payloads) - 1)
        return payloads[index]

    return caller, calls


def good_payload() -> str:
    return json.dumps(EXAMPLE, ensure_ascii=False)


def broken_payload() -> str:
    """把权重和改坏：0.5+0.3+0.2 改成 0.3+0.3+0.2 = 0.8，触发 R1。"""
    data = copy.deepcopy(EXAMPLE)
    data["private_state_by_party"]["cn"]["goals"][0]["weight"] = 0.3
    return json.dumps(data, ensure_ascii=False)


def save(name: str, text: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / name).write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
def case_once() -> str:
    caller, calls = fake_llm(good_payload())
    result = compile_scenario(TOPIC, llm=caller)
    assert result.ok is True, "应该编译成功"
    assert result.attempts == 1, f"应一次通过，实际 attempts={result.attempts}"
    assert len(calls) == 1
    names = [issue.name for issue in result.scenario.issues]
    save("offline_1_ok.txt",
         "【场景一】一次通过\n"
         f"topic={TOPIC}\n"
         f"attempts={result.attempts}\n"
         f"模型调用次数={len(calls)}\n"
         f"条款={names}\n")
    return f"一次通过                attempts=1  调用1次  条款{len(names)}个"


def case_repair() -> str:
    caller, calls = fake_llm(broken_payload(), good_payload())
    result = compile_scenario(TOPIC, llm=caller)
    assert result.ok is True, "修复后应该成功"
    assert result.attempts == 2, f"应重试一次后成功，实际 attempts={result.attempts}"
    repair_text = calls[1][-1]["content"]
    assert "R1_weight_sum" in repair_text, "回喂的消息里必须带上具体问题码"
    save("offline_2_repair.txt",
         "【场景二】第一次被校验拦下 → 回喂问题清单 → 通过\n"
         f"attempts={result.attempts}\n"
         "第二次发给模型的问题清单：\n\n" + repair_text + "\n")
    return "校验失败后自动修复      attempts=2  回喂含 R1_weight_sum"


def case_reject() -> str:
    caller, _calls = fake_llm(broken_payload())
    try:
        compile_scenario(TOPIC, llm=caller, max_retry=1)
    except ScenarioCompileError as exc:
        assert exc.last_issues, "异常里必须带上问题列表"
        detail = "\n".join(f"[{p.code}] {p.path}：{p.message}" for p in exc.last_issues)
        save("offline_3_reject.txt",
             "【场景三】连续不合格 → 抛异常，不返回半成品\n"
             f"stage={exc.stage}\n"
             f"问题数={len(exc.last_issues)}\n\n" + detail + "\n")
        return f"连续失败被拒绝          stage={exc.stage}  问题{len(exc.last_issues)}条"
    raise AssertionError("应该抛 ScenarioCompileError，但没有抛")


def case_blocked() -> str:
    caller, calls = fake_llm(good_payload())
    result = compile_scenario("2028 年美国大选结果会怎样", llm=caller)
    assert result.scenario is None, "预测类议题不该生成场景"
    assert result.attempts == 0, "预测类议题不该调用模型"
    assert len(calls) == 0, "模型一次都不该被调用"
    save("offline_4_blocked.txt",
         "【场景四】预测类议题被规则层拦下，模型零调用\n"
         f"verdict={result.negotiability.get('verdict')}\n"
         f"matched_rules={result.negotiability.get('matched_rules')}\n"
         f"suggestions={result.negotiability.get('suggestions')}\n")
    return f"预测类议题被拦下        attempts=0  调用0次（不花钱）"


def main() -> int:
    cases = [
        ("一", case_once),
        ("二", case_repair),
        ("三", case_reject),
        ("四", case_blocked),
    ]
    failed = 0
    for label, func in cases:
        try:
            print(f"[{label}] {func()}")
        except Exception as exc:  # 不让单个场景中断整批
            failed += 1
            print(f"[{label}] 失败：{type(exc).__name__}: {exc}")

    print()
    if failed == 0:
        print("全部通过 ✅  证据已写入 proof/")
    else:
        print(f"{failed} 个场景失败 ❌")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

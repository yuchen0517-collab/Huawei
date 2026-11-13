import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.scenario.compiler import (
    ScenarioCompileError,
    compile_from_narrowing,
    compile_scenario,
    parse_scenario_json,
)

EXAMPLE_PATH = ROOT / "docs" / "contracts" / "scenario.example.json"


def load_example() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def valid_output() -> str:
    return json.dumps(load_example(), ensure_ascii=False)


def stub_llm(*outputs):
    """按顺序返回 outputs，返回 (caller, calls) 便于断言调用次数。"""
    calls = []

    def caller(messages, **_kwargs):
        calls.append(messages)
        index = min(len(calls) - 1, len(outputs) - 1)
        return outputs[index]

    return caller, calls


# ---------------------------------------------------------------------------
# 解析层
# ---------------------------------------------------------------------------
def test_parse_handles_code_fence():
    text = "```json\n" + valid_output() + "\n```"
    data = parse_scenario_json(text)
    assert data["scenario_id"] == load_example()["scenario_id"]


def test_parse_handles_trailing_comma_and_prose():
    text = "好的，下面是场景：\n" + valid_output().replace("}\n}", "},\n}") + "\n以上。"
    data = parse_scenario_json(text)
    assert "issues" in data


def test_parse_rejects_non_json():
    with pytest.raises(ScenarioCompileError) as excinfo:
        parse_scenario_json("我无法生成这个场景。")
    assert excinfo.value.stage == "parse"


# ---------------------------------------------------------------------------
# 正常路径
# ---------------------------------------------------------------------------
def test_compile_success_on_first_attempt():
    caller, calls = stub_llm(valid_output())
    result = compile_scenario("中美先进计算芯片的许可门槛与审批时限", llm=caller)

    assert result.ok is True
    assert result.attempts == 1
    assert len(calls) == 1
    assert result.scenario.scenario_id == load_example()["scenario_id"]
    assert result.problems == []


def test_compile_normalizes_verdict_to_direct():
    caller, _ = stub_llm(valid_output())
    result = compile_scenario("中美先进计算芯片的许可门槛与审批时限", llm=caller)
    # example.json 原文是 needs_narrowing，编译成功后应归一为 direct
    assert result.scenario.negotiability.verdict == "direct"
    assert result.negotiability["verdict"] == "direct"


# ---------------------------------------------------------------------------
# 重试修复
# ---------------------------------------------------------------------------
def test_repair_after_business_violation():
    # 权重仍是 0~1 的合法值，JSON Schema 放行；但三项之和变成 0.9，
    # 只有业务规则 R1 能拦住 —— 用它验证第二层闸门确实在工作。
    broken = copy.deepcopy(load_example())
    broken["private_state_by_party"]["cn"]["goals"][0]["weight"] = 0.3

    caller, calls = stub_llm(json.dumps(broken, ensure_ascii=False), valid_output())
    result = compile_scenario("中美先进计算芯片的许可门槛与审批时限", llm=caller)

    assert result.ok is True
    assert result.attempts == 2
    assert len(calls) == 2
    repair_text = calls[1][-1]["content"]
    assert "R1_weight_sum" in repair_text


def test_repair_after_schema_violation():
    broken = copy.deepcopy(load_example())
    broken.pop("title")

    caller, calls = stub_llm(json.dumps(broken, ensure_ascii=False), valid_output())
    result = compile_scenario("中美先进计算芯片的许可门槛与审批时限", llm=caller)

    assert result.ok is True
    assert result.attempts == 2
    assert "结构问题" in calls[1][-1]["content"]


def test_raises_after_max_retry():
    broken = copy.deepcopy(load_example())
    broken["private_state_by_party"]["cn"]["goals"][0]["weight"] = 0.3
    payload = json.dumps(broken, ensure_ascii=False)

    caller, calls = stub_llm(payload)
    with pytest.raises(ScenarioCompileError) as excinfo:
        compile_scenario("中美先进计算芯片的许可门槛与审批时限", llm=caller, max_retry=1)

    error = excinfo.value
    assert error.last_issues, "异常里必须带上最后一次的问题列表"
    assert error.raw_output is not None
    assert len(calls) == 2, "max_retry=1 应共调用 2 次"


# ---------------------------------------------------------------------------
# 可谈判性前置拦截：不该浪费模型调用
# ---------------------------------------------------------------------------
def test_unsupported_topic_never_calls_llm():
    def boom(_messages, **_kwargs):
        raise AssertionError("不可谈议题不应调用模型")

    result = compile_scenario("谁该为气候变暖负责", llm=boom)
    assert result.scenario is None
    assert result.attempts == 0
    assert result.negotiability["verdict"] == "unsupported"
    assert result.negotiability["suggestions"]


def test_needs_narrowing_topic_never_calls_llm():
    def boom(_messages, **_kwargs):
        raise AssertionError("多边议题不应直接调用模型")

    result = compile_scenario("六国数字税谈判", llm=boom)
    assert result.scenario is None
    assert result.negotiability["verdict"] == "needs_narrowing"
    assert result.negotiability["matched_rules"] == ["U4"]


# ---------------------------------------------------------------------------
# 多边收窄：走 compile_from_narrowing
# ---------------------------------------------------------------------------
def test_narrowing_generates_and_records_assumption():
    caller, _calls = stub_llm(valid_output())
    result = compile_from_narrowing(
        "六国数字税",
        "中美两国数字服务税税率差",
        llm=caller,
    )
    assert result.ok is True
    assert result.negotiability["narrowed_from"] == "六国数字税"
    assert result.negotiability["narrowing"] == "中美两国数字服务税税率差"

    last = result.scenario.assumptions[-1]
    assert "双边简化" in last.text
    assert "六国数字税" in last.text
    assert last.affects, "补写的假设必须覆盖 issue_id，否则过不了 R11"

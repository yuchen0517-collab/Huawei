"""BACKLOG #3 回归：自定义场景的对手 Prompt 与初始指数必须来自场景本身。

此前 `agents.json` 的 `_scenario` 与各方 cfg 都是《全球AI治理框架公约》题材，
加载 B 的芯片 / DST 场景时对手仍以 AI 治理代表的口吻发言，初始三项指数也
沿用 50/70/65。本文件锁定修复后的行为，并顺带守住「Prompt 不泄露对方私牌」。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api
import neg_cli as neg
from load_scenario_bridge import load_scenario
from prompt_context import build_scenario_prompt

client = TestClient(api.app, raise_server_exceptions=False)

BASE_DIR = Path(__file__).resolve().parent
CHIP_PATH = str(BASE_DIR / "scenario agent v2" / "data" / "scenarios" / "main_chip_controls.json")
CHIP_ID = "scn-chip-controls-0001"
DEFAULT_INDEXES = {"interest": 50, "image": 70, "trust": 65}
CHIP_US_INDEXES = {"interest": 31, "image": 55, "trust": 40}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.setenv("NEG_OFFLINE", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("NEG_SESSION_STORE_DIR", str(tmp_path))
    api.SESSIONS.clear()
    yield
    api.SESSIONS.clear()


def chip_scenario() -> dict:
    return load_scenario(CHIP_PATH)


def test_chip_prompt_is_built_from_the_scenario():
    prompt = build_scenario_prompt(neg.load_prompt_markdown(), chip_scenario(), "us")

    assert "全球AI治理" not in prompt
    assert "AI治理框架公约" not in prompt
    assert "芯片算力门槛" in prompt
    assert "关键矿产出口安排" in prompt
    # 场景里的 BATNA 与隐藏任务卡必须原样进入本方 Prompt
    assert "35 分（0–100 标尺）" in prompt
    assert "把稀土议题与芯片许可解耦" in prompt
    # 事实与假设附录，且不残留未替换占位符
    assert "可引用的事实" in prompt
    assert "教学假设" in prompt
    assert neg.find_unresolved_placeholders(prompt) == []


def test_chip_prompt_does_not_leak_opponent_private_cards():
    scenario = chip_scenario()
    cn_private = next(
        party for party in scenario["parties"] if party["id"] == "cn"
    )["private"]
    prompt = build_scenario_prompt(neg.load_prompt_markdown(), scenario, "us")

    assert cn_private["bottom_line"] not in prompt
    assert cn_private["batna_note"] not in prompt


def test_chip_prompt_lists_legal_clause_values():
    """模型曾把 '800TFLOPS(FP16)' 整串写进 option，被引擎判 VALUE_OUT_OF_RANGE。"""
    prompt = build_scenario_prompt(neg.load_prompt_markdown(), chip_scenario(), "us")

    assert "条款取值规则" in prompt
    assert "取值范围 100–5000" in prompt
    assert "步长 100" in prompt
    assert "填数字" in prompt
    assert "O1 / O2 / O3 / O4" in prompt


def test_chip_session_uses_scenario_prompt_and_initial_indexes():
    response = client.post(
        "/session",
        json={
            "scenario_id": CHIP_ID,
            "agent": "us",
            "scenario_path": "scenario agent v2/data/scenarios/main_chip_controls.json",
        },
    )
    assert response.status_code == 200, response.text
    record = api.SESSIONS[response.json()["session_id"]]
    assert record.initial_indexes == CHIP_US_INDEXES
    assert record.system_prompt != api.SYSTEM_PROMPTS["us"]
    assert "芯片算力门槛" in record.system_prompt


def test_default_scenario_keeps_handwritten_prompt_and_indexes():
    response = client.post("/session", json={"scenario_id": "ai_governance", "agent": "us"})
    assert response.status_code == 200, response.text
    record = api.SESSIONS[response.json()["session_id"]]
    assert record.initial_indexes == DEFAULT_INDEXES
    assert record.system_prompt == api.SYSTEM_PROMPTS["us"]

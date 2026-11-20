"""行动契约 v2 的 API／真实引擎集成验收。"""

from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import api
import negotiation_rules as rules
import scenario_overrides as overrides
from engine.core import RulesEngine
from load_scenario_bridge import load_scenario

ROOT = Path(__file__).resolve().parent
SCENARIO_DIR = ROOT / "scenario agent v2" / "data" / "scenarios"
CHIP_PATH = SCENARIO_DIR / "main_chip_controls.json"
DST_PATH = SCENARIO_DIR / "backup_dst_bilateral.json"
NOZOPA_PATH = SCENARIO_DIR / "no_zopa_variant.json"
CLIENT = TestClient(api.app, raise_server_exceptions=False)
COUNTER = itertools.count(1)

NUMERIC_PATCH = {
    "芯片算力门槛": {"option": 1000, "note": "双方红线内的算力门槛。"},
}
ENUM_PATCH = {
    "第三国再出口限制": {"option": "O2", "note": "仅对清单对象事前许可。"},
    "关键矿产出口安排": {"option": "O2", "note": "设置民用快速通道。"},
    "协议退出与救济安排": {"option": "O2", "note": "协商延长履约期，避开双方硬红线。"},
}
FULL_PATCH = {**NUMERIC_PATCH, **ENUM_PATCH}
DEFAULT_PATCH = {
    "全球算力资源分配": {
        "option": "以既有联盟实践为蓝本设立高风险 AI 出口管制的可核查机制",
        "note": "以对称、可核查的安排回应各方关切。",
    }
}
EXPECTED_ROLES = {
    "scn-chip-controls-0001": {
        "condition": "第三国再出口限制",
        "performance": "关键矿产出口安排",
        "exit": "协议退出与救济安排",
    },
    "scn-chip-controls-nozopa-0001": {
        "condition": "第三国再出口限制",
        "performance": "关键矿产出口安排",
        "exit": "协议退出与救济安排",
    },
    "scn-dst-cn-us-0001": {
        "condition": "征税门槛",
        "performance": "追溯适用期",
        "exit": "加征关税去留",
    },
}


@pytest.fixture(autouse=True)
def clean_api_sessions(monkeypatch, tmp_path):
    monkeypatch.setenv("NEG_OFFLINE", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("NEG_SESSION_STORE_DIR", str(tmp_path))
    api.SESSIONS.clear()
    yield
    api.SESSIONS.clear()


def make_engine(filename: str = "main_chip_controls.json") -> RulesEngine:
    scenario = overrides.apply_overrides(load_scenario(SCENARIO_DIR / filename))
    scenario["action_points_per_round"] = 10
    scenario["deadlock_rounds"] = 99
    scenario["max_rounds"] = 50
    return RulesEngine(scenario, f"card-integration-{next(COUNTER)}")


def make_action(
    actor: str,
    action_type: str,
    patch_value: dict | None = None,
    card_id: str | None = None,
    payload: dict | None = None,
) -> dict:
    action = {
        "action_id": f"card-{next(COUNTER):04d}",
        "actor": actor,
        "action_type": action_type,
        "card_id": card_id,
        "offer_patch": copy.deepcopy(patch_value or {}),
        "conditions": [],
        "expected_effect": "契约集成测试",
        "public_message": "契约集成测试行动。",
    }
    if payload is not None:
        action["card_payload"] = copy.deepcopy(payload)
    return action


def submit_ok(engine: RulesEngine, action: dict) -> list:
    ok, code, message, events = engine.submit_action(action)
    assert ok, f"{action['action_type']} 应通过，实际为 {code}: {message}"
    assert code is None
    assert events
    return events


def submit_rejected(engine: RulesEngine, action: dict, expected_code: str) -> str:
    before = engine.state.to_archive_dict()
    ok, code, message, events = engine.submit_action(action)
    assert not ok
    assert code == expected_code
    assert events == []
    assert engine.state.to_archive_dict() == before
    return message


def new_session(scenario_path: Path | None = None) -> str:
    if scenario_path is None:
        body = {"scenario_id": "ai_governance", "agent": "us"}
    else:
        scenario_id = load_scenario(scenario_path)["scenario_id"]
        body = {
            "scenario_id": scenario_id,
            "agent": "us",
            "scenario_path": str(scenario_path),
        }
    response = CLIENT.post("/session", json=body)
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def post_default_action(session_id: str, action: dict):
    payload = {
        "conditions": [],
        "expected_effect": "验证卡牌字段透传。",
        "public_message": "我方按行动契约 v2 提交本手行动。",
        **copy.deepcopy(action),
        "client_action_id": f"req-card-{next(COUNTER)}",
        "base_version": 0,
    }
    return CLIENT.post(f"/session/{session_id}/action", json=payload)


def available_by_id(engine: RulesEngine, actor: str = "cn") -> dict[str, dict]:
    return {
        item["id"]: item
        for item in rules.available_cards(actor, engine.state, rules.load_registry())
    }


def test_api_forwards_card_id_to_engine():
    session_id = new_session()
    response = post_default_action(
        session_id,
        {
            "action_type": "offer",
            "card_id": "anchor_offer",
            "offer_patch": DEFAULT_PATCH,
            "actor": "us",
            "action_id": "client-forged-id",
        },
    )
    assert response.status_code == 200, response.text
    mine = response.json()["action_history"][0]
    assert mine["action_id"] == "a000001"
    assert mine["actor"] == "cn"
    assert mine["card_id"] == "anchor_offer"
    engine_event = api.SESSIONS[session_id].engine.state.public_events[0]
    assert engine_event["card_id"] == "anchor_offer"


def test_api_forwards_card_payload_to_contract(monkeypatch):
    seen = []
    original = rules.check_card_action

    def spy(action, state, scenario, registry=None):
        seen.append(copy.deepcopy(action))
        return original(action, state, scenario, registry)

    monkeypatch.setattr(rules, "check_card_action", spy)
    session_id = new_session()
    payload = {"text": "我方承诺继续公开磋商并回应条款关切。"}
    response = post_default_action(
        session_id,
        {
            "action_type": "statement",
            "card_id": "public_commitment",
            "card_payload": payload,
            "offer_patch": {},
        },
    )
    assert response.status_code == 200, response.text
    mine = next(action for action in seen if action["action_id"] == "a000001")
    assert mine["card_id"] == "public_commitment"
    assert mine["card_payload"] == payload


def test_quote_card_requires_offer_patch():
    engine = make_engine()
    message = submit_rejected(
        engine,
        make_action("cn", "offer", card_id="anchor_offer"),
        "CARD_REQUIRES_QUOTE_BOARD",
    )
    assert "anchor_offer" in message


def test_non_quote_card_forbids_offer_patch():
    engine = make_engine()
    submit_rejected(
        engine,
        make_action(
            "cn", "probe", NUMERIC_PATCH, "probe_priority", {"target": "us"}
        ),
        "CARD_FORBIDS_QUOTE_BOARD",
    )


def test_card_payload_missing_required_field():
    engine = make_engine()
    message = submit_rejected(
        engine,
        make_action("cn", "probe", card_id="probe_priority"),
        "CARD_PAYLOAD_MISSING",
    )
    assert "probe_priority" in message
    assert "缺少载荷" in message


def test_card_cooling_rejects_reuse():
    engine = make_engine()
    submit_ok(
        engine,
        make_action("cn", "probe", card_id="probe_priority", payload={"target": "us"}),
    )
    engine.next_round()
    message = submit_rejected(
        engine,
        make_action("cn", "probe", card_id="probe_priority", payload={"target": "us"}),
        "CARD_COOLING",
    )
    assert "第 4 回合" in message


def test_card_use_limit_rejects_exhausted_card():
    engine = make_engine()
    submit_ok(
        engine,
        make_action("cn", "statement", card_id="adjourn", payload={"option": "休会一轮"}),
    )
    submit_rejected(
        engine,
        make_action("cn", "statement", card_id="adjourn", payload={"option": "再次休会"}),
        "CARD_EXHAUSTED",
    )


def test_pending_response_deferral_limit():
    engine = make_engine()
    submit_ok(engine, make_action("cn", "offer", NUMERIC_PATCH))
    submit_ok(
        engine,
        make_action("us", "probe", card_id="probe_priority", payload={"target": "cn"}),
    )
    submit_rejected(
        engine,
        make_action("us", "probe", card_id="verify_capacity", payload={"target": "cn"}),
        "PENDING_RESPONSE_EXCEEDED",
    )


def test_self_revision_is_locked_until_response():
    engine = make_engine()
    submit_ok(engine, make_action("cn", "offer", NUMERIC_PATCH))
    submit_rejected(
        engine,
        make_action("cn", "counter_offer", NUMERIC_PATCH),
        "SELF_REVISION_LOCKED",
    )


def test_empty_offer_is_rejected_before_legacy_validation():
    engine = make_engine()
    submit_rejected(engine, make_action("cn", "offer"), "EMPTY_TURN")


def test_available_cards_initially_available_with_empty_reason():
    engine = make_engine()
    anchor = available_by_id(engine)["anchor_offer"]
    assert anchor["available"] is True
    assert anchor["reason"] == ""
    assert anchor["quote_board"] is True


def test_available_cards_reports_cooldown_reason():
    engine = make_engine()
    submit_ok(engine, make_action("cn", "offer", NUMERIC_PATCH, "anchor_offer"))
    engine.next_round()
    anchor = available_by_id(engine)["anchor_offer"]
    assert anchor["available"] is False
    assert anchor["reason"] == "冷却至第 3 回合"


def test_available_cards_reports_exhausted_reason():
    engine = make_engine()
    submit_ok(
        engine,
        make_action("cn", "statement", card_id="adjourn", payload={"option": "休会一轮"}),
    )
    adjourn = available_by_id(engine)["adjourn"]
    assert adjourn["available"] is False
    assert adjourn["reason"] == "本局限用 1 次，已用尽"


@pytest.mark.parametrize("action_type", ["offer", "counter_offer", "conditional_exchange"])
def test_basic_quote_actions_need_no_card(action_type):
    engine = make_engine()
    events = submit_ok(engine, make_action("cn", action_type, NUMERIC_PATCH))
    assert events[0]["card_id"] is None
    assert events[0]["offer_patch"] == NUMERIC_PATCH


def test_basic_accept_needs_no_card():
    engine = make_engine()
    submit_ok(engine, make_action("cn", "offer", FULL_PATCH))
    submit_ok(engine, make_action("us", "accept"))
    assert engine.state.status == "ended"
    assert engine.state.terminal["type"] == "FULL_AGREEMENT"


def test_basic_reject_needs_no_card():
    engine = make_engine()
    submit_ok(engine, make_action("cn", "offer", NUMERIC_PATCH))
    events = submit_ok(engine, make_action("us", "reject"))
    assert events[0]["action_type"] == "reject"
    assert events[0]["card_id"] is None


def test_basic_walk_away_needs_no_card():
    engine = make_engine()
    submit_ok(engine, make_action("us", "walk_away"))
    assert engine.state.status == "ended"
    assert engine.state.terminal["type"] == "WITHDRAWAL"


def test_pending_hint_projection_matches_engine_judgement():
    session_id = new_session()
    response = post_default_action(
        session_id,
        {"action_type": "offer", "card_id": "anchor_offer", "offer_patch": DEFAULT_PATCH},
    )
    assert response.status_code == 200, response.text
    rec = api.SESSIONS[session_id]
    expected = rules.pending_hint(rec.engine.state, rec.engine.scenario)
    assert response.json()["pending_hint"] == expected
    assert expected["responder"] == "cn"
    assert expected["version"] == 2
    assert expected["deferrals_left"] == 1
    assert expected["must_resolve"] is False


def test_clause_role_is_enforced_and_valid_patch_passes():
    engine = make_engine()
    message = submit_rejected(
        engine,
        make_action("cn", "offer", NUMERIC_PATCH, "effective_condition"),
        "CARD_PAYLOAD_INVALID",
    )
    assert "第三国再出口限制" in message
    submit_ok(
        engine,
        make_action(
            "cn", "offer", {**NUMERIC_PATCH, "第三国再出口限制": ENUM_PATCH["第三国再出口限制"]},
            "effective_condition",
        ),
    )
    assert engine.state.offers[-1].clauses["第三国再出口限制"]["option"] == "O2"


def test_apply_overrides_preserves_declared_roles_and_input():
    scenario = load_scenario(CHIP_PATH)
    declared = {"condition": "第三国再出口限制"}
    scenario["clause_roles"] = declared
    original = copy.deepcopy(scenario)
    result = overrides.apply_overrides(scenario)
    assert result is not scenario
    assert result["clause_roles"] == declared
    assert result["action_points_per_round"] == 5
    assert result["deadlock_rounds"] == 3
    assert scenario == original


def test_apply_overrides_rejects_unknown_declared_role_clause():
    """场景自带的 clause_roles 也要校验：拼错或指向已删条款必须报错。

    B 侧新场景直接声明 clause_roles（issue_id），适配层已映射为条款名，
    覆盖层负责最后一道存在性校验，避免坏名字流到卡牌校验和前端。
    """
    scenario = load_scenario(CHIP_PATH)
    scenario["clause_roles"] = {"condition": "不存在的条款"}
    with pytest.raises(ValueError) as caught:
        overrides.apply_overrides(scenario)
    assert str(caught.value) == (
        "场景 'scn-chip-controls-0001' 的 clause_roles.condition "
        "指向不存在的条款 '不存在的条款'"
    )


def test_apply_overrides_fallback_rejects_unknown_role_clause(monkeypatch):
    """场景未声明 clause_roles 时走内置兜底表，兜底表同样要校验。"""
    monkeypatch.setitem(
        overrides.CLAUSE_ROLES_BY_SCENARIO,
        "scn-chip-controls-0001",
        {"condition": "不存在的条款"},
    )
    scenario = load_scenario(CHIP_PATH)
    scenario.pop("clause_roles", None)
    with pytest.raises(ValueError) as caught:
        overrides.apply_overrides(scenario)
    assert str(caught.value) == (
        "场景 'scn-chip-controls-0001' 的 clause_roles.condition "
        "指向不存在的条款 '不存在的条款'"
    )


def test_apply_overrides_uses_deepcopy():
    scenario = load_scenario(CHIP_PATH)
    with patch.object(overrides.copy, "deepcopy", wraps=copy.deepcopy) as mocked:
        result = overrides.apply_overrides(scenario)
    mocked.assert_called_once_with(scenario)
    assert result == scenario | {
        "clause_roles": EXPECTED_ROLES[scenario["scenario_id"]],
        "action_points_per_round": 5,
        "deadlock_rounds": 3,
        "action_contract_version": 2,
    }


@pytest.mark.parametrize(
    "path",
    [CHIP_PATH, DST_PATH, NOZOPA_PATH],
    ids=["chip", "dst", "nozopa"],
)
def test_three_real_scenarios_receive_valid_overrides(path):
    scenario = load_scenario(path)
    original = copy.deepcopy(scenario)
    result = overrides.apply_overrides(scenario)
    scenario_id = result["scenario_id"]
    assert result["clause_roles"] == EXPECTED_ROLES[scenario_id]
    assert set(result["clause_roles"].values()) <= {
        clause["name"] for clause in result["clauses"]
    }
    assert result["action_points_per_round"] == (5 if len(result["clauses"]) >= 4 else 4)
    assert result["deadlock_rounds"] == 3
    assert scenario == original


def test_role_clause_returns_mapping_or_none():
    scenario = overrides.apply_overrides(load_scenario(CHIP_PATH))
    assert overrides.role_clause(scenario, "condition") == "第三国再出口限制"
    assert overrides.role_clause(scenario, "unknown") is None
    assert overrides.role_clause({}, "condition") is None


def test_projection_available_cards_contains_target_clause():
    session_id = new_session(CHIP_PATH)
    response = CLIENT.get(f"/session/{session_id}/state")
    assert response.status_code == 200, response.text
    state = response.json()
    cards = {item["id"]: item for item in state["available_cards"]}
    assert len(cards) == 14
    assert cards["effective_condition"]["target_clause"] == "第三国再出口限制"
    assert cards["performance_node"]["target_clause"] == "关键矿产出口安排"
    assert cards["exit_clause"]["target_clause"] == "协议退出与救济安排"
    assert cards["anchor_offer"]["target_clause"] is None
    assert state["action_points_per_round"] == 5
    assert state["pending_hint"] is None


def test_real_scenario_three_card_flow_and_projection():
    session_id = new_session(CHIP_PATH)
    rec = api.SESSIONS[session_id]
    engine = rec.engine
    submit_ok(engine, make_action("cn", "offer", NUMERIC_PATCH, "anchor_offer"))
    submit_ok(
        engine,
        make_action(
            "us", "counter_offer",
            {"第三国再出口限制": ENUM_PATCH["第三国再出口限制"]},
            "effective_condition",
        ),
    )
    submit_ok(
        engine,
        make_action("cn", "probe", card_id="probe_priority", payload={"target": "us"}),
    )
    state = api.project_state(rec)
    assert [event["card_id"] for event in state["action_history"]] == [
        "anchor_offer", "effective_condition", "probe_priority",
    ]
    cards = {item["id"]: item for item in state["available_cards"]}
    assert cards["anchor_offer"]["available"] is False
    assert cards["anchor_offer"]["reason"] == "冷却至第 3 回合"
    assert cards["probe_priority"]["available"] is False
    assert cards["probe_priority"]["reason"] == "冷却至第 4 回合"
    assert cards["effective_condition"]["available"] is True
    assert cards["effective_condition"]["target_clause"] == "第三国再出口限制"
    assert state["pending_hint"]["responder"] == "cn"
    assert state["pending_hint"]["deferrals_used"] == 1
    assert state["pending_hint"]["deferrals_left"] == 0
    assert state["pending_hint"]["must_resolve"] is True
    print(json.dumps({
        "available_cards": state["available_cards"],
        "pending_hint": state["pending_hint"],
    }, ensure_ascii=False, indent=2))


def test_deadlock_requires_three_rounds_without_either_side_offering():
    scenario = overrides.apply_overrides(load_scenario(CHIP_PATH))
    scenario["action_points_per_round"] = 10
    scenario["max_rounds"] = 50
    engine = RulesEngine(scenario, "deadlock-integration")
    submit_ok(engine, make_action("cn", "offer", NUMERIC_PATCH))
    assert engine.next_round()["rounds_without_offer"] == 0
    assert engine.next_round()["rounds_without_offer"] == 1
    assert engine.next_round()["rounds_without_offer"] == 2
    assert engine.state.status == "active"
    assert engine.next_round()["rounds_without_offer"] == 3
    assert engine.state.status == "ended"
    assert engine.state.terminal["type"] == "DEADLOCK"


def test_installed_schema_is_v2_and_card_payload_is_optional():
    current = json.loads((ROOT / "action_schema.json").read_text(encoding="utf-8-sig"))["schema"]
    v2 = json.loads((ROOT / "action_schema_v2.json").read_text(encoding="utf-8-sig"))
    assert current == v2
    assert "card_payload" not in current["required"]
    assert (ROOT / "action_schema_v1.json").is_file()
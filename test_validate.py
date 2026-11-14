import copy
import json
from types import SimpleNamespace

import pytest

import neg_cli as neg


def valid_payload():
    return {
        "action": {
            "action_type": "offer",
            "offer_patch": {
                "全球算力资源分配": {
                    "option": "附带可核查机制",
                    "note": "以对称核查推动形成可执行安排。",
                }
            },
            "conditions": ["核查安排对双方对称适用。"],
            "expected_effect": "推动双方就算力分配形成共同文本。",
            "reason_public": "以可核查方案回应各方安全关切。",
        },
        "public_message": "我方提出附带对称核查机制的算力分配方案，愿继续听取各方意见。",
        "mood": "审慎推进",
        "round_summary": "中方提出可核查的算力方案。",
    }


@pytest.mark.parametrize("action_type", sorted(neg.OFFER_ACTION_TYPES))
def test_offer_actions_accept_structured_patch(action_type):
    payload = valid_payload()
    payload["action"]["action_type"] = action_type
    original = copy.deepcopy(payload)
    checked, warnings = neg.validate_action(payload)
    assert checked["action"] == original["action"]
    assert checked["public_message"] == original["public_message"]
    assert payload == original
    assert warnings == []


@pytest.mark.parametrize(
    "action_type",
    ["accept", "reject", "walk_away", "probe", "statement"],
)
def test_non_offer_actions_require_empty_patch(action_type):
    payload = valid_payload()
    payload["action"].update(action_type=action_type, offer_patch={})
    checked, warnings = neg.validate_action(payload)
    assert checked["action"]["action_type"] == action_type
    assert checked["action"]["offer_patch"] == {}
    assert warnings == []


@pytest.mark.parametrize(
    ("name", "mutate", "error_marker"),
    [
        ("顶层不是对象", lambda obj: obj.clear(), "action"),
        ("action 不是对象", lambda obj: obj.update(action="offer"), "action"),
        ("缺 action_type", lambda obj: obj["action"].pop("action_type"), "action_type"),
        ("未知 action_type", lambda obj: obj["action"].update(action_type="offerr"), "action_type"),
        ("缺 offer_patch", lambda obj: obj["action"].pop("offer_patch"), "offer_patch"),
        ("offer_patch 为 null", lambda obj: obj["action"].update(offer_patch=None), "offer_patch"),
        ("offer_patch 为数组", lambda obj: obj["action"].update(offer_patch=[]), "offer_patch"),
        (
            "accept 携带报价",
            lambda obj: obj["action"].update(action_type="accept"),
            "offer_patch",
        ),
        ("缺 public_message", lambda obj: obj.pop("public_message"), "public_message"),
        ("public_message 空白", lambda obj: obj.update(public_message="   "), "public_message"),
        ("public_message 非字符串", lambda obj: obj.update(public_message=123), "public_message"),
    ],
)
def test_invalid_v2_contract_is_rejected_without_mutating_input(name, mutate, error_marker):
    payload = valid_payload()
    mutate(payload)
    snapshot = copy.deepcopy(payload)
    with pytest.raises(ValueError) as caught:
        neg.validate_action(payload)
    assert error_marker in str(caught.value), name
    assert payload == snapshot, name


def test_non_object_top_level_is_rejected():
    with pytest.raises(ValueError, match="顶层不是 JSON 对象"):
        neg.validate_action(["action", "public_message"])


def test_validate_returns_independent_copy_and_preserves_v2_action_fields():
    payload = valid_payload()
    checked, _ = neg.validate_action(payload)
    checked["action"]["offer_patch"]["全球算力资源分配"]["option"] = "修改副本"
    checked["public_message"] = "修改副本发言"
    assert payload["action"]["offer_patch"]["全球算力资源分配"]["option"] == "附带可核查机制"
    assert payload["public_message"].startswith("我方提出")
    assert checked["action"]["reason_public"] == payload["action"]["reason_public"]


def test_v11_response_only_payload_is_rejected():
    legacy = {
        "response": "这是 v1.1 的纯发言字段。",
        "private_note": "这是 v1.1 的私有备注。",
        "indexes_update": {"interest_delta": 3},
    }
    with pytest.raises(ValueError, match="v1.1"):
        neg.validate_action(legacy)


def test_v2_validation_does_not_settle_legacy_indexes():
    payload = valid_payload()
    payload["indexes_update"] = {"interest_delta": 99, "trust_delta": -99}
    checked, _ = neg.validate_action(payload)
    assert checked["indexes_update"] == payload["indexes_update"]
    assert "interest" not in checked and "trust" not in checked


def test_warnings_cover_short_speech_private_leak_and_missing_metadata():
    payload = valid_payload()
    payload["public_message"] = "我的底牌是"
    payload.pop("mood")
    payload["round_summary"] = " "
    checked, warnings = neg.validate_action(payload)
    assert checked["public_message"] == "我的底牌是"
    assert any("基本没有实质内容" in warning for warning in warnings)
    assert any("疑似泄露隐藏任务卡" in warning for warning in warnings)
    assert "缺少 mood" in warnings
    assert "缺少 round_summary" in warnings


def test_repaired_marker_is_removed_and_reported():
    payload = valid_payload()
    payload["_json_repaired"] = True
    checked, warnings = neg.validate_action(payload)
    assert "_json_repaired" not in checked
    assert any("自动拼合修复" in warning for warning in warnings)


def test_extract_json_handles_v2_fence_and_trailing_commas():
    raw = """```json
    {
      "action": {"action_type": "statement", "offer_patch": {},},
      "public_message": "公开发言",
      "mood": "平和",
      "round_summary": "程序性表态",
    }
    ```"""
    parsed = neg.extract_json(raw)
    assert parsed["action"]["action_type"] == "statement"
    assert parsed["action"]["offer_patch"] == {}
    assert parsed["round_summary"] == "程序性表态"


def test_extract_json_salvages_prematurely_closed_v2_object():
    broken = (
        '{"action": {"action_type": "statement", "offer_patch": {}}, '
        '"public_message": "公开发言"}'
        ', "mood": "陷入僵局", "round_summary": "继续磋商"}'
    )
    parsed = neg.extract_json(broken)
    assert parsed["action"]["action_type"] == "statement"
    assert parsed["mood"] == "陷入僵局"
    assert parsed["round_summary"] == "继续磋商"
    assert parsed["_json_repaired"] is True


@pytest.mark.parametrize("raw", ["没有 JSON 对象", '{"action": "statement", "mood": }'])
def test_extract_json_rejects_unrecoverable_input(raw):
    with pytest.raises(ValueError) as caught:
        neg.extract_json(raw)
    assert "JSON" in str(caught.value) or "大括号" in str(caught.value)


def test_system_prompt_uses_v2_contract_and_only_own_hidden_card():
    agents = neg.load_agents()
    scenario = agents["_scenario"]
    prompt = neg.build_system_prompt(
        neg.load_prompt_markdown(), agents["us"], scenario, side="us"
    )
    assert scenario["name"] in prompt
    assert scenario["agenda"][0] in prompt
    assert '"action"' in prompt and '"public_message"' in prompt
    assert "player_indexes_update" not in prompt
    assert agents["us"]["hidden_task_card"] in prompt
    assert "全球AI治理研究院" not in prompt
    assert neg.find_unresolved_placeholders(prompt) == []


def test_three_consecutive_invalid_json_responses_return_none(monkeypatch):
    calls = []

    def invalid_json(messages, json_mode=True, temperature=0.7):
        calls.append({"messages": messages, "json_mode": json_mode})
        return "这不是 JSON", "stop"

    monkeypatch.setattr(neg, "call_deepseek", invalid_json)
    monkeypatch.setattr(neg.time, "sleep", lambda _: None)
    messages = [{"role": "system", "content": "原始提示"}, {"role": "user", "content": "请行动"}]
    args = SimpleNamespace(no_json_mode=False, temperature=0.7)
    obj, raw, finish = neg.call_with_retry(messages, "原始提示", args)
    assert obj is None
    assert raw == "这不是 JSON"
    assert finish == "stop"
    assert len(calls) == 3
    assert [call["json_mode"] for call in calls] == [True, True, False]
    assert calls[0]["messages"][0]["content"] == "原始提示"
    assert all(neg.RETRY_NUDGE in call["messages"][0]["content"] for call in calls[1:])


def test_json_retry_recovers_on_second_response(monkeypatch):
    responses = iter([("bad json", "stop"), (json.dumps(valid_payload()), "stop")])
    monkeypatch.setattr(neg, "call_deepseek", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(neg.time, "sleep", lambda _: None)
    args = SimpleNamespace(no_json_mode=False, temperature=0.7)
    obj, _, finish = neg.call_with_retry(
        [{"role": "system", "content": "提示"}, {"role": "user", "content": "行动"}],
        "提示",
        args,
    )
    assert obj["action"]["action_type"] == "offer"
    assert obj["public_message"].startswith("我方提出")
    assert finish == "stop"

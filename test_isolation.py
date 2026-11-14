import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api
import neg_cli as neg
from load_scenario import make_scenario
from multi_agent import CountryAgent

BASE_DIR = Path(__file__).resolve().parent
AGENTS = json.loads((BASE_DIR / "agents.json").read_text(encoding="utf-8-sig"))
CN_MARKERS = [task["text"] for task in AGENTS["_scenario"]["player"]["hidden_tasks"]]
CN_MARKERS.append("全球AI治理研究院")
US_MARKERS = [
    AGENTS["us"]["hidden_task_card"],
    "为技术监控铺路",
    "确保对中国的 AI 技术限制不被谈判决议削弱",
]


def _assert_without(payload, markers, location):
    serialized = json.dumps(payload, ensure_ascii=False)
    for marker in markers:
        if marker in serialized:
            print(f"FAIL {location}: 发现私有信息 {marker!r}")
            pytest.fail(f"{location} 泄露私有信息：{marker}")


def _assert_messages_without(messages, markers, location):
    for index, message in enumerate(messages):
        _assert_without(message, markers, f"{location}.messages[{index}]({message.get('role')})")


def _response(actor, round_no):
    label = "美国" if actor == "us" else "中国"
    return {
        "action": {
            "action_type": "counter_offer" if actor == "us" else "offer",
            "offer_patch": {
                "全球算力资源分配": {
                    "option": "附带可核查机制",
                    "note": f"{label}第 {round_no} 轮公开方案说明。",
                }
            },
            "conditions": [],
            "expected_effect": "推动双方继续讨论可核查的算力安排。",
        },
        "public_message": f"{label}第 {round_no} 轮公开发言。",
        "private_note": f"{actor}-internal-round-{round_no}",
        "mood": "审慎推进",
        "round_summary": f"第 {round_no} 轮提出公开方案",
    }


def _check_engine_snapshots(engine, extra_cn=(), extra_us=()):
    for viewer, own_markers, other_markers in (
        ("us", US_MARKERS + list(extra_us), CN_MARKERS + list(extra_cn)),
        ("cn", CN_MARKERS + list(extra_cn), US_MARKERS + list(extra_us)),
    ):
        snapshot = engine.public_state(viewer)
        assert set(snapshot["private_state_by_party"]) == {viewer}
        _assert_without(snapshot, other_markers, f"engine.to_public_dict({viewer!r})")
        assert any(
            marker in json.dumps(snapshot["private_state_by_party"], ensure_ascii=False)
            for marker in own_markers
        ), "测试夹具必须确认己方私有状态确实存在"
    anonymous = engine.public_state()
    assert anonymous["private_state_by_party"] == {}
    _assert_without(
        anonymous,
        CN_MARKERS + US_MARKERS + list(extra_cn) + list(extra_us),
        "engine.to_public_dict('')",
    )


@pytest.fixture(autouse=True)
def clean_sessions(monkeypatch):
    monkeypatch.setenv("NEG_OFFLINE", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    api.SESSIONS.clear()
    yield
    api.SESSIONS.clear()


def test_three_round_offline_agent_messages_and_engine_are_isolated():
    scenario = AGENTS["_scenario"]
    player = scenario["player"]
    agents = {
        "us": CountryAgent("us", AGENTS["us"]["label"]),
        "cn": CountryAgent("cn", player["label"]),
    }
    prompts = {
        "us": neg.build_system_prompt(
            neg.load_prompt_markdown(), AGENTS["us"], scenario, side="us"
        ),
        "cn": "你是中国的独立国家 Agent。\n本方私有配置（仅你可见）：\n"
        + json.dumps(player, ensure_ascii=False),
    }
    _assert_without(prompts["us"], CN_MARKERS, "美国 Agent.system_prompt")
    _assert_without(prompts["cn"], US_MARKERS, "中国 Agent.system_prompt")
    assert "为技术监控铺路" in prompts["us"]
    assert "全球AI治理研究院" in prompts["cn"]

    engine = api.RulesEngine(make_scenario(), "agent-isolation-three-rounds")
    public_messages = []
    captured = {"us": [], "cn": []}
    samples = {key: [_response(key, n) for n in range(1, 4)] for key in agents}

    for round_no in range(1, 4):
        for key in ("us", "cn"):
            result = agents[key].act(
                system_prompt=prompts[key],
                public_messages=copy.deepcopy(public_messages),
                turn_input=f"第 {round_no} 轮，请根据公共会场记录给出本轮行动。",
                offline_responses=samples[key],
            )
            captured[key].append(copy.deepcopy(result["messages"]))
            other = "cn" if key == "us" else "us"
            _assert_messages_without(
                result["messages"],
                CN_MARKERS if other == "cn" else US_MARKERS,
                f"{agents[key].label} Agent 第 {round_no} 轮",
            )

            obj = result["obj"]
            flat = copy.deepcopy(obj["action"])
            flat.update({
                "action_id": f"{key}-round-{round_no}",
                "actor": key,
                "card_id": None,
                "public_message": obj["public_message"],
            })
            ok, code, detail, _ = engine.submit_action(flat)
            assert ok, (key, round_no, code, detail)
            agents[key].remember(round_no, obj)
            public_messages.append({
                "role": "agent" if key == "us" else "player",
                "sender": agents[key].label,
                "text": obj["public_message"],
                "action": copy.deepcopy(obj["action"]),
            })
            _check_engine_snapshots(engine)
        engine.next_round()

    assert engine.state.round == 4
    assert len(public_messages) == 6
    assert agents["us"].turns == agents["cn"].turns == 3
    assert len(captured["us"]) == len(captured["cn"]) == 3
    for key, other_markers in (("us", CN_MARKERS), ("cn", US_MARKERS)):
        for round_no, messages in enumerate(captured[key], start=1):
            _assert_messages_without(
                messages, other_markers, f"最终复核 {key} 第 {round_no} 轮"
            )
            for message in public_messages:
                _assert_without(
                    message,
                    ["us-internal-round-" if key == "cn" else "cn-internal-round-"],
                    f"公共记录 {message['sender']}",
                )

    second_round_cn_context = captured["cn"][1][1]["content"]
    assert (
        "美国[反报价]：全球算力资源分配→附带可核查机制｜"
        '发言："美国第 1 轮公开发言。"'
    ) in second_round_cn_context
    for key in agents:
        for item in agents[key].private_memory:
            assert set(item) == {"round", "action", "public_message", "mood"}
            assert "response" not in item and "private_note" not in item
    print("PASS: 中美离线 3 轮的 Agent messages、公共记录和引擎快照均无对方私有底牌")


def test_api_responses_use_public_projection_without_private_markers(monkeypatch):
    viewers = []
    original = api.RulesEngine.public_state

    def spy_public_state(self, viewer=""):
        viewers.append(viewer)
        return original(self, viewer)

    monkeypatch.setattr(api.RulesEngine, "public_state", spy_public_state)
    client = TestClient(api.app, raise_server_exceptions=False)
    created = client.post("/session", json={"scenario_id": "ai_governance", "agent": "us"})
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]
    _assert_without(created.json(), CN_MARKERS + US_MARKERS, "POST /session")

    rec = api.SESSIONS[session_id]
    cn_sentinel = "CN_API_PRIVATE_SENTINEL"
    us_sentinel = "US_API_PRIVATE_SENTINEL"
    rec.engine.state.private_state_by_party["cn"]["test_sentinel"] = cn_sentinel
    rec.engine.state.private_state_by_party["us"]["test_sentinel"] = us_sentinel
    all_markers = CN_MARKERS + US_MARKERS + [cn_sentinel, us_sentinel]

    api_start = len(viewers)
    state_response = client.get(f"/session/{session_id}/state")
    assert state_response.status_code == 200, state_response.text
    assert set(state_response.json()) == set(api.PUBLIC_STATE_KEYS)
    _assert_without(state_response.json(), all_markers, "GET /session/{id}/state")

    action_response = client.post(f"/session/{session_id}/action", json={
        "action_type": "statement",
        "offer_patch": {},
        "conditions": [],
        "expected_effect": "",
        "public_message": "本轮仅作公开程序性表态，继续磋商。",
        "client_action_id": "isolation-api-action-1",
        "base_version": 0,
    })
    assert action_response.status_code == 200, action_response.text
    assert set(action_response.json()) == set(api.PUBLIC_STATE_KEYS)
    _assert_without(action_response.json(), all_markers, "POST /session/{id}/action")
    api_viewers = viewers[api_start:]
    assert api_viewers and set(api_viewers) == {"cn"}

    _check_engine_snapshots(rec.engine, extra_cn=[cn_sentinel], extra_us=[us_sentinel])
    serialized_response = json.dumps(action_response.json(), ensure_ascii=False)
    assert "private_state_by_party" not in serialized_response
    print("PASS: API 创建、查询、行动响应均经 public_state 投影且不序列化私有底牌")


def test_memory_stores_full_action_and_keeps_truncation_windows():
    agent = CountryAgent("us", "美国")
    for round_no in range(1, 14):
        obj = _response("us", round_no)
        agent.remember(round_no, obj)
        if round_no == 13:
            obj["action"]["offer_patch"]["全球算力资源分配"]["option"] = "事后篡改"

    assert agent.turns == 13
    assert len(agent.private_memory) == 12
    assert [item["round"] for item in agent.private_memory] == list(range(2, 14))
    last = agent.private_memory[-1]
    assert last["action"] == _response("us", 13)["action"]
    assert last["action"]["offer_patch"]["全球算力资源分配"]["option"] == "附带可核查机制"
    assert last["public_message"] == "美国第 13 轮公开发言。"
    assert "response" not in last and "private_note" not in last

    public_messages = []
    for number in range(1, 41):
        public_messages.append({
            "role": "agent",
            "sender": "美国",
            "text": f"公开发言{number}",
            "action": {
                "action_type": "counter_offer",
                "offer_patch": {
                    "芯片算力门槛": {"option": 1000 + number, "note": "数值条款摘要"}
                },
            },
        })
    context = agent._context(public_messages, "继续谈判")
    assert '美国[反报价]：芯片算力门槛→1040｜发言："公开发言40"' in context
    assert '发言："公开发言5"' in context
    assert '发言："公开发言4"' not in context
    assert "第8轮" in context and "第13轮" in context
    assert "第7轮" not in context
    assert "事后篡改" not in context
    print("PASS: 完整 action 深拷贝存储，公共 36、记忆读取 6、记忆存储 12 窗口不变")


def test_memory_formatting_and_offline_error_edges():
    agent = CountryAgent("us", "美国")
    public_messages = [
        {"role": "system", "sender": "系统", "text": "不应进入公共会场"},
        {"role": "agent", "sender": "空发言", "text": ""},
        {"role": "agent", "sender": "旧记录", "text": "兼容无行动记录"},
        {
            "role": "agent",
            "sender": "非法行动",
            "text": "未知行动类型",
            "action": {"action_type": "not-real", "offer_patch": {}},
        },
        {
            "role": "agent",
            "sender": "非法条款",
            "text": "条款结构异常",
            "action": {"action_type": "statement", "offer_patch": []},
        },
        {
            "role": "agent",
            "sender": "空选项",
            "text": "选项为空",
            "action": {
                "action_type": "offer",
                "offer_patch": {"议题": {"option": None, "note": "无效"}},
            },
        },
    ]
    context = agent._context(public_messages, "继续")
    assert '旧记录[未知行动]：—｜发言："兼容无行动记录"' in context
    assert '非法行动[未知行动]：—｜发言："未知行动类型"' in context
    assert '非法条款[未知行动]：—｜发言："条款结构异常"' in context
    assert '空选项[报价]：议题→—｜发言："选项为空"' in context
    assert "不应进入公共会场" not in context
    assert "空发言[" not in context

    with pytest.raises(ValueError, match="离线模式没有可用"):
        agent.act(system_prompt="提示", public_messages=[], turn_input="行动")
    with pytest.raises(ValueError, match="完整 action"):
        agent.remember(1, {"public_message": "缺行动"})
    with pytest.raises(ValueError, match="非空 public_message"):
        agent.remember(1, {"action": {"action_type": "statement"}, "public_message": " "})
    assert agent.turns == 0 and agent.private_memory == []

    expected = _response("us", 1)
    result = agent.act(
        system_prompt="提示",
        public_messages=[],
        turn_input="行动",
        call_model=lambda messages, prompt: (expected, "raw", "stop"),
    )
    assert result["obj"] is expected
    assert result["raw"] == "raw" and result["finish"] == "stop"
    agent.remember(1, expected)
    info = agent.public_info()
    assert info == {"key": "us", "label": "美国", "turns": 1, "memory_count": 1}
    assert "private_memory" not in json.dumps(info, ensure_ascii=False)
    print("PASS: 行动摘要异常分支、离线错误和公开 Agent 信息均有有效断言")
"""11/19 回合粒度验收：一次 /action = 我方一手 + 对手一手。

已签字段不动：
- action_points 恒等于 action_points_per_round（D 回签：UI 只显示上限）；
- action_points_left 是新字段，逐手递减、回合结束回满；
- version 仍是已提交行动数，但步长不保证 2（终局在对手行动前只 +1）。
"""

from __future__ import annotations

import copy
import uuid

import pytest
from fastapi.testclient import TestClient

import api
import neg_cli as neg
from load_scenario import load_scenario

client = TestClient(api.app, raise_server_exceptions=False)

AI_SCENARIO_ID = "ai_governance"
CHIP_PATH = "scenario agent v2/data/scenarios/main_chip_controls.json"
CHIP_SCENARIO_ID = "scn-chip-controls-0001"

# ai_governance：3 个条款 → 预算 4
OFFER_AI = {
    "action_type": "offer",
    "card_id": "anchor_offer",
    "offer_patch": {
        "全球算力资源分配": {
            "option": "以既有联盟实践为蓝本设立高风险 AI 出口管制的可核查机制",
            "note": "我方锚定报价。",
        }
    },
    "conditions": [],
    "expected_effect": "把分歧收拢到可核查机制。",
    "public_message": "我方就全球算力资源分配提出具体方案。",
}
PROBE = {
    "action_type": "probe",
    "card_id": "probe_priority",
    "card_payload": {"target": "us"},
    "offer_patch": {},
    "conditions": [],
    "expected_effect": "",
    "public_message": "我方想先确认贵方把哪条议题排在前面。",
}
COUNTER = {
    "action_type": "counter_offer",
    "offer_patch": {},
    "conditions": [],
    "expected_effect": "对贵方版本给出对等回应。",
    "public_message": "我方对当前版本作出对等回应。",
}

# main_chip_controls：4 个条款 → 预算 5
NUMERIC_PATCH = {
    "芯片算力门槛": {"option": 1000, "note": "双方红线内的算力门槛。"},
}
ENUM_PATCH = {
    "第三国再出口限制": {"option": "O2", "note": "仅对清单对象事前许可。"},
    "关键矿产出口安排": {"option": "O2", "note": "设置民用快速通道。"},
    "协议退出与救济安排": {"option": "O2", "note": "协商延长履约期。"},
}
FULL_PATCH = {**NUMERIC_PATCH, **ENUM_PATCH}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.setenv("NEG_OFFLINE", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("NEG_SESSION_STORE_DIR", str(tmp_path))
    api.SESSIONS.clear()
    yield
    api.SESSIONS.clear()


def new_ai_session() -> str:
    resp = client.post(
        "/session", json={"scenario_id": AI_SCENARIO_ID, "agent": "us"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def new_chip_session() -> str:
    resp = client.post(
        "/session",
        json={"scenario_id": CHIP_SCENARIO_ID, "agent": "us", "scenario_path": CHIP_PATH},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def get_state(sid: str) -> dict:
    resp = client.get(f"/session/{sid}/state")
    assert resp.status_code == 200, resp.text
    return resp.json()


def stored_document(sid: str) -> dict:
    return api.get_session_store().read(sid)


def post_action(sid: str, action: dict, key: str | None = None):
    """按当前服务端 version 填基线，模拟前端按 current_state 刷新后提交。"""
    payload = copy.deepcopy(action)
    payload["client_action_id"] = key or uuid.uuid4().hex
    payload["base_version"] = get_state(sid)["version"]
    return client.post(f"/session/{sid}/action", json=payload)


def latest_opponent_clauses(sid: str) -> dict:
    return copy.deepcopy(api.SESSIONS[sid].engine.state.offers[-1].clauses)


def counter_against_latest(sid: str) -> dict:
    action = copy.deepcopy(COUNTER)
    action["offer_patch"] = latest_opponent_clauses(sid)
    return action


def opponent_offer(patch: dict):
    def respond(rec, messages, runtime):
        return {
            "action": {
                "action_type": "offer",
                "offer_patch": copy.deepcopy(patch),
                "conditions": [],
                "expected_effect": "给出具体方案，推动分歧收敛。",
            },
            "public_message": "我方就相关条款提出具体方案，愿继续磋商。",
        }

    return respond


def opponent_statement(card_id: str, payload: dict):
    def respond(rec, messages, runtime):
        return {
            "action": {
                "action_type": "statement",
                "card_id": card_id,
                "card_payload": copy.deepcopy(payload),
                "offer_patch": {},
                "conditions": [],
                "expected_effect": "",
            },
            "public_message": "我方对当前版本作出程序性回应。",
        }

    return respond


def opponent_probe(target: str):
    def respond(rec, messages, runtime):
        return {
            "action": {
                "action_type": "probe",
                "card_id": "probe_priority",
                "card_payload": {"target": target},
                "offer_patch": {},
                "conditions": [],
                "expected_effect": "",
            },
            "public_message": "我方先确认贵方把哪条议题排在前面。",
        }

    return respond


def script_opponent(monkeypatch, turns):
    """按顺序回放对手响应；turns 用完后就重复最后一条。"""
    calls = []

    def respond(rec, messages, runtime):
        index = min(len(calls), len(turns) - 1)
        calls.append(index)
        return turns[index](rec, messages, runtime)

    monkeypatch.setattr(api, "generate_opponent_turn", respond)
    return calls


def auto_step(sid: str):
    return client.post(f"/session/{sid}/auto_step")


def four_ai_hands(sid: str):
    """预算 4 的合法四手：报价卡 → 反报价 → 探询卡 → 反报价。"""
    makers = [
        lambda: OFFER_AI,
        lambda: counter_against_latest(sid),
        lambda: PROBE,
        lambda: counter_against_latest(sid),
    ]
    left_before = []
    responses = []
    for make in makers:
        left_before.append(get_state(sid)["action_points_left"])
        responses.append(post_action(sid, make()))
    return left_before, responses


# ---------------------------------------------------------------------------
# 1) 预算 4：四手递减、前三次回合不变、第四次换回合并回满
# ---------------------------------------------------------------------------
def test_budget_four_four_actions_drain_then_advance_round():
    sid = new_ai_session()
    assert get_state(sid)["action_points_left"] == 4
    assert get_state(sid)["action_points_per_round"] == 4

    responses = four_ai_hands(sid)
    left_before, responses = responses
    assert [resp.status_code for resp in responses] == [200, 200, 200, 200]
    # 出手前剩余：4 → 3 → 2 → 1；前三手在同一回合。
    assert left_before == [4, 3, 2, 1]
    assert [resp.json()["round"] for resp in responses[:3]] == [1, 1, 1]
    expected_left = [resp.json()["action_points_left"] for resp in responses]
    # 第四手用掉最后 1 手（归零），回合结束随即回满，所以响应里是 4。
    assert expected_left == [3, 2, 1, 4]

    state = responses[-1].json()
    # 第四手用完预算：只结束回合，不是终局；回合 +1 且剩余回满。
    assert state["status"] == "active"
    assert state["round"] == 2
    assert state["action_points_left"] == 4


# ---------------------------------------------------------------------------
# 2) 守 D 契约：action_points 四手全程恒等于预算
# ---------------------------------------------------------------------------
def test_action_points_stays_at_budget_across_all_hands():
    sid = new_ai_session()
    _, responses = four_ai_hands(sid)
    assert [resp.status_code for resp in responses] == [200, 200, 200, 200]
    seen = [
        (
            resp.json()["action_points"],
            resp.json()["action_points_per_round"],
            resp.json()["action_points_left"],
        )
        for resp in responses
    ]
    assert [(a, b) for a, b, _ in seen] == [(4, 4)] * 4
    assert [left for _, _, left in seen] == [3, 2, 1, 4]


# ---------------------------------------------------------------------------
# 3) 一次 auto_step 只推一个来回
# ---------------------------------------------------------------------------
def test_auto_step_pushes_one_exchange_and_one_left():
    sid = new_ai_session()
    before = get_state(sid)
    resp = auto_step(sid)
    assert resp.status_code == 200, resp.text
    state = resp.json()
    assert state["action_points_left"] == before["action_points_left"] - 1
    assert state["round"] - before["round"] <= 1
    assert len(state["action_history"]) == 2
    # 一次 auto_step 不等于一个回合：预算没满就留在同一回合。
    assert state["round"] == 1


# ---------------------------------------------------------------------------
# 4) 幂等账本：同一 Idempotency-Key 两次响应逐字节一致
# ---------------------------------------------------------------------------
def test_idempotency_replay_is_byte_identical_including_left_and_round():
    sid = new_ai_session()
    key = "granularity-idem-1"
    payload = copy.deepcopy(OFFER_AI)
    payload["base_version"] = 0
    first = client.post(
        f"/session/{sid}/action", json=payload, headers={"Idempotency-Key": key}
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["round"] == 1
    assert body["action_points"] == 4
    assert body["action_points_left"] == 3
    assert body["version"] == 2

    second = client.post(
        f"/session/{sid}/action", json=payload, headers={"Idempotency-Key": key}
    )
    assert second.status_code == 200
    assert second.content == first.content
    assert second.json()["action_points_left"] == 3
    assert second.json()["round"] == 1
    assert get_state(sid) == body


# ---------------------------------------------------------------------------
# 5) 终局在对手行动前发生：version 只 +1，round 不再推进
# ---------------------------------------------------------------------------
def test_terminal_before_opponent_action_only_bumps_version_by_one():
    sid = new_ai_session()

    rec = api.SESSIONS[sid]
    # 先让双方各有一版报价（我方 + 离线对手）。
    first = post_action(sid, OFFER_AI)
    assert first.status_code == 200, first.text
    before = first.json()
    assert before["version"] == 2
    assert before["round"] == 1

    # 模拟所有条款都已表态：此刻 accept 在引擎前置上合法。
    rec.engine.state.open_issues.clear()
    accept = {
        "action_type": "accept",
        "offer_patch": {},
        "conditions": [],
        "expected_effect": "确认协议。",
        "public_message": "我方接受当前协议。",
    }
    resp = post_action(sid, accept)
    assert resp.status_code == 200, resp.text
    state = resp.json()
    assert state["status"] == "ended"
    # 终局步我方一手后对手不再行动：version 为 3（此前 2 条 + 我方 1 条），
    # 步长不是 2，所以用绝对值比较而不是加减。
    assert before["version"] == 2
    assert state["version"] == 3
    assert state["round"] == before["round"]
    assert state["action_points"] == before["action_points"]
    assert state["action_points_left"] == before["action_points_left"] - 1
    assert len(state["action_history"]) == 3


# ---------------------------------------------------------------------------
# 6) 预算 5 的场景：5 手才换回合
# ---------------------------------------------------------------------------
def test_budget_five_requires_five_hands_to_change_round(monkeypatch):
    script_opponent(
        monkeypatch,
        [
            opponent_offer(NUMERIC_PATCH),
            opponent_offer(NUMERIC_PATCH),
            opponent_offer(NUMERIC_PATCH),
            opponent_offer(NUMERIC_PATCH),
            opponent_probe("cn"),
        ],
    )
    sid = new_chip_session()
    # 芯片场景 4 个子议题 → 预算 5。
    assert get_state(sid)["action_points_per_round"] == 5

    first = {
        "action_type": "offer",
        "card_id": "anchor_offer",
        "offer_patch": copy.deepcopy(NUMERIC_PATCH),
        "conditions": [],
        "expected_effect": "锚定数值条款。",
        "public_message": "我方提出数值条款方案。",
    }
    resp = post_action(sid, first)
    assert resp.status_code == 200, resp.text
    assert resp.json()["action_points_left"] == 4

    for _ in range(2):
        resp = post_action(sid, counter_against_latest(sid))
        assert resp.status_code == 200, resp.text
        assert resp.json()["round"] == 1

    resp = post_action(sid, counter_against_latest(sid))
    assert resp.status_code == 200, resp.text
    # 第四手后预算还剩 1，回合不变。
    assert resp.json()["round"] == 1
    assert resp.json()["action_points_left"] == 1

    fifth = {
        "action_type": "statement",
        "card_id": "mediation",
        "card_payload": {"option": "请求主席团调解。"},
        "offer_patch": {},
        "conditions": [],
        "expected_effect": "",
        "public_message": "我方愿接受主席团调解。",
    }
    resp = post_action(sid, fifth)
    assert resp.status_code == 200, resp.text
    state = resp.json()
    assert state["round"] == 2
    assert state["action_points_left"] == 5
    assert state["action_points"] == 5


# ---------------------------------------------------------------------------
# 7) 引擎侧不被 AP 挡住：预算 4 时引擎起点 8，第四手不报 ACTION_POINTS_INSUFFICIENT
# ---------------------------------------------------------------------------
def test_engine_action_points_is_two_per_my_hand():
    sid = new_ai_session()
    rec = api.SESSIONS[sid]
    assert rec.engine.state.action_points == 8  # 2 × 4
    responses = four_ai_hands(sid)
    _, responses = responses
    assert [resp.status_code for resp in responses] == [200, 200, 200, 200]
    assert "ACTION_POINTS_INSUFFICIENT" not in responses[-1].text
    # 每手结束引擎共享计数扣 2（我方 + 对手），第四手后新回合重新铺满。
    assert api.SESSIONS[sid].engine.state.action_points == 8


# ---------------------------------------------------------------------------
# 8) 中途模型超时：两个行动点字段与 round 都没变（未落盘）
# ---------------------------------------------------------------------------
def test_timeout_keeps_round_and_both_point_fields(monkeypatch):
    monkeypatch.delenv("NEG_OFFLINE", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    sid = new_ai_session()
    before = get_state(sid)
    before_document = stored_document(sid)

    def timeout_once(req, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(neg.urllib.request, "urlopen", timeout_once)
    monkeypatch.setattr(neg.time, "sleep", lambda _: pytest.fail("不应重试"))

    resp = post_action(sid, OFFER_AI)
    assert resp.status_code == 504
    assert resp.json()["error"] == "TIMEOUT"

    after = get_state(sid)
    assert after["round"] == before["round"]
    assert after["action_points"] == before["action_points"]
    assert after["action_points_left"] == before["action_points_left"]
    assert after["version"] == before["version"]
    assert stored_document(sid) == before_document


# ---------------------------------------------------------------------------
# 9) 5 次 auto_step = 5 个来回（10 手），current_round 与实际轮次一致
# ---------------------------------------------------------------------------
def test_five_auto_steps_are_five_exchanges(monkeypatch):
    script_opponent(monkeypatch, [opponent_offer(NUMERIC_PATCH)] * 5)
    sid = new_chip_session()
    previous = get_state(sid)
    history = 0
    for _ in range(5):
        resp = auto_step(sid)
        assert resp.status_code == 200, resp.text
        state = resp.json()
        assert len(state["action_history"]) == len(previous["action_history"]) + 2
        assert client.get(f"/session/{sid}/auto_status").json()["current_round"] == state["round"]
        previous = state
        history = len(state["action_history"])

    assert history == 10
    assert previous["round"] == 2
    assert previous["action_points_left"] == 5
    assert client.get(f"/session/{sid}/auto_status").json()["current_round"] == 2


# ---------------------------------------------------------------------------
# 10) 同一回合内连手时，卡牌冷却理由不跳变
# ---------------------------------------------------------------------------
def test_available_cards_cooldown_reason_stable_within_round():
    sid = new_ai_session()
    resp = post_action(sid, OFFER_AI)
    assert resp.status_code == 200, resp.text

    def anchor_reason():
        cards = {item["id"]: item for item in get_state(sid)["available_cards"]}
        return cards["anchor_offer"]["reason"], cards["anchor_offer"]["available"]

    reason_after_first = anchor_reason()
    assert reason_after_first == ("冷却至第 3 回合", False)

    resp = post_action(sid, counter_against_latest(sid))
    assert resp.status_code == 200, resp.text
    assert anchor_reason() == reason_after_first

    resp = post_action(sid, PROBE)
    assert resp.status_code == 200, resp.text
    assert anchor_reason() == reason_after_first


# ---------------------------------------------------------------------------
# 11) 回合结束条件 c：双方都已报价且可直接 accept → 未用满预算也换回合
# ---------------------------------------------------------------------------
def test_round_ends_when_accept_is_already_possible(monkeypatch):
    script_opponent(monkeypatch, [opponent_offer(FULL_PATCH)])
    sid = new_chip_session()
    first = {
        "action_type": "offer",
        "card_id": "anchor_offer",
        "offer_patch": copy.deepcopy(FULL_PATCH),
        "conditions": [],
        "expected_effect": "一次性给出完整方案。",
        "public_message": "我方提出覆盖全部条款的方案。",
    }
    resp = post_action(sid, first)
    assert resp.status_code == 200, resp.text
    state = resp.json()
    assert state["open_issues"] == []
    # 只用了 1 手（预算 5），但双方对同一方案都已表态、当前可直接 accept。
    assert state["status"] == "active"
    assert state["round"] == 2
    assert state["action_points_left"] == 5


# ---------------------------------------------------------------------------
# 12) 手数用完不是终局：只换回合，对局继续
# ---------------------------------------------------------------------------
def test_hand_budget_exhaustion_is_round_end_not_terminal():
    sid = new_ai_session()
    _, responses = four_ai_hands(sid)
    assert [resp.status_code for resp in responses] == [200, 200, 200, 200]
    state = responses[-1].json()
    assert state["round"] == 2
    assert state["status"] == "active"
    assert state["action_points_left"] == 4
    assert get_state(sid)["status"] == "active"
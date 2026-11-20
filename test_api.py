import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

import api
import neg_cli as neg
from _scenario_fixtures import legacy_body
from load_scenario import CLAUSE_NAMES, make_scenario

client = TestClient(api.app, raise_server_exceptions=False)

VALID_OFFER = {
    "action_type": "offer",
    "offer_patch": {
        "全球算力资源分配": {
            "option": "以既有联盟实践为蓝本设立高风险 AI 出口管制的可核查机制",
            "note": "以对称、可核查的安排回应各方关切。",
        }
    },
    "conditions": ["核查标准对所有参与方对称适用。"],
    "expected_effect": "推动各方形成可讨论的交换条件。",
    "public_message": "我方愿在全球算力资源分配议题上提出建设性方案。",
}

STATEMENT = {
    "action_type": "statement",
    "card_id": "public_commitment",
    "card_payload": {"text": "我方承诺继续在联合国框架下磋商。"},
    "offer_patch": {},
    "conditions": [],
    "expected_effect": "",
    "public_message": "我方主张在联合国框架下继续磋商，反对任何单边安排。",
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.setenv("NEG_OFFLINE", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("NEG_SESSION_STORE_DIR", str(tmp_path))
    api.SESSIONS.clear()
    yield
    api.SESSIONS.clear()


def new_session(agent="us"):
    # 本文件守的是契约机制（幂等、版本、错误码、教练、评分），沿用旧的 3 条款
    # 形状做夹具；产品默认场景已换成芯片，见 test_scenario_prompt.py。
    body = legacy_body()
    body["agent"] = agent
    resp = client.post("/session", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def new_online_session(monkeypatch):
    monkeypatch.delenv("NEG_OFFLINE", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    return new_session()


def get_state(sid):
    resp = client.get(f"/session/{sid}/state")
    assert resp.status_code == 200, resp.text
    return resp.json()


def assert_state_keys(state):
    assert set(state) == set(api.PUBLIC_STATE_KEYS)


def flat_action(action_id="engine-1", actor="cn", action_type="offer", patch=None):
    return {
        "action_id": action_id,
        "actor": actor,
        "action_type": action_type,
        "card_id": None,
        "offer_patch": copy.deepcopy(patch if patch is not None else VALID_OFFER["offer_patch"]),
        "conditions": [],
        "expected_effect": "",
        "public_message": "引擎错误适配测试。",
    }


def test_health():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_session_initial_state():
    sid = new_session()
    state = get_state(sid)
    assert_state_keys(state)
    assert state["session_id"] == sid
    assert state["round"] == 1
    assert state["phase"] == "opening"
    assert state["my_offer"] == {"version": 0, "offers": {}}
    assert state["opponent_offer"] == {"version": 0, "offers": {}}
    assert state["open_issues"] == list(CLAUSE_NAMES)
    assert state["action_history"] == []
    assert state["status"] == "active"
    assert state["mode"] == "offline"


def test_create_session_invalid_scenario():
    for value in ("default", "other", ""):
        body = legacy_body()
        body["scenario_id"] = value
        resp = client.post("/session", json=body)
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_SCENARIO"


def test_create_session_invalid_agent():
    for value in ("_scenario", "xx", "", "eu"):
        body = legacy_body()
        body["agent"] = value
        resp = client.post("/session", json=body)
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_AGENT"


def test_create_session_request_validation():
    resp = client.post("/session", json={"agent": "us"})
    assert resp.status_code == 422
    assert resp.json()["error"] == "INVALID_REQUEST"
    assert set(resp.json()) == {"error", "detail"}
    resp = client.post("/session", json={**legacy_body(), "extra": 1})
    assert resp.status_code == 422
    resp = client.post("/session", json={**legacy_body(), "scenario_id": 1})
    assert resp.status_code == 422


def test_action_success_full_flow():
    sid = new_session()
    before = get_state(sid)
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 200, resp.text
    state = resp.json()
    assert_state_keys(state)
    # 11/19 粒度：一次 /action = 我方一手 + 对手一手；预算未用完时回合不变。
    assert state["round"] == before["round"]
    assert state["action_points"] == before["action_points"]
    assert state["action_points_left"] == before["action_points_left"] - 1
    assert state["phase"] == "bargaining"
    assert len(state["action_history"]) == 2
    mine, opp = state["action_history"]
    assert mine["actor"] == "cn"
    assert mine["origin"] == "human"
    assert mine["action_id"] == "a000001"
    assert mine["card_id"] is None
    assert mine["action_type"] == "offer"
    assert "缺少 mood" in mine["warnings"]
    assert "缺少 round_summary" in mine["warnings"]
    assert opp["actor"] == "us"
    assert opp["origin"] == "opponent_ai"
    assert opp["action_id"] == "a000002"
    assert opp["public_message"] == api.offline_opponent.build_offline_turn(
        api.SESSIONS[sid].engine.scenario, 0
    )["public_message"]
    assert state["my_offer"]["version"] == 1
    entry = state["my_offer"]["offers"]["全球算力资源分配"]
    assert entry == VALID_OFFER["offer_patch"]["全球算力资源分配"]
    assert "round" not in entry and "action_id" not in entry
    assert state["opponent_offer"]["version"] == 2
    # 离线对手第 1 手只谈数值条款（旧夹具里的「前沿模型评测门槛」）。
    assert "前沿模型评测门槛" in state["opponent_offer"]["offers"]
    assert "全球算力资源分配" not in state["open_issues"]
    assert get_state(sid) == state


def test_action_identity_fields_are_server_controlled_and_card_is_forwarded():
    sid = new_session()
    payload = dict(VALID_OFFER, actor="us", action_id="fake-id", card_id="anchor_offer")
    resp = client.post(f"/session/{sid}/action", json=payload)
    assert resp.status_code == 200, resp.text
    mine = resp.json()["action_history"][0]
    assert mine["actor"] == "cn"
    assert mine["action_id"] == "a000001"
    assert mine["card_id"] == "anchor_offer"
    resp = client.post(f"/session/{sid}/action", json=dict(VALID_OFFER, unknown_field=1))
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_ACTION"


def test_action_double_validation():
    sid = new_session()
    bad_patch = copy.deepcopy(VALID_OFFER)
    bad_patch["offer_patch"]["全球算力资源分配"] = {"option": "只有选项没有说明"}
    resp = client.post(f"/session/{sid}/action", json=bad_patch)
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_ACTION"
    resp = client.post(f"/session/{sid}/action", json=dict(VALID_OFFER, public_message="   "))
    assert resp.status_code == 400
    resp = client.post(f"/session/{sid}/action", json=dict(VALID_OFFER, action_type="not_a_type"))
    assert resp.status_code == 400


def test_invalid_action_no_model_call_and_state_unchanged(monkeypatch):
    sid = new_session()
    calls = []
    monkeypatch.setattr(api, "generate_opponent_turn", lambda *args: calls.append(args) or {})
    before = get_state(sid)
    illegal = dict(STATEMENT, action_type="accept", offer_patch=VALID_OFFER["offer_patch"])
    resp = client.post(f"/session/{sid}/action", json=illegal)
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_ACTION"
    assert set(resp.json()) == {"error", "detail"}
    assert calls == []
    assert get_state(sid) == before
    runtime = api.SESSIONS[sid].runtime
    assert runtime.action_seq == 0
    assert runtime.offline_cursor == 0
    assert len(runtime.messages) == 1


def test_engine_rejection_preserves_error_and_zero_change(monkeypatch):
    sid = new_session()
    calls = []
    monkeypatch.setattr(api, "generate_opponent_turn", lambda *args: calls.append(args) or {})
    before = get_state(sid)
    rec = api.SESSIONS[sid]
    archive = copy.deepcopy(rec.engine.state.to_archive_dict())
    payload = copy.deepcopy(VALID_OFFER)
    payload["offer_patch"] = {"不存在的条款": {"option": "x", "note": "y"}}
    resp = client.post(f"/session/{sid}/action", json=payload)
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "INVALID_ACTION"
    assert body["engine_error"] == "UNKNOWN_CLAUSE"
    assert calls == []
    assert get_state(sid) == before
    assert rec.engine.state.to_archive_dict() == archive
    assert rec.runtime.action_seq == 0


def test_term_locked_error_mapping_and_zero_change():
    engine = api.RulesEngine(make_scenario(), "locked-test")
    engine.scenario["clauses"][0]["locked"] = True
    archive = copy.deepcopy(engine.state.to_archive_dict())
    with pytest.raises(api.ApiError) as caught:
        api.submit_engine_action(engine, flat_action())
    assert caught.value.status_code == 409
    assert caught.value.error == "ROUND_LOCKED"
    assert caught.value.extra == {"engine_error": "TERM_LOCKED"}
    assert engine.state.to_archive_dict() == archive


def test_duplicate_and_phase_closed_error_mappings():
    engine = api.RulesEngine(make_scenario(), "error-test")
    action = flat_action()
    api.submit_engine_action(engine, action)
    archive = copy.deepcopy(engine.state.to_archive_dict())
    with pytest.raises(api.ApiError) as caught:
        api.submit_engine_action(engine, action)
    # DUPLICATE_ACTION 不在映射表里 → 归 INVALID_ACTION，原始码保留。
    assert caught.value.status_code == 400
    assert caught.value.error == "INVALID_ACTION"
    assert caught.value.extra == {"engine_error": "DUPLICATE_ACTION"}
    assert engine.state.to_archive_dict() == archive
    engine.state.status = "ended"
    with pytest.raises(api.ApiError) as caught:
        api.submit_engine_action(engine, flat_action(action_id="engine-2"))
    assert caught.value.status_code == 409
    assert caught.value.error == "ROUND_LOCKED"
    assert caught.value.extra == {"engine_error": "PHASE_CLOSED"}


def test_action_id_sequence_not_consumed_by_failure():
    sid = new_session()
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 200
    bad = copy.deepcopy(VALID_OFFER)
    bad["offer_patch"] = {"不存在的条款": {"option": "x", "note": "y"}}
    resp = client.post(f"/session/{sid}/action", json=bad)
    assert resp.status_code == 400
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 200, resp.text
    ids = [record["action_id"] for record in resp.json()["action_history"]]
    assert ids == ["a000001", "a000002", "a000003", "a000004"]


def test_offers_independent_between_sides():
    sid = new_session()
    payload = copy.deepcopy(VALID_OFFER)
    payload["offer_patch"] = {"前沿模型评测门槛": {"option": 40, "note": "我方说明"}}
    resp = client.post(f"/session/{sid}/action", json=payload)
    assert resp.status_code == 200, resp.text
    state = resp.json()
    assert state["my_offer"]["offers"]["前沿模型评测门槛"]["option"] == 40
    assert state["opponent_offer"]["offers"]["前沿模型评测门槛"]["option"] != 40
    assert state["my_offer"]["version"] == 1
    assert state["opponent_offer"]["version"] == 2


def test_auto_step_stub_and_single_round():
    sid = new_session()
    before = get_state(sid)
    resp = client.post(f"/session/{sid}/auto_step")
    assert resp.status_code == 200, resp.text
    state = resp.json()
    # 一次 auto_step 只推一个来回（我方一手 + 对手一手），回合按预算推进。
    assert state["round"] == before["round"]
    assert state["action_points_left"] == before["action_points_left"] - 1
    assert len(state["action_history"]) == 2
    mine, _ = state["action_history"]
    assert mine["origin"] == "auto_player"
    assert mine["action_type"] == "statement"
    assert mine["offer_patch"] == {}
    assert mine["public_message"] == api.offline_opponent.auto_speech(
        api.SESSIONS[sid].engine.scenario, 1
    )
    assert state["my_offer"] == {"version": 0, "offers": {}}
    assert state["opponent_offer"]["version"] == 1
    assert get_state(sid) == state


def test_auto_step_talk_track_follows_round():
    """我方自动话术按「本手所在回合」取句，同回合复用、跨回合换句。"""
    sid = new_session()
    scenario = api.SESSIONS[sid].engine.scenario
    checked = 0
    for _ in range(6):
        resp = client.post(f"/session/{sid}/auto_step")
        if resp.status_code != 200:
            break
        state = resp.json()
        mine = [item for item in state["action_history"] if item["actor"] == "cn"]
        assert mine
        last = mine[-1]
        expected = (
            api.offline_opponent.ACCEPT_SPEECH
            if last["action_type"] == "accept"
            else api.offline_opponent.auto_speech(scenario, last["round"])
        )
        assert last["public_message"] == expected
        checked += 1
    assert checked >= 2


def test_offline_cursor_isolation():
    """两个会话的离线游标互不影响，且各自按游标推进方案。"""
    s1, s2 = new_session(), new_session()
    r1 = client.post(f"/session/{s1}/auto_step").json()
    r2 = client.post(f"/session/{s2}/auto_step").json()
    assert r1["action_history"][-1]["public_message"] == r2["action_history"][-1]["public_message"]
    client.post(f"/session/{s1}/auto_step")
    client.post(f"/session/{s1}/auto_step")
    r4 = client.post(f"/session/{s1}/auto_step").json()
    # 第 4 手已经谈到第 2 批条款，与第 1 手不再相同。
    assert r4["action_history"][-1]["public_message"] != r1["action_history"][-1]["public_message"]
    assert api.SESSIONS[s2].runtime.offline_cursor == 1


def test_offline_opponent_is_deterministic_and_does_not_mutate_scenario():
    sid = new_session()
    scenario = api.SESSIONS[sid].engine.scenario
    baseline = copy.deepcopy(scenario)
    first = api.offline_opponent.build_offline_turn(scenario, 0)
    second = api.offline_opponent.build_offline_turn(scenario, 0)
    assert first == second
    client.post(f"/session/{sid}/action", json=VALID_OFFER)
    client.post(f"/session/{sid}/auto_step")
    assert scenario == baseline


def test_mode_detection(monkeypatch):
    sid = new_session()
    assert get_state(sid)["mode"] == "offline"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "some-key")
    sid2 = new_session()
    assert get_state(sid2)["mode"] == "offline"
    monkeypatch.delenv("NEG_OFFLINE", raising=False)
    sid3 = new_session()
    assert get_state(sid3)["mode"] == "online"
    assert get_state(sid)["mode"] == "offline"
    assert get_state(sid2)["mode"] == "offline"


def test_model_failure_atomic(monkeypatch):
    sid = new_online_session(monkeypatch)
    before = get_state(sid)
    rec = api.SESSIONS[sid]
    archive = copy.deepcopy(rec.engine.state.to_archive_dict())
    monkeypatch.setattr(neg, "call_with_retry", lambda *args: (None, "", None))
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 503
    assert resp.json()["error"] == "MODEL_UNAVAILABLE"
    assert get_state(sid) == before
    assert rec.engine.state.to_archive_dict() == archive
    assert rec.runtime.action_seq == 0
    assert rec.runtime.offline_cursor == 0
    assert len(rec.runtime.messages) == 1


def test_systemexit_via_call_deepseek(monkeypatch):
    sid = new_online_session(monkeypatch)
    before = get_state(sid)

    def boom(*args, **kwargs):
        raise SystemExit("[错误] 未设置 DEEPSEEK_API_KEY")

    monkeypatch.setattr(neg, "call_deepseek", boom)
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 503
    assert resp.json()["error"] == "MODEL_UNAVAILABLE"
    assert "DEEPSEEK_API_KEY" not in resp.json()["detail"]
    assert client.get("/").status_code == 200
    assert get_state(sid) == before


def test_systemexit_boundary_not_swallowing_others(monkeypatch):
    sid = new_online_session(monkeypatch)
    rec = api.SESSIONS[sid]

    def boom(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(neg, "call_with_retry", boom)
    with pytest.raises(KeyboardInterrupt):
        api.generate_opponent_turn(rec, [], rec.runtime)


def test_opponent_invalid_response_503(monkeypatch):
    sid = new_online_session(monkeypatch)
    before = get_state(sid)
    bad = {"action": {"action_type": "not_a_type"}, "public_message": "不合规回应"}
    monkeypatch.setattr(neg, "call_with_retry", lambda *args: (bad, "raw", None))
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 503
    assert resp.json()["error"] == "MODEL_UNAVAILABLE"
    assert get_state(sid) == before


def test_opponent_engine_rejection_retries_once_then_succeeds(monkeypatch):
    """对手先给出非法动作、重试后合法：应正常推进，且只消耗两条模型调用。"""
    sid = new_online_session(monkeypatch)
    calls = []
    bad = {
        "action": {
            "action_type": "offer",
            "offer_patch": {"不存在的条款": {"option": "x", "note": "y"}},
            "conditions": [],
            "expected_effect": "",
        },
        "public_message": "结构上合规但条款不存在。",
    }
    good = api.offline_opponent.build_offline_turn(api.SESSIONS[sid].engine.scenario, 0)

    def respond(*args):
        calls.append(1)
        return bad if len(calls) == 1 else good

    monkeypatch.setattr(api, "generate_opponent_turn", respond)
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 200, resp.text
    assert len(calls) == 2
    # 只推进一手我方 + 一手对手，重试不额外写状态
    assert resp.json()["version"] == 2


def test_opponent_repair_hint_carries_legal_ranges(monkeypatch):
    """重试提示必须带上条款板，否则模型还是会瞎猜数值。"""
    sid = new_online_session(monkeypatch)
    seen = []

    def capture(rec, messages, runtime, *extra):
        seen.append(messages[-1]["content"])
        return {
            "action": {
                "action_type": "offer",
                "offer_patch": {"不存在的条款": {"option": "x", "note": "y"}},
                "conditions": [],
                "expected_effect": "",
            },
            "public_message": "非法动作。",
        }

    monkeypatch.setattr(api, "generate_opponent_turn", capture)
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 400
    assert len(seen) == 2
    repair = json.loads(seen[1])
    assert "correction" in repair and "UNKNOWN_CLAUSE" in repair["correction"]
    assert repair["clauses"]
    assert any(item["name"] == "全球算力资源分配" for item in repair["clauses"])


def test_opponent_engine_rejection_preserves_original_error(monkeypatch):
    sid = new_online_session(monkeypatch)
    before = get_state(sid)
    bad = {
        "action": {
            "action_type": "offer",
            "offer_patch": {"不存在的条款": {"option": "x", "note": "y"}},
            "conditions": [],
            "expected_effect": "",
        },
        "public_message": "结构上合规但条款不存在。",
    }
    monkeypatch.setattr(neg, "call_with_retry", lambda *args: (bad, "raw", None))
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "INVALID_ACTION"
    assert body["engine_error"] == "UNKNOWN_CLAUSE"
    assert get_state(sid) == before
    assert api.SESSIONS[sid].runtime.action_seq == 0


def test_online_no_fallback_to_offline(monkeypatch):
    sid = new_online_session(monkeypatch)
    monkeypatch.setattr(neg, "call_with_retry", lambda *args: (None, "", None))
    resp = client.post(f"/session/{sid}/auto_step")
    assert resp.status_code == 503
    state = get_state(sid)
    assert state["mode"] == "online"
    assert state["round"] == 1
    assert api.SESSIONS[sid].runtime.offline_cursor == 0


def test_debrief_not_available_before_terminal_and_state_unchanged():
    sid = new_session()
    client.post(f"/session/{sid}/auto_step")
    before = get_state(sid)
    resp = client.post(f"/session/{sid}/debrief")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "DEBRIEF_NOT_AVAILABLE"
    assert body["fail_reason"] == "谈判尚未结束，复盘暂不可用"
    assert set(body) == {"error", "detail", "fail_reason"}
    assert get_state(sid) == before


def test_session_not_found_all_endpoints():
    for method, path in (
        ("GET", "/session/nope/state"),
        ("POST", "/session/nope/action"),
        ("POST", "/session/nope/auto_step"),
        ("POST", "/session/nope/debrief"),
    ):
        resp = client.request(method, path, json=VALID_OFFER if path.endswith("action") else None)
        assert resp.status_code == 404
        assert resp.json()["error"] == "SESSION_NOT_FOUND"


def test_malformed_json_and_wrong_top_level():
    sid = new_session()
    resp = client.post(f"/session/{sid}/action", content="{not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_JSON"
    resp = client.post(f"/session/{sid}/action", json=[1, 2])
    assert resp.status_code == 422
    assert resp.json()["error"] == "INVALID_REQUEST"


def test_unknown_route_and_method():
    resp = client.get("/no_such_path")
    assert resp.status_code == 404
    assert resp.json() == {"error": "NOT_FOUND", "detail": "请求的路径不存在。"}
    resp = client.get("/session")
    assert resp.status_code == 405
    assert resp.json()["error"] == "METHOD_NOT_ALLOWED"


def test_cors_preflight_and_actual():
    resp = client.options(
        "/session",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "*"
    assert "POST" in resp.headers["access-control-allow-methods"]
    resp = client.post(
        "/session",
        json=legacy_body(),
        headers={"Origin": "http://localhost:3000"},
    )
    assert resp.headers["access-control-allow-origin"] == "*"


def test_session_isolation():
    s1, s2 = new_session(), new_session()
    client.post(f"/session/{s1}/auto_step")
    client.post(f"/session/{s1}/auto_step")
    client.post(f"/session/{s2}/auto_step")
    st1, st2 = get_state(s1), get_state(s2)
    # 两个会话各自按自己的手数推进，互不影响；两次/一次都未用满预算。
    assert st1["round"] == 1
    assert st2["round"] == 1
    assert st1["action_points_left"] == 2
    assert st2["action_points_left"] == 3
    assert len(st1["action_history"]) == 4
    assert len(st2["action_history"]) == 2
    assert api.SESSIONS[s1].runtime.offline_cursor == 2
    assert api.SESSIONS[s2].runtime.offline_cursor == 1


def test_session_busy(monkeypatch):
    sid = new_session()
    started = threading.Event()
    release = threading.Event()
    original = api.generate_opponent_turn

    def blocking(rec, messages, runtime, *extra):
        started.set()
        release.wait(10)
        return original(rec, messages, runtime, *extra)

    monkeypatch.setattr(api, "generate_opponent_turn", blocking)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(client.post, f"/session/{sid}/action", json=VALID_OFFER)
        assert started.wait(10)
        resp2 = client.post(f"/session/{sid}/auto_step")
        assert resp2.status_code == 409
        assert resp2.json()["error"] == "SESSION_BUSY"
        release.set()
        resp1 = future.result(timeout=15)
    assert resp1.status_code == 200
    assert get_state(sid)["round"] == 1
    assert get_state(sid)["action_points_left"] == 3


def test_state_reads_committed_engine_during_turn(monkeypatch):
    sid = new_session()
    started = threading.Event()
    release = threading.Event()
    original = api.generate_opponent_turn

    def blocking(rec, messages, runtime, *extra):
        started.set()
        release.wait(10)
        return original(rec, messages, runtime, *extra)

    monkeypatch.setattr(api, "generate_opponent_turn", blocking)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(client.post, f"/session/{sid}/auto_step")
        assert started.wait(10)
        mid = get_state(sid)
        assert mid["round"] == 1
        assert mid["action_history"] == []
        release.set()
        resp = future.result(timeout=15)
    assert resp.status_code == 200
    assert get_state(sid)["round"] == 1
    assert get_state(sid)["action_points_left"] == 3


def test_restore_engine_archive_equivalence_and_isolation():
    sid = new_session()
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 200
    original = api.SESSIONS[sid].engine
    archive = copy.deepcopy(original.state.to_archive_dict())
    candidate = api.restore_engine(original)
    assert candidate is not original
    assert candidate.state.to_archive_dict() == archive
    candidate.state.open_issues.append("候选修改")
    candidate.state.private_state_by_party["us"]["sentinel"] = "changed"
    candidate.state.offers[0].clauses["全球算力资源分配"]["option"] = "changed"
    assert original.state.to_archive_dict() == archive


def test_exact_eight_fields_forwarded_without_extensions(monkeypatch):
    sid = new_session()
    captured = []
    original = api.submit_engine_action

    def spy(engine, flat):
        captured.append(copy.deepcopy(flat))
        return original(engine, flat)

    monkeypatch.setattr(api, "submit_engine_action", spy)
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 200
    expected = {"action_id", "actor", "action_type", "card_id", "offer_patch", "conditions", "expected_effect", "public_message"}
    assert len(captured) == 2
    for action in captured:
        assert set(action) == expected
        assert "base_version" not in action
        assert "effect_labels" not in action


def test_effect_labels_forwarded_when_present(monkeypatch):
    sid = new_session()
    captured = []
    original = api.submit_engine_action

    def spy(engine, flat):
        captured.append(copy.deepcopy(flat))
        return original(engine, flat)

    monkeypatch.setattr(api, "submit_engine_action", spy)
    labels = [
        {
            "label": "constructive_proposal",
            "magnitude": "moderate",
            "clause": "全球算力资源分配",
            "reason": "本轮提出了附带可核查机制的分配方案。",
        }
    ]
    payload = dict(VALID_OFFER, effect_labels=labels)
    resp = client.post(f"/session/{sid}/action", json=payload)
    assert resp.status_code == 200
    assert captured[0]["effect_labels"] == labels
    assert "effect_labels" not in captured[1]


def test_effect_labels_invalid_rejected():
    sid = new_session()
    bad = [
        {
            "label": "not_a_real_label",
            "magnitude": "moderate",
            "clause": None,
            "reason": "非法枚举值应被 schema 拦截。",
        }
    ]
    resp = client.post(
        f"/session/{sid}/action", json=dict(VALID_OFFER, effect_labels=bad)
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_ACTION"


def test_next_round_called_once(monkeypatch):
    """预算 4 手：前 3 手不推进回合，第 4 手用完预算时恰好调用一次 next_round。

    固定让对手只报数值条款，`open_issues` 始终非空 → 不会因为「可以 accept」
    提前推进回合，这一手就只剩「预算用完」这个触发条件。
    """
    sid = new_session()
    fixed = api.offline_opponent.build_offline_turn(
        api.SESSIONS[sid].engine.scenario, 0
    )
    monkeypatch.setattr(
        api, "generate_opponent_turn", lambda *args: copy.deepcopy(fixed)
    )
    calls = []
    original = api.RulesEngine.next_round

    def spy(self):
        calls.append(self.session_id)
        return original(self)

    monkeypatch.setattr(api.RulesEngine, "next_round", spy)
    for step in range(4):
        resp = client.post(f"/session/{sid}/auto_step")
        assert resp.status_code == 200, resp.text
        if step < 3:
            assert resp.json()["action_points_left"] == 3 - step
            assert calls == []
        else:
            # 第四手用完预算：回合推进，剩余手数回满。
            assert resp.json()["round"] == 2
            assert resp.json()["action_points_left"] == 4
    assert calls == [sid]
    assert client.get(f"/session/{sid}/state").json()["round"] == 2


def test_error_response_shape_and_privacy(monkeypatch):
    sid = new_online_session(monkeypatch)
    rec = api.SESSIONS[sid]
    rec.engine.state.private_state_by_party["us"]["sentinel"] = "US_PRIVATE_SENTINEL"
    rec.engine.state.private_state_by_party["cn"]["sentinel"] = "CN_PRIVATE_SENTINEL"
    public_text = json.dumps(get_state(sid), ensure_ascii=False)
    assert "US_PRIVATE_SENTINEL" not in public_text
    assert "CN_PRIVATE_SENTINEL" not in public_text
    assert "private_state_by_party" not in public_text
    monkeypatch.setattr(neg, "call_with_retry", lambda *args: (None, "", None))
    responses = [
        client.post("/session", json={"scenario_id": "bad", "agent": "us"}),
        client.post(f"/session/{sid}/action", json=dict(VALID_OFFER, public_message=" ")),
        client.get("/session/nope/state"),
        client.post(f"/session/{sid}/action", json=VALID_OFFER),
        client.get("/no_such_path"),
    ]
    for resp in responses:
        body = resp.json()
        assert set(body) == {"error", "detail"}
        assert isinstance(body["detail"], str) and body["detail"]
        assert "test-key" not in body["detail"]
        assert "US_PRIVATE_SENTINEL" not in body["detail"]

import uuid


class ContractClient(TestClient):
    def post(self, url, **kwargs):
        payload = kwargs.get("json")
        if isinstance(payload, dict) and url.startswith("/session/") and url.endswith("/action"):
            rec = api.SESSIONS.get(url.split("/")[2])
            payload = dict(payload)
            payload.setdefault("client_action_id", uuid.uuid4().hex)
            if rec is not None:
                # base_version 与顶层 version 同口径：已提交行动数。
                payload.setdefault(
                    "base_version",
                    api.action_event_count(rec.engine.public_state("cn")["public_events"]),
                )
            kwargs["json"] = payload
        return super().post(url, **kwargs)


raw_client = client
client = ContractClient(api.app, raise_server_exceptions=False)


def submit_action(sid, payload, client_action_id, base_version):
    return raw_client.post(
        f"/session/{sid}/action",
        json=dict(payload, client_action_id=client_action_id, base_version=base_version),
    )


def test_idempotent_replay_returns_byte_identical_response():
    sid = new_session()
    first = submit_action(sid, VALID_OFFER, "idem-1", 0)
    assert first.status_code == 200, first.text
    rec = api.SESSIONS[sid]
    committed_version = rec.engine.state.current_version
    history_len = len(first.json()["action_history"])
    second = submit_action(sid, VALID_OFFER, "idem-1", 0)
    assert second.status_code == 200, second.text
    assert second.content == first.content
    state = get_state(sid)
    assert state == first.json()
    assert len(state["action_history"]) == history_len
    assert rec.engine.state.current_version == committed_version
    assert rec.runtime.action_seq == 2


def test_missing_or_invalid_transport_fields_rejected():
    sid = new_session()
    resp = raw_client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 422
    assert resp.json() == {
        "error": "INVALID_REQUEST",
        "detail": "缺少必填字段 client_action_id（或 Idempotency-Key 头）。",
    }
    resp = raw_client.post(f"/session/{sid}/action", json=dict(VALID_OFFER, client_action_id="c-1"))
    assert resp.status_code == 422
    assert resp.json() == {"error": "INVALID_REQUEST", "detail": "缺少必填字段 base_version。"}
    resp = raw_client.post(
        f"/session/{sid}/action", json=dict(VALID_OFFER, client_action_id="   ", base_version=0)
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "缺少必填字段 client_action_id（或 Idempotency-Key 头）。"
    for bad_version in ("0", -1, 1.5, True, None):
        resp = raw_client.post(
            f"/session/{sid}/action",
            json=dict(VALID_OFFER, client_action_id="c-1", base_version=bad_version),
        )
        assert resp.status_code == 422, bad_version
        assert resp.json()["error"] == "INVALID_REQUEST"
    assert get_state(sid)["action_history"] == []
    assert api.SESSIONS[sid].idempotency_ledger == {}


def test_stale_base_version_conflict_returns_current_state():
    sid = new_session()
    ok = submit_action(sid, VALID_OFFER, "v-1", 0)
    assert ok.status_code == 200, ok.text
    rec = api.SESSIONS[sid]
    before = get_state(sid)
    assert before["version"] == 2
    archive = copy.deepcopy(rec.engine.state.to_archive_dict())
    # 0 是旧的“报价版本”口径，在新口径下必然是过期基线。
    resp = submit_action(sid, STATEMENT, "v-2", 0)
    assert resp.status_code == 409
    body = resp.json()
    assert set(body) == {"error", "detail", "current_state", "version"}
    assert body["error"] == "VERSION_CONFLICT"
    assert body["version"] == before["version"]
    assert body["current_state"] == before
    for key in ("my_offer", "opponent_offer", "open_issues", "version"):
        assert key in body["current_state"]
    assert get_state(sid) == before
    assert rec.engine.state.to_archive_dict() == archive
    assert set(rec.idempotency_ledger) == {"v-1"}
    retry = submit_action(
        sid, dict(VALID_OFFER, action_type="counter_offer"), "v-2", before["version"]
    )
    assert retry.status_code == 200, retry.text


def test_failed_attempt_does_not_poison_ledger():
    sid = new_session()
    bad = submit_action(sid, dict(VALID_OFFER, unknown_field=1), "retry-1", 0)
    assert bad.status_code == 400
    assert bad.json()["error"] == "INVALID_ACTION"
    assert api.SESSIONS[sid].idempotency_ledger == {}
    retry = submit_action(sid, VALID_OFFER, "retry-1", 0)
    assert retry.status_code == 200, retry.text
    assert len(retry.json()["action_history"]) == 2
    assert set(api.SESSIONS[sid].idempotency_ledger) == {"retry-1"}


def test_transport_fields_stripped_and_replay_skips_engine(monkeypatch):
    sid = new_session()
    captured = []
    original = api.submit_engine_action

    def spy(engine, flat):
        captured.append(copy.deepcopy(flat))
        return original(engine, flat)

    monkeypatch.setattr(api, "submit_engine_action", spy)
    first = submit_action(sid, VALID_OFFER, "spy-1", 0)
    assert first.status_code == 200, first.text
    assert len(captured) == 2
    for flat in captured:
        assert "client_action_id" not in flat
        assert "base_version" not in flat
    second = submit_action(sid, VALID_OFFER, "spy-1", 0)
    assert second.status_code == 200
    assert second.content == first.content
    assert len(captured) == 2


def test_model_timeout_fails_atomically_and_same_request_can_retry(monkeypatch):
    sid = new_online_session(monkeypatch)
    before = get_state(sid)
    rec = api.SESSIONS[sid]
    archive = copy.deepcopy(rec.engine.state.to_archive_dict())
    calls = []

    def timeout_once(req, timeout):
        calls.append({"url": req.full_url, "timeout": timeout})
        raise TimeoutError("timed out")

    monkeypatch.setattr(neg.urllib.request, "urlopen", timeout_once)
    monkeypatch.setattr(
        neg.time, "sleep", lambda _: pytest.fail("60 秒超时后不应继续内层重试")
    )
    failed = submit_action(sid, VALID_OFFER, "timeout-retry-1", 0)
    assert failed.status_code == 504
    body = failed.json()
    assert body["error"] == "TIMEOUT"
    assert body["engine_error"] == "MODEL_TIMEOUT"
    assert body["detail"] == "对手模型响应超时，本次未提交，可原样重试。"
    assert len(calls) == 1
    assert calls[0]["timeout"] == 60
    assert get_state(sid) == before
    assert rec.engine.state.to_archive_dict() == archive
    assert rec.runtime.action_seq == 0
    assert rec.idempotency_ledger == {}
    assert not rec.mutation_lock.locked()


    monkeypatch.setattr(
        neg,
        "call_with_retry",
        lambda *args: (
            api.offline_opponent.build_offline_turn(api.SESSIONS[sid].engine.scenario, 0),
            "raw",
            "stop",
        ),
    )
    retry = submit_action(sid, VALID_OFFER, "timeout-retry-1", 0)
    assert retry.status_code == 200, retry.text
    assert retry.json()["round"] == 1
    assert retry.json()["action_points_left"] == 3
    assert [event["action_id"] for event in retry.json()["action_history"]] == [
        "a000001", "a000002",
    ]
    assert not rec.mutation_lock.locked()


def test_three_invalid_model_json_responses_return_503_without_fabricated_action(monkeypatch):
    sid = new_online_session(monkeypatch)
    before = get_state(sid)
    rec = api.SESSIONS[sid]
    archive = copy.deepcopy(rec.engine.state.to_archive_dict())
    calls = []

    def invalid_json(messages, json_mode=True, temperature=0.7):
        calls.append(json_mode)
        return "{ definitely not valid JSON", "stop"

    monkeypatch.setattr(neg, "call_deepseek", invalid_json)
    monkeypatch.setattr(neg.time, "sleep", lambda _: None)
    response = submit_action(sid, VALID_OFFER, "invalid-json-1", 0)
    assert response.status_code == 503
    assert response.json()["error"] == "MODEL_UNAVAILABLE"
    assert calls == [True, True, False]
    assert get_state(sid) == before
    assert rec.engine.state.to_archive_dict() == archive
    assert rec.runtime.action_seq == 0
    assert rec.runtime.offline_cursor == 0
    assert len(rec.runtime.messages) == 1
    assert rec.idempotency_ledger == {}
    assert not rec.mutation_lock.locked()
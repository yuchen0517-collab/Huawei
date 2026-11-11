import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

import api
import neg_cli as neg

client = TestClient(api.app, raise_server_exceptions=False)

VALID_OFFER = {
    "action_type": "offer",
    "offer_patch": {
        "数据跨境流动规则": {
            "option": "在联合国框架下建立对称适用的数据跨境通报机制",
            "note": "以对称通报安排回应各方对透明度与数据主权的共同关切。",
        }
    },
    "conditions": ["核查标准对所有参与方对称适用。"],
    "expected_effect": "推动各方在数据主权与跨境合作之间形成可讨论的交换条件。",
    "public_message": "我方愿在数据跨境流动议题上提出建设性方案，建议建立对称适用的通报机制。",
}

STATEMENT = {
    "action_type": "statement",
    "offer_patch": {},
    "conditions": [],
    "expected_effect": "",
    "public_message": "我方主张在联合国框架下继续磋商，反对任何单边安排。",
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setenv("NEG_OFFLINE", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    api.SESSIONS.clear()
    yield
    api.SESSIONS.clear()


def new_session(agent="us"):
    resp = client.post("/session", json={"scenario_id": "ai_governance", "agent": agent})
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


def test_health():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_session_initial_state():
    sid = new_session()
    state = get_state(sid)
    assert_state_keys(state)
    assert state["session_id"] == sid
    assert state["round"] == 0
    assert state["phase"] == "opening"
    assert state["my_offer"] == {"version": 0, "offers": {}}
    assert state["opponent_offer"] == {"version": 0, "offers": {}}
    assert state["open_issues"] == list(api.AGENDA)
    assert state["action_history"] == []
    assert state["status"] == "active"
    assert state["mode"] == "offline"


def test_create_session_invalid_scenario():
    for value in ("default", "other", ""):
        resp = client.post("/session", json={"scenario_id": value, "agent": "us"})
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_SCENARIO"


def test_create_session_invalid_agent():
    for value in ("_scenario", "xx", ""):
        resp = client.post("/session", json={"scenario_id": "ai_governance", "agent": value})
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_AGENT"


def test_create_session_request_validation():
    resp = client.post("/session", json={"agent": "us"})
    assert resp.status_code == 422
    assert resp.json()["error"] == "INVALID_REQUEST"
    assert set(resp.json()) == {"error", "detail"}
    resp = client.post(
        "/session",
        json={"scenario_id": "ai_governance", "agent": "us", "extra": 1},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "INVALID_REQUEST"
    resp = client.post("/session", json={"scenario_id": 1, "agent": "us"})
    assert resp.status_code == 422


def test_action_success_full_flow():
    sid = new_session()
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 200, resp.text
    state = resp.json()
    assert_state_keys(state)
    assert state["round"] == 1
    assert state["phase"] == "opening"
    assert len(state["action_history"]) == 2
    mine, opp = state["action_history"]
    assert mine["round"] == 1
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
    assert opp["card_id"] is None
    assert opp["public_message"] == neg.OFFLINE_RESPONSES[0]["public_message"]
    assert state["my_offer"]["version"] == 1
    entry = state["my_offer"]["offers"]["数据跨境流动规则"]
    assert entry["option"] == VALID_OFFER["offer_patch"]["数据跨境流动规则"]["option"]
    assert entry["round"] == 1
    assert entry["action_id"] == "a000001"
    assert state["opponent_offer"]["version"] == 1
    assert "AI安全监管框架" in state["opponent_offer"]["offers"]
    assert get_state(sid) == state


def test_action_identity_fields_stripped():
    sid = new_session()
    payload = dict(VALID_OFFER, actor="us", action_id="fake-id", card_id="card-x")
    resp = client.post(f"/session/{sid}/action", json=payload)
    assert resp.status_code == 200, resp.text
    mine = resp.json()["action_history"][0]
    assert mine["actor"] == "cn"
    assert mine["action_id"] == "a000001"
    assert mine["card_id"] is None
    resp = client.post(f"/session/{sid}/action", json=dict(VALID_OFFER, unknown_field=1))
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_ACTION"


def test_action_double_validation():
    sid = new_session()
    bad_patch = copy.deepcopy(VALID_OFFER)
    bad_patch["offer_patch"]["数据跨境流动规则"] = {"option": "只有选项没有说明"}
    resp = client.post(f"/session/{sid}/action", json=bad_patch)
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_ACTION"
    blank = dict(VALID_OFFER, public_message="   ")
    resp = client.post(f"/session/{sid}/action", json=blank)
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_ACTION"
    bad_type = dict(VALID_OFFER, action_type="not_a_type")
    resp = client.post(f"/session/{sid}/action", json=bad_type)
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_ACTION"


def test_invalid_action_no_model_call_and_state_unchanged(monkeypatch):
    sid = new_session()
    calls = []
    monkeypatch.setattr(
        api, "generate_opponent_turn", lambda *args: calls.append(args) or {}
    )
    before = get_state(sid)
    illegal = {
        "action_type": "accept",
        "offer_patch": {"AI安全监管框架": {"option": "x", "note": "y"}},
        "conditions": [],
        "expected_effect": "",
        "public_message": "我方接受。",
    }
    resp = client.post(f"/session/{sid}/action", json=illegal)
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_ACTION"
    assert set(resp.json()) == {"error", "detail"}
    assert calls == []
    assert get_state(sid) == before
    snap = api.SESSIONS[sid].snapshot
    assert snap.action_seq == 0
    assert snap.offline_cursor == 0
    assert len(snap.messages) == 1


def test_action_id_sequence_not_consumed_by_failure():
    sid = new_session()
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 200
    resp = client.post(f"/session/{sid}/action", json=dict(VALID_OFFER, public_message=" "))
    assert resp.status_code == 400
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 200
    ids = [r["action_id"] for r in resp.json()["action_history"]]
    assert ids == ["a000001", "a000002", "a000003", "a000004"]


def test_offer_version_rules_unit():
    side = api.OfferSide()
    multi = {
        "action_id": "a000001",
        "offer_patch": {
            "议题A": {"option": "x", "note": "a"},
            "议题B": {"option": 30, "note": "b"},
        },
    }
    side = api.apply_offer(side, multi, 1)
    assert side.version == 1
    assert set(side.offers) == {"议题A", "议题B"}
    empty = {"action_id": "a000002", "offer_patch": {}}
    assert api.apply_offer(side, empty, 2) is side
    override = {"action_id": "a000003", "offer_patch": {"议题A": {"option": "y", "note": "c"}}}
    side2 = api.apply_offer(side, override, 3)
    assert side2.version == 2
    assert side2.offers["议题A"]["option"] == "y"
    assert side2.offers["议题A"]["round"] == 3
    assert side2.offers["议题B"]["option"] == 30
    assert side.offers["议题A"]["option"] == "x"


def test_offers_independent_between_sides():
    sid = new_session()
    payload = copy.deepcopy(VALID_OFFER)
    payload["offer_patch"] = {
        "AI安全监管框架": {"option": "我方版本条款", "note": "我方说明"}
    }
    resp = client.post(f"/session/{sid}/action", json=payload)
    assert resp.status_code == 200
    state = resp.json()
    assert state["my_offer"]["offers"]["AI安全监管框架"]["option"] == "我方版本条款"
    assert state["opponent_offer"]["offers"]["AI安全监管框架"]["option"] != "我方版本条款"
    assert state["my_offer"]["version"] == 1
    assert state["opponent_offer"]["version"] == 1


def test_open_issues_and_status_never_change():
    sid = new_session()
    for action_type in ("accept", "walk_away"):
        payload = dict(STATEMENT, action_type=action_type)
        resp = client.post(f"/session/{sid}/action", json=payload)
        assert resp.status_code == 200, resp.text
    resp = client.post(f"/session/{sid}/debrief")
    assert resp.status_code == 202
    state = get_state(sid)
    assert state["open_issues"] == list(api.AGENDA)
    assert state["status"] == "active"


def test_phase_boundaries():
    assert api.phase_of(0) == "opening"
    assert api.phase_of(3) == "opening"
    assert api.phase_of(4) == "bargaining"
    assert api.phase_of(8) == "bargaining"
    assert api.phase_of(9) == "closing"
    assert api.phase_of(10) == "closing"


def test_auto_step_stub_and_single_round():
    sid = new_session()
    resp = client.post(f"/session/{sid}/auto_step")
    assert resp.status_code == 200, resp.text
    state = resp.json()
    assert state["round"] == 1
    assert len(state["action_history"]) == 2
    mine, opp = state["action_history"]
    assert mine["origin"] == "auto_player"
    assert mine["action_type"] == "statement"
    assert mine["offer_patch"] == {}
    assert mine["conditions"] == []
    assert mine["expected_effect"] == ""
    assert mine["public_message"] == neg.CHINA_LINES[0].replace("\n", " ")
    assert state["my_offer"] == {"version": 0, "offers": {}}
    assert state["opponent_offer"]["version"] == 1
    assert get_state(sid) == state


def test_auto_step_china_lines_cycle():
    sid = new_session()
    texts = []
    for _ in range(4):
        resp = client.post(f"/session/{sid}/auto_step")
        assert resp.status_code == 200
        texts.append(resp.json()["action_history"][-2]["public_message"])
    expected = [neg.CHINA_LINES[i % 3].replace("\n", " ") for i in range(4)]
    assert texts == expected


def test_offline_cursor_isolation_and_cycle():
    s1, s2 = new_session(), new_session()
    r1 = client.post(f"/session/{s1}/auto_step").json()
    r2 = client.post(f"/session/{s2}/auto_step").json()
    assert r1["action_history"][-1]["public_message"] == r2["action_history"][-1]["public_message"]
    first = r1["action_history"][-1]["public_message"]
    client.post(f"/session/{s1}/auto_step")
    client.post(f"/session/{s1}/auto_step")
    r4 = client.post(f"/session/{s1}/auto_step").json()
    assert r4["action_history"][-1]["public_message"] == first
    assert api.SESSIONS[s2].snapshot.offline_cursor == 1


def test_offline_samples_immutable():
    baseline = copy.deepcopy(neg.OFFLINE_RESPONSES)
    sid = new_session()
    client.post(f"/session/{sid}/action", json=VALID_OFFER)
    client.post(f"/session/{sid}/auto_step")
    assert neg.OFFLINE_RESPONSES == baseline


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
    assert before["mode"] == "online"
    monkeypatch.setattr(neg, "call_with_retry", lambda *args: (None, "", None))
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 503
    assert resp.json()["error"] == "MODEL_UNAVAILABLE"
    assert get_state(sid) == before
    snap = api.SESSIONS[sid].snapshot
    assert snap.round == 0
    assert snap.action_seq == 0
    assert snap.offline_cursor == 0
    assert len(snap.messages) == 1
    assert snap.action_history == ()


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
        api.generate_opponent_turn(rec, [], rec.snapshot)


def test_opponent_invalid_response_503(monkeypatch):
    sid = new_online_session(monkeypatch)
    before = get_state(sid)
    bad = {"action": {"action_type": "not_a_type"}, "public_message": "不合规回应"}
    monkeypatch.setattr(neg, "call_with_retry", lambda *args: (bad, "raw", None))
    resp = client.post(f"/session/{sid}/action", json=VALID_OFFER)
    assert resp.status_code == 503
    assert resp.json()["error"] == "MODEL_UNAVAILABLE"
    assert get_state(sid) == before


def test_online_no_fallback_to_offline(monkeypatch):
    sid = new_online_session(monkeypatch)
    monkeypatch.setattr(neg, "call_with_retry", lambda *args: (None, "", None))
    resp = client.post(f"/session/{sid}/auto_step")
    assert resp.status_code == 503
    state = get_state(sid)
    assert state["mode"] == "online"
    assert state["round"] == 0
    assert api.SESSIONS[sid].snapshot.offline_cursor == 0


def test_debrief_placeholder_and_state_unchanged():
    sid = new_session()
    client.post(f"/session/{sid}/auto_step")
    before = get_state(sid)
    resp = client.post(f"/session/{sid}/debrief")
    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted"}
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
    resp = client.post(
        f"/session/{sid}/action",
        content="{not json",
        headers={"Content-Type": "application/json"},
    )
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
        json={"scenario_id": "ai_governance", "agent": "us"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert resp.headers["access-control-allow-origin"] == "*"


def test_session_isolation():
    s1, s2 = new_session(), new_session()
    client.post(f"/session/{s1}/auto_step")
    client.post(f"/session/{s1}/auto_step")
    client.post(f"/session/{s2}/auto_step")
    st1, st2 = get_state(s1), get_state(s2)
    assert st1["round"] == 2
    assert st2["round"] == 1
    assert len(st1["action_history"]) == 4
    assert len(st2["action_history"]) == 2
    assert api.SESSIONS[s1].snapshot.offline_cursor == 2
    assert api.SESSIONS[s2].snapshot.offline_cursor == 1


def test_session_busy(monkeypatch):
    sid = new_session()
    started = threading.Event()
    release = threading.Event()
    original = api.generate_opponent_turn

    def blocking(rec, messages, snap):
        started.set()
        release.wait(10)
        return original(rec, messages, snap)

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


def test_state_reads_committed_snapshot_during_turn(monkeypatch):
    sid = new_session()
    started = threading.Event()
    release = threading.Event()
    original = api.generate_opponent_turn

    def blocking(rec, messages, snap):
        started.set()
        release.wait(10)
        return original(rec, messages, snap)

    monkeypatch.setattr(api, "generate_opponent_turn", blocking)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(client.post, f"/session/{sid}/auto_step")
        assert started.wait(10)
        mid = get_state(sid)
        assert mid["round"] == 0
        assert mid["action_history"] == []
        release.set()
        resp = future.result(timeout=15)
    assert resp.status_code == 200
    assert get_state(sid)["round"] == 1


def test_error_response_shape_and_safety(monkeypatch):
    sid = new_online_session(monkeypatch)
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
        assert "隐藏任务" not in body["detail"]
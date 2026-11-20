"""11/17 接口回签（给A的消息-接口回签-1117.md）的契约验收。

覆盖：投影 16 字段、clauses 两种形状与数量、version 口径、base_version、
六码归一、Idempotency-Key、TIMEOUT 504、SESSION_BUSY retry_after、
coach_advice 三态/确定性/证据过滤、debrief fail_reason、openapi schema。
"""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api
import neg_cli as neg
from _scenario_fixtures import LEGACY_ID, LEGACY_PATH

client = TestClient(api.app, raise_server_exceptions=False)

BASE_DIR = Path(__file__).resolve().parent
OPENAPI_PATH = BASE_DIR / "openapi.json"
CHIP_SCENARIO_PATH = str(BASE_DIR / "scenario agent v2" / "data" / "scenarios" / "main_chip_controls.json")
CHIP_SCENARIO_ID = "scn-chip-controls-0001"
SIX_CODES = {
    "INVALID_ACTION", "ROUND_LOCKED", "VERSION_CONFLICT",
    "SESSION_BUSY", "MODEL_UNAVAILABLE", "TIMEOUT",
}
CLAUSE_KEYS = {"name", "type", "unit", "range", "options", "initial"}

OFFER = {
    "action_type": "offer",
    "offer_patch": {
        "全球算力资源分配": {"option": "附带可核查机制", "note": "对称核查安排。"},
    },
    "conditions": ["核查标准对所有参与方对称适用。"],
    "expected_effect": "推动形成可讨论的交换条件。",
    "public_message": "我方就全球算力资源分配提出附带可核查机制的建设性方案。",
}
STATEMENT = {
    "action_type": "statement",
    "card_id": "public_commitment",
    "card_payload": {"text": "我方承诺继续在多方框架下磋商。"},
    "offer_patch": {},
    "conditions": [],
    "expected_effect": "",
    "public_message": "我方主张继续在多方框架下磋商，反对任何单边安排。",
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.setenv("NEG_OFFLINE", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("NEG_SESSION_STORE_DIR", str(tmp_path))
    api.SESSIONS.clear()
    yield
    api.SESSIONS.clear()


def new_session(path: str | None = None, scenario_id: str = LEGACY_ID) -> str:
    body: dict = {
        "scenario_id": scenario_id,
        "agent": "us",
        "scenario_path": path or LEGACY_PATH,
    }
    resp = client.post("/session", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def get_state(sid: str) -> dict:
    resp = client.get(f"/session/{sid}/state")
    assert resp.status_code == 200, resp.text
    return resp.json()


def post_action(
    sid: str,
    payload: dict,
    base_version: int = 0,
    body_key: str | None = None,
    header_key: str | None = None,
):
    body = dict(payload, base_version=base_version)
    if body_key is not None:
        body["client_action_id"] = body_key
    headers = {"Idempotency-Key": header_key} if header_key is not None else {}
    return client.post(f"/session/{sid}/action", json=body, headers=headers)


def new_key() -> str:
    return f"req-{uuid.uuid4().hex}"


def do_action(sid: str, payload: dict | None = None):
    """提交一手合法行动（自动补 base_version 与意图号），返回 (state, response)。"""
    state = get_state(sid)
    resp = post_action(
        sid,
        payload or OFFER,
        base_version=state["version"],
        body_key=new_key(),
    )
    assert resp.status_code == 200, resp.text
    return resp.json(), resp


def coach_pieces(sid: str) -> dict:
    """取 build_coach_advice 的入参快照，用于证据过滤测试。"""
    rec = api.SESSIONS[sid]
    state = get_state(sid)
    public = rec.engine.public_state("cn")
    my = api.latest_offer(public, "cn")
    opponent = api.latest_offer(public, "us")
    return {
        "version": state["version"],
        "round_no": state["round"],
        "clauses": state["clauses"],
        "my_offers": my["offers"],
        "opponent_offers": opponent["offers"],
        "open_issues": state["open_issues"],
        "history": state["action_history"],
        "opponent_actor": "us",
    }


# ---------------------------------------------------------------------------
# 任务 1：投影 18 字段（v2 新增 available_cards / pending_hint；
# 11/19 新增 action_points_left；11/20 封板新增 speaker_score，其余语义不动）
# ---------------------------------------------------------------------------
def test_projection_has_eighteen_fields_and_no_more():
    sid = new_session()
    state = get_state(sid)
    expected = {
        "session_id", "round", "phase", "my_offer", "opponent_offer",
        "open_issues", "action_history", "status", "mode",
        "clauses", "version", "action_points", "action_points_per_round",
        "action_points_left",
        "coach_advice", "available_cards", "pending_hint",
        "speaker_score",
    }
    assert expected == set(api.PUBLIC_STATE_KEYS)
    assert len(expected) == 18
    assert set(state) == expected
    assert state["version"] == 0
    assert state["speaker_score"] is None
    assert state["action_points"] == 4
    assert state["action_points_per_round"] == 4
    assert state["action_points"] == state["action_points_per_round"]
    assert state["action_points_left"] == state["action_points_per_round"]


def test_clauses_enum_and_numeric_shapes():
    state = get_state(new_session())
    enums = [item for item in state["clauses"] if item["type"] == "enum"]
    numerics = [item for item in state["clauses"] if item["type"] == "numeric"]
    assert enums and numerics
    for clause in state["clauses"]:
        assert set(clause) == CLAUSE_KEYS
        assert isinstance(clause["unit"], str)
    for clause in enums:
        assert clause["range"] is None
        assert isinstance(clause["options"], list) and clause["options"]
        assert all(isinstance(option, str) for option in clause["options"])
        assert clause["initial"] in clause["options"]
    for clause in numerics:
        assert clause["options"] is None
        assert set(clause["range"]) == {"min", "max", "step"}
        assert clause["range"]["min"] < clause["range"]["max"]
        assert clause["range"]["step"] > 0
        assert isinstance(clause["initial"], (int, float))
        assert clause["range"]["min"] <= clause["initial"] <= clause["range"]["max"]


def test_clause_count_follows_scenario_issues():
    sid = new_session()
    state = get_state(sid)
    rec = api.SESSIONS[sid]
    names = [clause["name"] for clause in rec.engine.scenario["clauses"]]
    # ai_governance 是 3 条（2 枚举 + 1 数值），不硬凑 5 条。
    assert len(state["clauses"]) == len(names) == 3
    assert [clause["name"] for clause in state["clauses"]] == names

    chip_sid = new_session(CHIP_SCENARIO_PATH, CHIP_SCENARIO_ID)
    chip_state = get_state(chip_sid)
    chip_names = [clause["name"] for clause in api.SESSIONS[chip_sid].engine.scenario["clauses"]]
    assert len(chip_state["clauses"]) == len(chip_names) == 4
    assert {item["unit"] for item in chip_state["clauses"]} >= {"TFLOPS(FP16)", ""}
    numeric = next(item for item in chip_state["clauses"] if item["type"] == "numeric")
    assert numeric["range"] == {"min": 100, "max": 5000, "step": 100}


def test_clause_initial_tracks_my_latest_offer():
    sid = new_session()
    payload = {
        "action_type": "offer",
        "offer_patch": {
            "数据跨境流动": {"option": "白名单互认", "note": "枚举条款换档。"},
            "前沿模型评测门槛": {"option": 40, "note": "数值条款下调。"},
        },
        "conditions": [],
        "expected_effect": "",
        "public_message": "我方同时调整枚举与数值条款，测试投影 initial 的取值来源。",
    }
    state, _ = do_action(sid, payload)
    by_name = {clause["name"]: clause for clause in state["clauses"]}
    assert by_name["数据跨境流动"]["initial"] == "白名单互认"
    assert by_name["前沿模型评测门槛"]["initial"] == 40


def test_action_history_keeps_evidence_anchor_fields():
    sid = new_session()
    state, _ = do_action(sid)
    assert state["action_history"]
    for item in state["action_history"]:
        for key in ("action_id", "round", "actor", "action_type"):
            assert key in item
        assert item["action_id"] == f"a{int(str(item['action_id'])[1:]):06d}"


# ---------------------------------------------------------------------------
# 任务 1/2：version 与 base_version 同口径
# ---------------------------------------------------------------------------
def test_version_is_committed_action_count_and_monotonic():
    sid = new_session()
    versions = [get_state(sid)["version"]]
    assert versions == [0]
    state, _ = do_action(sid)
    versions.append(state["version"])
    state, _ = do_action(sid, dict(OFFER, action_type="counter_offer"))
    versions.append(state["version"])
    api.SESSIONS[sid].engine.state.status = "ended"
    versions.append(get_state(sid)["version"])
    assert versions == [0, 2, 4, 4]
    assert versions == sorted(versions)
    rec = api.SESSIONS[sid]
    assert versions[-1] == api.action_event_count(
        rec.engine.public_state("cn")["public_events"]
    )


def test_missing_base_version_is_422_and_state_unchanged():
    sid = new_session()
    before = get_state(sid)
    resp = client.post(
        f"/session/{sid}/action",
        json=dict(OFFER, client_action_id=new_key()),
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "INVALID_REQUEST"
    assert get_state(sid) == before


def test_stale_base_version_is_409_with_top_level_version():
    sid = new_session()
    state, _ = do_action(sid)
    assert state["version"] == 2
    before = get_state(sid)
    # 报价版本是 2，旧口径会误判为“基线正确”；新口径下 1 才是过期。
    resp = post_action(sid, STATEMENT, base_version=1, body_key=new_key())
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "VERSION_CONFLICT"
    assert body["version"] == before["version"] == 2
    assert body["current_state"] == before
    assert get_state(sid) == before


# ---------------------------------------------------------------------------
# 任务 3：六码归一
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("code", sorted(api.ENGINE_ERRORS))
def test_every_engine_code_maps_to_one_of_six(code):
    err = api.engine_action_error(code)
    assert err.error in {"INVALID_ACTION", "ROUND_LOCKED", "VERSION_CONFLICT"}
    assert err.status_code == api.API_ERROR_STATUS[err.error]
    assert err.extra == {"engine_error": code}
    if code in api.INVALID_ACTION_ENGINE_CODES:
        assert err.error == "INVALID_ACTION"
    elif code in api.ROUND_LOCKED_ENGINE_CODES:
        assert err.error == "ROUND_LOCKED"
    elif code == "VERSION_CONFLICT":
        assert err.error == "VERSION_CONFLICT"
    else:
        # 映射表没覆盖到的引擎码统一归 INVALID_ACTION，不发明第七码。
        assert err.error == "INVALID_ACTION"


def test_invalid_action_and_round_locked_over_http():
    sid = new_session()
    bad = dict(OFFER, offer_patch={"不存在的条款": {"option": "x", "note": "y"}})
    resp = post_action(sid, bad, base_version=0, body_key=new_key())
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_ACTION"
    assert resp.json()["engine_error"] == "UNKNOWN_CLAUSE"

    rec = api.SESSIONS[sid]
    rec.engine.state.status = "ended"
    rec.engine.state.phase = "ended"
    resp = post_action(sid, STATEMENT, base_version=0, body_key=new_key())
    assert resp.status_code == 409
    assert resp.json()["error"] == "ROUND_LOCKED"
    assert resp.json()["engine_error"] == "PHASE_CLOSED"


def test_model_unavailable_is_503(monkeypatch):
    monkeypatch.delenv("NEG_OFFLINE", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    sid = new_session()
    before = get_state(sid)
    monkeypatch.setattr(neg, "call_with_retry", lambda *args: (None, "", None))
    resp = post_action(sid, OFFER, base_version=0, body_key=new_key())
    assert resp.status_code == 503
    assert resp.json()["error"] == "MODEL_UNAVAILABLE"
    assert get_state(sid) == before


def test_session_busy_second_click_has_retry_after(monkeypatch):
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
        future = pool.submit(
            post_action, sid, OFFER, 0, new_key()
        )
        assert started.wait(10)
        second = post_action(sid, STATEMENT, 0, new_key())
        assert second.status_code == 409
        assert second.json()["error"] == "SESSION_BUSY"
        assert second.json()["retry_after"] == 1
        release.set()
        first = future.result(timeout=15)
    assert first.status_code == 200


def test_timeout_is_504_and_process_survives(monkeypatch):
    monkeypatch.delenv("NEG_OFFLINE", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    sid = new_session()
    before = get_state(sid)
    calls = []

    def timeout(req, timeout):
        calls.append(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(neg.urllib.request, "urlopen", timeout)
    monkeypatch.setattr(neg.time, "sleep", lambda _: pytest.fail("超时不应内层重试"))
    resp = post_action(sid, OFFER, base_version=0, body_key=new_key())
    assert resp.status_code == 504
    body = resp.json()
    assert body["error"] == "TIMEOUT"
    assert body["engine_error"] == "MODEL_TIMEOUT"
    assert body["detail"] == "对手模型响应超时，本次未提交，可原样重试。"
    assert calls == [60]
    # sys.exit 不再发生：进程还能继续服务，状态零变更。
    assert client.get("/").status_code == 200
    assert get_state(sid) == before


# ---------------------------------------------------------------------------
# 任务 5：Idempotency-Key
# ---------------------------------------------------------------------------
def test_idempotency_key_and_body_alias_are_equivalent():
    sid = new_session()
    key = "req-alias-1"
    first = post_action(sid, OFFER, 0, header_key=key)
    assert first.status_code == 200, first.text
    replay = post_action(sid, OFFER, 0, body_key=key)
    assert replay.status_code == 200
    assert replay.content == first.content
    assert len(get_state(sid)["action_history"]) == 2


def test_idempotency_key_body_mismatch_is_400():
    sid = new_session()
    before = get_state(sid)
    resp = post_action(sid, OFFER, 0, body_key="req-body", header_key="req-header")
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_REQUEST"
    assert "不一致" in resp.json()["detail"]
    assert get_state(sid) == before
    assert api.SESSIONS[sid].idempotency_ledger == {}


def test_intent_key_is_opaque_and_replay_byte_identical():
    sid = new_session()
    # 前端已把前缀从 act- 改成 req-；这里故意用一个不像 a+6 位数字的号，
    # 服务端只当不透明字符串，不做格式校验。
    key = "req-OPAQUE-20261117-001"
    first = post_action(sid, OFFER, 0, header_key=key)
    assert first.status_code == 200, first.text
    second = post_action(sid, OFFER, 0, header_key=key)
    assert second.content == first.content
    state = get_state(sid)
    # 新增字段也在幂等响应里，并且账本键就是原样的意图号。
    assert state == first.json()
    assert state["version"] == 2
    assert state["action_points"] == 4
    assert set(api.SESSIONS[sid].idempotency_ledger) == {key}


# ---------------------------------------------------------------------------
# 任务 6：coach_advice
# ---------------------------------------------------------------------------
def assert_coach_item_contract(advice: dict, state: dict):
    history_ids = {item["action_id"] for item in state["action_history"]}
    clause_names = {clause["name"] for clause in state["clauses"]}
    assert advice["status"] in ("pending", "ready", "failed")
    if advice["status"] == "pending":
        assert advice["items"] == []
    if advice["status"] == "failed":
        assert advice["items"] == []
        assert advice["fail_reason"] and len(advice["fail_reason"]) <= 30
    if advice["status"] == "ready":
        assert advice["basis_version"] == state["version"]
        assert advice["basis_round"] == state["round"]
        assert advice["generated_at"]
        assert 0 <= len(advice["items"]) <= 5
    for item in advice["items"]:
        assert len(item["title"]) <= 16
        assert 30 <= len(item["text"]) <= 90
        assert item["kind"] in ("risk", "opportunity", "next_move")
        assert item["ap_cost"] == (1 if item["kind"] == "next_move" else None)
        assert item["id"].startswith("ca-")
        blob = (item["title"] + item["text"]).replace(" ", "").lower()
        for word in api.FORBIDDEN_COACH_WORDS:
            assert word.lower() not in blob
        for evidence in item["evidence"]:
            assert evidence["kind"] in ("action", "offer", "event")
            assert 1 <= evidence["round"] <= advice["basis_round"]
            assert evidence["action_id"] in history_ids
            if evidence["clause"] is not None:
                assert evidence["clause"] in clause_names
            assert 0 < len(evidence["label"]) <= 20


def test_coach_advice_pending_then_ready():
    sid = new_session()
    pending = get_state(sid)["coach_advice"]
    assert pending["status"] == "pending"
    assert pending["items"] == []
    assert pending["basis_version"] == 0

    state, resp = do_action(sid)
    ready = state["coach_advice"]
    assert ready["status"] == "ready", resp.text
    assert ready["basis_version"] == state["version"] == 2
    assert ready["items"]
    assert ready == get_state(sid)["coach_advice"]
    assert_coach_item_contract(ready, state)


def test_coach_advice_failed_degrades_without_500(monkeypatch):
    sid = new_session()

    def boom(*args, **kwargs):
        raise RuntimeError("规则算挂了")

    monkeypatch.setattr(api, "build_coach_advice", boom)
    resp = client.post(
        f"/session/{sid}/action",
        json=dict(OFFER, client_action_id=new_key(), base_version=0),
    )
    assert resp.status_code == 200, resp.text
    state = resp.json()
    advice = state["coach_advice"]
    assert advice["status"] == "failed"
    assert advice["items"] == []
    assert advice["fail_reason"] and len(advice["fail_reason"]) <= 30
    assert get_state(sid)["coach_advice"] == advice


def test_coach_advice_is_byte_stable_for_same_version():
    sid = new_session()
    state, _ = do_action(sid)
    first = client.get(f"/session/{sid}/state")
    second = client.get(f"/session/{sid}/state")
    assert first.content == second.content
    coach = json.dumps(first.json()["coach_advice"], ensure_ascii=False)
    assert coach == json.dumps(second.json()["coach_advice"], ensure_ascii=False)
    assert first.json()["coach_advice"]["generated_at"] == state["coach_advice"]["generated_at"]

    # 落盘重载后同一个 version 仍逐字节一致（generated_at 不重新生成）。
    api.SESSIONS.clear()
    third = client.get(f"/session/{sid}/state")
    assert third.content == first.content


def test_coach_evidence_out_of_range_or_missing_action_is_dropped():
    sid = new_session()
    do_action(sid)
    pieces = coach_pieces(sid)
    assert api.build_coach_advice(**pieces)["items"]  # 正样本：有可溯源证据

    future = [dict(item, round=99) for item in pieces["history"]]
    assert api.build_coach_advice(**{**pieces, "history": future})["items"] == []

    # 证据里的 action_id 不可查（这里用 None 模拟“账本里没有”）→ 整条不生成。
    ghost = [dict(item, action_id=None) for item in pieces["history"]]
    assert api.build_coach_advice(**{**pieces, "history": ghost})["items"] == []

    # 单元级断言：越界 round / 未知 action_id / 未知条款都判不合法。
    good = {"kind": "action", "round": 2, "action_id": "a000001", "clause": "X", "label": "R2 我方报价"}
    ids = {"a000001"}
    assert api.coach_evidence_ok(good, ids, 2, {"X"}) is True
    assert api.coach_evidence_ok(dict(good, round=3), ids, 2, {"X"}) is False
    assert api.coach_evidence_ok(dict(good, round=0), ids, 2, {"X"}) is False
    assert api.coach_evidence_ok(dict(good, action_id="a000002"), ids, 2, {"X"}) is False
    assert api.coach_evidence_ok(dict(good, clause="Y"), ids, 2, {"X"}) is False


# ---------------------------------------------------------------------------
# 任务 7 / 8：debrief 与 openapi
# ---------------------------------------------------------------------------
def test_debrief_not_available_has_human_fail_reason():
    sid = new_session()
    resp = client.post(f"/session/{sid}/debrief")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "DEBRIEF_NOT_AVAILABLE"
    assert body["fail_reason"] == "谈判尚未结束，复盘暂不可用"
    assert len(body["fail_reason"]) <= 30
    assert body["detail"]


def test_openapi_schema_contains_new_fields_and_six_codes():
    schema = api.app.openapi()
    state_schema = schema["components"]["schemas"]["StateProjection"]["properties"]
    assert {
        "clauses", "version", "action_points", "action_points_per_round", "coach_advice",
    } <= set(state_schema)
    assert schema["components"]["schemas"]["ApiErrorCode"]["enum"] == [
        "INVALID_ACTION", "ROUND_LOCKED", "VERSION_CONFLICT",
        "SESSION_BUSY", "MODEL_UNAVAILABLE", "TIMEOUT",
    ]
    assert SIX_CODES == set(schema["components"]["schemas"]["ApiErrorCode"]["enum"])
    error_properties = schema["components"]["schemas"]["ActionErrorResponse"]["properties"]
    assert {"version", "current_state"} <= set(error_properties)
    action_responses = schema["paths"]["/session/{session_id}/action"]["post"]["responses"]
    for status in ("400", "409", "503", "504"):
        ref = action_responses[status]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ActionErrorResponse")
    # 落盘的 openapi.json 必须与当前应用一致，避免“文档落后于代码”。
    assert json.loads(OPENAPI_PATH.read_text(encoding="utf-8")) == schema

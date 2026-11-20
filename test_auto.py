"""自动推演（auto_step / auto_status）状态机与 B 真实场景端到端验证。

场景来源：`scenario agent v2/data/scenarios/main_chip_controls.json`，
经 load_scenario.py（C 侧 load_scenario_bridge）转换，不使用最小场景。
真实芯片场景使用脚本化对手，不是真模型推演或真实在线模型验收。
我方行动完全由 api.build_auto_action 自动决策：open_issues 非空时选择可用过渡卡，
为空时 accept。
"""

import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

import api
import neg_cli as neg

client = TestClient(api.app, raise_server_exceptions=False)

REAL_SCENARIO_PATH = "scenario agent v2/data/scenarios/main_chip_controls.json"
REAL_SCENARIO_ID = "scn-chip-controls-0001"

# 数值条款取双方硬红线之内的安全值；枚举条款按引擎要求使用 option id。
NUMERIC_PATCH = {
    "芯片算力门槛": {"option": 1000, "note": "位于中方 800 以上、美方 1500 以下的安全区间。"},
    "许可审批时限": {"option": 75, "note": "位于美方 60 以上、中方 90 以下的安全区间。"},
}
ENUM_PATCH = {
    "第三国再出口限制": {"option": "O2", "note": "避开美方对 O1 的硬红线。"},
    "关键矿产出口安排": {"option": "O2", "note": "避开中方对 O3/O4 的硬红线。"},
}
FULL_PATCH = {**NUMERIC_PATCH, **ENUM_PATCH}
# 双方都未表态的条款保持未决；仅一方表态的条款不算未决。
OPEN_AFTER_NUMERIC = list(ENUM_PATCH)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.setenv("NEG_OFFLINE", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("NEG_SESSION_STORE_DIR", str(tmp_path))
    api.SESSIONS.clear()
    yield
    api.SESSIONS.clear()


def new_real_session():
    resp = client.post(
        "/session",
        json={
            "scenario_id": REAL_SCENARIO_ID,
            "agent": "us",
            "scenario_path": REAL_SCENARIO_PATH,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def get_state(sid):
    resp = client.get(f"/session/{sid}/state")
    assert resp.status_code == 200, resp.text
    return resp.json()


def auto_status(sid):
    resp = client.get(f"/session/{sid}/auto_status")
    assert resp.status_code == 200, resp.text
    return resp.json()


def auto_step(sid):
    return client.post(f"/session/{sid}/auto_step")


def stored_document(sid):
    """直接读落盘文件，验证每步结果都已持久化，而非只在内存中。"""
    return api.get_session_store().read(sid)


def opponent_with_patch(patch):
    def respond(rec, messages, runtime):
        return {
            "action": {
                "action_type": "offer",
                "offer_patch": copy.deepcopy(patch),
                "conditions": [],
                "expected_effect": "就条款取值给出具体方案，推动分歧收敛。",
            },
            "public_message": "我方就相关条款提出具体方案，愿在相互尊重基础上继续磋商并寻求一致。",
        }

    return respond


def script_opponent(monkeypatch, patches):
    """脚本化对手按顺序给出报价，不是真模型推演或真实在线模型验收。"""
    calls = []

    def respond(rec, messages, runtime):
        index = min(len(calls), len(patches) - 1)
        calls.append(index)
        return opponent_with_patch(patches[index])(rec, messages, runtime)

    monkeypatch.setattr(api, "generate_opponent_turn", respond)
    return calls


def test_chip_scripted_opponent_five_steps_to_full_agreement(monkeypatch):
    """真实芯片场景＋脚本化对手连续 5 步到终局，不是真模型推演。"""
    sid = new_real_session()
    rec = api.SESSIONS[sid]
    assert rec.engine.scenario["scenario_id"] == REAL_SCENARIO_ID
    assert [clause["name"] for clause in rec.engine.scenario["clauses"]] == list(FULL_PATCH)
    assert rec.engine.scenario["max_rounds"] == 8
    opponent_calls = script_opponent(
        monkeypatch, [NUMERIC_PATCH, NUMERIC_PATCH, NUMERIC_PATCH, FULL_PATCH]
    )

    assert auto_status(sid) == {
        "session_id": sid,
        "status": "paused",
        "current_round": 1,
        "terminal_type": None,
        "last_error": None,
    }
    assert get_state(sid)["open_issues"] == list(FULL_PATCH)

    seen_rounds = []
    seen_left = []
    for step in range(1, 6):
        resp = auto_step(sid)
        assert resp.status_code == 200, resp.text
        state = resp.json()
        seen_rounds.append(state["round"])
        seen_left.append(state["action_points_left"])
        # D 契约：action_points 全程恒等于本回合预算（芯片场景 4 子议题 → 5）。
        assert state["action_points"] == 5
        assert state["action_points_per_round"] == 5
        status = auto_status(sid)
        assert status["current_round"] == state["round"]
        assert status["last_error"] is None

        # 每一步返回前必须已落盘：磁盘轮次/状态与响应一致。
        document = stored_document(sid)
        assert document["engine_state"]["round"] == state["round"]
        assert document["auto_status"] == status["status"]
        assert document["auto_terminal_type"] == status["terminal_type"]

        history = state["action_history"]
        if step < 5:
            assert state["status"] == "active"
            assert status["status"] == "paused"
            assert status["terminal_type"] is None
            assert len(history) == step * 2  # 我方 AI 与对手 AI 各行动一次
            mine, opponent = history[-2], history[-1]
            assert mine["actor"] == "cn"
            assert mine["origin"] == "auto_player"
            assert mine["action_type"] in {"statement", "probe", "counter_offer"}
            if mine["action_type"] != "counter_offer":
                assert mine["card_id"] is not None
            assert opponent["actor"] == "us"
            assert opponent["origin"] == "opponent_ai"
            assert opponent["action_type"] == "offer"
        if step < 4:
            assert state["open_issues"] == OPEN_AFTER_NUMERIC
        if step == 4:
            assert state["open_issues"] == []
        if step == 5:
            assert state["status"] == "ended"
            assert status["status"] == "done"
            assert status["terminal_type"] == "FULL_AGREEMENT"
            assert len(history) == 9  # 终局步我方 accept 后对手不再行动
            assert history[-1]["action_type"] == "accept"
            assert history[-1]["origin"] == "auto_player"
            assert history[-1]["actor"] == "cn"
        print(
            f"[real-scenario] step={step} round={state['round']} "
            f"history={len(history)} open_issues={len(state['open_issues'])} "
            f"auto={status['status']} terminal={status['terminal_type']}"
        )

    assert seen_rounds == [1, 1, 1, 2, 2]
    # 第 4 步双方都已对清空后的方案报价（条件 c），回合推进并回满。
    assert seen_left == [4, 3, 2, 5, 4]
    assert opponent_calls == [0, 1, 2, 3]  # 终局步不再调用对手
    assert stored_document(sid)["auto_status"] == "done"
    assert stored_document(sid)["auto_terminal_type"] == "FULL_AGREEMENT"


def test_chip_terminal_rejection_after_done_and_reload(monkeypatch):
    """真实芯片场景＋脚本化对手到终局后拒绝推进，重载仍保持拒绝。"""
    sid = new_real_session()
    opponent_calls = script_opponent(monkeypatch, [FULL_PATCH])
    assert auto_step(sid).status_code == 200
    assert auto_step(sid).status_code == 200
    assert opponent_calls == [0]
    before = get_state(sid)
    assert before["status"] == "ended"
    assert auto_status(sid)["status"] == "done"

    before_document = stored_document(sid)
    resp = auto_step(sid)
    assert resp.status_code == 409
    body = resp.json()
    assert set(body) == {
        "error", "detail", "engine_error", "auto_status", "current_round", "terminal_type",
    }
    assert body["error"] == "ROUND_LOCKED"
    assert body["engine_error"] == "PHASE_CLOSED"
    assert body["auto_status"] == "done"
    assert body["terminal_type"] == "FULL_AGREEMENT"
    assert body["current_round"] == before["round"]
    assert get_state(sid) == before
    assert auto_status(sid)["status"] == "done"
    assert stored_document(sid) == before_document
    assert opponent_calls == [0]

    # 模拟服务重启：内存会话清空，从磁盘记录恢复终局状态。
    api.SESSIONS.clear()
    restored = auto_status(sid)
    assert restored["status"] == "done"
    assert restored["terminal_type"] == "FULL_AGREEMENT"
    assert restored["current_round"] == before["round"]
    assert restored["last_error"] is None
    rejected = auto_step(sid)
    assert rejected.status_code == 409
    assert rejected.json()["error"] == "ROUND_LOCKED"
    assert rejected.json()["engine_error"] == "PHASE_CLOSED"
    assert get_state(sid) == before


def test_auto_timeout_once_pauses_and_recovers(monkeypatch):
    """注入一次超时，验证 paused 零推进、显式恢复和脚本化对手后续终局。"""
    monkeypatch.delenv("NEG_OFFLINE", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    sid = new_real_session()
    rec = api.SESSIONS[sid]
    assert rec.mode == "online"
    before_state = get_state(sid)
    before_document = stored_document(sid)
    calls = []

    def timeout_once(req, timeout):
        calls.append(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(neg.urllib.request, "urlopen", timeout_once)
    monkeypatch.setattr(
        neg.time, "sleep", lambda _: pytest.fail("60 秒超时后不应继续内层重试")
    )

    failed = auto_step(sid)
    assert failed.status_code == 504
    assert failed.json()["error"] == "TIMEOUT"
    assert failed.json()["engine_error"] == "MODEL_TIMEOUT"
    assert calls == [60]

    status = auto_status(sid)
    assert status["status"] == "paused"
    assert status["current_round"] == 1
    assert status["terminal_type"] is None
    assert status["last_error"]["code"] == "MODEL_TIMEOUT"
    assert status["last_error"]["detail"]
    assert get_state(sid) == before_state
    assert rec.runtime.action_seq == 0
    assert rec.runtime.offline_cursor == 0
    document = stored_document(sid)
    assert document["auto_status"] == "paused"
    assert document["auto_last_error"]["code"] == "MODEL_TIMEOUT"
    assert document["engine_state"] == before_document["engine_state"]
    assert document["runtime"] == before_document["runtime"]
    assert document["idempotency_ledger"] == before_document["idempotency_ledger"]
    assert not rec.mutation_lock.locked()
    print(f"[timeout] calls={len(calls)} timeout={calls[0]} paused_round={status['current_round']}")

    monkeypatch.setattr(api, "generate_opponent_turn", opponent_with_patch(FULL_PATCH))
    resumed = auto_step(sid)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["round"] == 1
    assert resumed.json()["action_points_left"] == 4
    assert len(resumed.json()["action_history"]) == 2
    assert [event["action_id"] for event in resumed.json()["action_history"]] == [
        "a000001", "a000002",
    ]
    status = auto_status(sid)
    assert status["status"] == "paused"
    assert status["last_error"] is None
    assert stored_document(sid)["auto_last_error"] is None
    assert calls == [60]

    finished = auto_step(sid)
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "ended"
    final = auto_status(sid)
    assert final["status"] == "done"
    assert final["terminal_type"] == "FULL_AGREEMENT"
    print(f"[resume] recovered to round={final['current_round']} terminal={final['terminal_type']}")


def test_auto_step_serializes_and_exposes_running(monkeypatch):
    """上一步未完成时第二个 auto_step 被 SESSION_BUSY 拒绝；进行中状态为 running。"""
    sid = new_real_session()
    started = threading.Event()
    release = threading.Event()

    def blocking(rec, messages, runtime):
        started.set()
        assert release.wait(10)
        return opponent_with_patch(NUMERIC_PATCH)(rec, messages, runtime)

    monkeypatch.setattr(api, "generate_opponent_turn", blocking)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(auto_step, sid)
        assert started.wait(10)
        mid = auto_status(sid)
        assert mid["status"] == "running"
        assert mid["current_round"] == 1
        assert mid["last_error"] is None
        assert stored_document(sid)["auto_status"] == "running"

        busy = auto_step(sid)
        assert busy.status_code == 409
        assert busy.json()["error"] == "SESSION_BUSY"
        # 并发读取只见最后已提交状态，不见半成品。
        assert get_state(sid)["action_history"] == []
        release.set()
        resp = future.result(timeout=15)

    assert resp.status_code == 200, resp.text
    assert resp.json()["round"] == 1
    assert resp.json()["action_points_left"] == 4
    status = auto_status(sid)
    assert status["status"] == "paused"
    assert status["current_round"] == 1
    assert stored_document(sid)["auto_status"] == "paused"


def test_auto_status_session_not_found():
    resp = client.get("/session/nope/auto_status")
    assert resp.status_code == 404
    assert resp.json()["error"] == "SESSION_NOT_FOUND"
    assert set(resp.json()) == {"error", "detail"}


def test_auto_five_explicit_steps_commit_independently(monkeypatch):
    """芯片场景预算 5：5 次 auto_step = 5 个来回（10 手），恰好用完一个回合。"""
    sid = new_real_session()
    opponent_calls = script_opponent(monkeypatch, [NUMERIC_PATCH] * 5)
    previous = get_state(sid)

    for step in range(1, 6):
        resp = auto_step(sid)
        assert resp.status_code == 200, resp.text
        state = resp.json()
        # 前 4 手仍在同一回合，第 5 手用完预算才换回合。
        expected_round = 1 if step < 5 else 2
        assert state["round"] == expected_round
        assert state["action_points_left"] == (5 - step if step < 5 else 5)
        assert len(state["action_history"]) == len(previous["action_history"]) + 2
        assert state["status"] == "active"
        assert auto_status(sid) == {
            "session_id": sid,
            "status": "paused",
            "current_round": expected_round,
            "terminal_type": None,
            "last_error": None,
        }
        document = stored_document(sid)
        assert document["engine_state"]["round"] == state["round"]
        assert document["runtime"]["action_seq"] == step * 2
        assert document["runtime"]["offline_cursor"] == step
        assert document["auto_status"] == "paused"
        previous = state

    assert previous["round"] == 2
    assert len(previous["action_history"]) == 10
    assert opponent_calls == [0, 1, 2, 3, 4]
    final_document = stored_document(sid)
    assert get_state(sid) == previous
    assert auto_status(sid)["current_round"] == 2
    assert stored_document(sid) == final_document
    print(f"[five-full-steps] round={previous['round']} history={len(previous['action_history'])}")


def test_session_persistence_reload_restores_runtime_and_idempotency(monkeypatch):
    sid = new_real_session()
    opponent_calls = script_opponent(monkeypatch, [NUMERIC_PATCH])
    payload = {
        "action_type": "offer",
        "offer_patch": copy.deepcopy(NUMERIC_PATCH),
        "conditions": [],
        "expected_effect": "推动数值条款形成一致方案。",
        "public_message": "我方提出数值条款方案并继续磋商。",
        "client_action_id": "persist-action-1",
        "base_version": 0,
    }
    first = client.post(f"/session/{sid}/action", json=payload)
    assert first.status_code == 200, first.text
    before_document = stored_document(sid)

    api.SESSIONS.clear()
    assert get_state(sid) == first.json()
    replay = client.post(f"/session/{sid}/action", json=payload)
    assert replay.status_code == 200
    assert replay.content == first.content
    assert stored_document(sid) == before_document
    assert opponent_calls == [0]
    rec = api.SESSIONS[sid]
    assert rec.runtime.action_seq == 2
    assert rec.runtime.offline_cursor == 1
    assert len(rec.runtime.action_meta) == 2
    assert set(rec.idempotency_ledger) == {"persist-action-1"}


def test_auto_status_legacy_active_and_terminal_records(monkeypatch):
    active_sid = new_real_session()
    active_document = stored_document(active_sid)
    for key in api.AUTO_FIELDS:
        active_document.pop(key)
    api.get_session_store().write(active_document)
    api.SESSIONS.clear()
    assert auto_status(active_sid) == {
        "session_id": active_sid,
        "status": "paused",
        "current_round": 1,
        "terminal_type": None,
        "last_error": None,
    }

    terminal_sid = new_real_session()
    script_opponent(monkeypatch, [FULL_PATCH])
    assert auto_step(terminal_sid).status_code == 200
    assert auto_step(terminal_sid).status_code == 200
    terminal_document = stored_document(terminal_sid)
    for key in api.AUTO_FIELDS:
        terminal_document.pop(key)
    api.get_session_store().write(terminal_document)
    api.SESSIONS.clear()
    restored = auto_status(terminal_sid)
    assert restored["status"] == "done"
    assert restored["current_round"] == 1
    assert restored["terminal_type"] == "FULL_AGREEMENT"
    assert restored["last_error"] is None


def test_auto_status_interrupted_running_recovers_without_advancing():
    sid = new_real_session()
    before = get_state(sid)
    document = stored_document(sid)
    document["auto_status"] = "running"
    document["auto_terminal_type"] = None
    document["auto_last_error"] = None
    api.get_session_store().write(document)
    api.SESSIONS.clear()

    status = auto_status(sid)
    assert status["status"] == "paused"
    assert status["current_round"] == 1
    assert status["last_error"]["code"] == "AUTO_INTERRUPTED"
    assert get_state(sid) == before
    persisted = stored_document(sid)
    assert persisted["auto_status"] == "paused"
    assert persisted["auto_last_error"]["code"] == "AUTO_INTERRUPTED"
    assert persisted["engine_state"] == document["engine_state"]


def test_auto_status_record_invalid_and_unreadable_records():
    invalid_sid = new_real_session()
    before = get_state(invalid_sid)
    document = stored_document(invalid_sid)
    document["auto_status"] = "done"
    document["auto_terminal_type"] = "FULL_AGREEMENT"
    api.get_session_store().write(document)
    api.SESSIONS.clear()

    status = auto_status(invalid_sid)
    assert status["status"] == "error"
    assert status["last_error"]["code"] == "AUTO_RECORD_INVALID"
    rejected = auto_step(invalid_sid)
    assert rejected.status_code == 409
    assert rejected.json() == {
        "error": "AUTO_STATUS_ERROR",
        "detail": api.AUTO_STATUS_ERROR_DETAIL,
    }
    assert get_state(invalid_sid) == before

    unreadable_sid = new_real_session()
    api.get_session_store().path_for(unreadable_sid).write_text("{broken", encoding="utf-8")
    api.SESSIONS.clear()
    response = client.get(f"/session/{unreadable_sid}/auto_status")
    assert response.status_code == 500
    assert set(response.json()) == {"error", "detail"}
    assert response.json()["error"] == "INTERNAL_ERROR"


def test_auto_accept_redline_precheck_pauses_without_opponent(monkeypatch):
    sid = new_real_session()
    opponent_calls = script_opponent(monkeypatch, [FULL_PATCH])
    assert auto_step(sid).status_code == 200
    rec = api.SESSIONS[sid]
    rec.engine.state.offers[-1].clauses["芯片算力门槛"]["option"] = 100
    api.persist_session(
        rec, rec.engine, rec.runtime, rec.idempotency_ledger, "paused", None, None
    )
    before = get_state(sid)

    rejected = auto_step(sid)
    assert rejected.status_code == 400
    assert rejected.json()["error"] == "INVALID_ACTION"
    assert rejected.json()["engine_error"] == "REDLINE_VIOLATION"
    status = auto_status(sid)
    assert status["status"] == "paused"
    assert status["last_error"]["code"] == "REDLINE_VIOLATION"
    assert get_state(sid) == before
    assert opponent_calls == [0]


def test_auto_accept_without_counterpart_offer_pauses(monkeypatch):
    sid = new_real_session()
    rec = api.SESSIONS[sid]
    rec.engine.state.open_issues.clear()
    api.persist_session(
        rec, rec.engine, rec.runtime, rec.idempotency_ledger, "paused", None, None
    )
    opponent_calls = []
    monkeypatch.setattr(
        api, "generate_opponent_turn", lambda *args: opponent_calls.append(args) or {}
    )

    rejected = auto_step(sid)
    assert rejected.status_code == 400
    assert rejected.json()["error"] == "INVALID_ACTION"
    assert rejected.json()["engine_error"] == "NO_COUNTERPART_OFFER"
    assert auto_status(sid)["last_error"]["code"] == "NO_COUNTERPART_OFFER"
    assert opponent_calls == []
    assert get_state(sid)["action_history"] == []


def test_terminal_types_use_single_engine_source():
    from engine.terminal import TERMINAL_TYPES as ENGINE_TERMINAL_TYPES

    assert api.TERMINAL_TYPES is ENGINE_TERMINAL_TYPES
    assert set(api.TERMINAL_TYPES) == {
        "FULL_AGREEMENT",
        "PARTIAL_AGREEMENT",
        "WITHDRAWAL",
        "DEADLOCK",
        "ROUNDS_EXHAUSTED",
    }


def test_auto_busy_rejects_action_and_allows_other_session(monkeypatch):
    sid = new_real_session()
    other_sid = new_real_session()
    started = threading.Event()
    release = threading.Event()

    def controlled(rec, messages, runtime):
        if rec.session_id == sid:
            started.set()
            assert release.wait(10)
        return opponent_with_patch(NUMERIC_PATCH)(rec, messages, runtime)

    monkeypatch.setattr(api, "generate_opponent_turn", controlled)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(auto_step, sid)
        assert started.wait(10)
        try:
            busy = client.post(f"/session/{sid}/action", json={
                "action_type": "offer",
                "offer_patch": copy.deepcopy(NUMERIC_PATCH),
                "conditions": [],
                "expected_effect": "推动条款收敛。",
                "public_message": "我方提出条款方案。",
                "client_action_id": "busy-action-1",
                "base_version": 0,
            })
            assert busy.status_code == 409
            assert busy.json()["error"] == "SESSION_BUSY"
            assert auto_status(sid)["status"] == "running"
            other = auto_step(other_sid)
            assert other.status_code == 200, other.text
            assert other.json()["round"] == 1
        finally:
            release.set()
        response = future.result(timeout=15)

    assert response.status_code == 200, response.text
    assert response.json()["round"] == 1
    assert response.json()["action_points_left"] == 4
    assert len(response.json()["action_history"]) == 2


def test_session_store_atomic_write_failure_preserves_previous_document(monkeypatch):
    sid = new_real_session()
    store = api.get_session_store()
    before = store.read(sid)
    candidate = copy.deepcopy(before)
    candidate["auto_last_error"] = {"code": "TEST_ERROR", "detail": "测试故障。"}

    def fail_replace(source, target):
        raise OSError("injected")

    monkeypatch.setattr(api.session_store.os, "replace", fail_replace)
    with pytest.raises(api.session_store.SessionStoreBeforeReplace):
        store.write(candidate)
    assert store.read(sid) == before


def test_auto_persistence_failure_before_running_pauses_and_recovers(monkeypatch):
    sid = new_real_session()
    before = get_state(sid)
    original = api.session_store.SessionStore.write
    failures = []

    def fail_running_once(self, document):
        if document["session_id"] == sid and document["auto_status"] == "running" and not failures:
            failures.append(document["auto_status"])
            raise api.session_store.SessionStoreBeforeReplace()
        return original(self, document)

    monkeypatch.setattr(api.session_store.SessionStore, "write", fail_running_once)
    monkeypatch.setattr(api, "generate_opponent_turn", opponent_with_patch(NUMERIC_PATCH))
    failed = auto_step(sid)
    assert failed.status_code == 500
    assert failed.json()["error"] == "INTERNAL_ERROR"
    status = auto_status(sid)
    assert status["status"] == "paused"
    assert status["last_error"]["code"] == "AUTO_PERSISTENCE_FAILED"
    assert get_state(sid) == before
    assert failures == ["running"]

    recovered = auto_step(sid)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["round"] == 1
    assert recovered.json()["action_points_left"] == 4
    assert auto_status(sid)["last_error"] is None


def test_auto_persistence_failure_final_before_replace_recovers_paused(monkeypatch):
    sid = new_real_session()
    original = api.session_store.SessionStore.write
    failures = []

    def fail_final_once(self, document):
        if (
            document["session_id"] == sid
            and document["auto_status"] == "paused"
            and document["runtime"]["action_seq"] > 0
            and not failures
        ):
            failures.append(document["runtime"]["action_seq"])
            raise api.session_store.SessionStoreBeforeReplace()
        return original(self, document)

    monkeypatch.setattr(api.session_store.SessionStore, "write", fail_final_once)
    monkeypatch.setattr(api, "generate_opponent_turn", opponent_with_patch(NUMERIC_PATCH))
    failed = auto_step(sid)
    assert failed.status_code == 500
    status = auto_status(sid)
    assert status["status"] == "paused"
    assert status["current_round"] == 1
    assert status["last_error"]["code"] == "AUTO_PERSISTENCE_FAILED"
    assert get_state(sid)["action_history"] == []
    assert stored_document(sid)["runtime"]["action_seq"] == 0
    assert failures == [2]

    recovered = auto_step(sid)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["round"] == 1
    assert recovered.json()["action_points_left"] == 4
    assert auto_status(sid)["last_error"] is None


def test_auto_persistence_failure_commit_unknown_sets_error(monkeypatch):
    sid = new_real_session()
    original = api.session_store.SessionStore.write

    def commit_unknown(self, document):
        if (
            document["session_id"] == sid
            and document["auto_status"] == "paused"
            and document["runtime"]["action_seq"] > 0
        ):
            raise api.session_store.SessionStoreCommitUnknown()
        return original(self, document)

    monkeypatch.setattr(api.session_store.SessionStore, "write", commit_unknown)
    monkeypatch.setattr(api, "generate_opponent_turn", opponent_with_patch(NUMERIC_PATCH))
    failed = auto_step(sid)
    assert failed.status_code == 500
    status = auto_status(sid)
    assert status["status"] == "error"
    assert status["last_error"]["code"] == "AUTO_PERSISTENCE_FAILED"
    assert get_state(sid)["action_history"] == []
    assert stored_document(sid)["auto_status"] == "running"
    rejected = auto_step(sid)
    assert rejected.status_code == 409
    assert rejected.json()["error"] == "AUTO_STATUS_ERROR"



def test_auto_persistence_failure_writing_business_pause_sets_error(monkeypatch):
    sid = new_real_session()
    original = api.session_store.SessionStore.write

    def fail_business_pause(self, document):
        error = document.get("auto_last_error") or {}
        if document["session_id"] == sid and error.get("code") == "MODEL_UNAVAILABLE":
            raise api.session_store.SessionStoreBeforeReplace()
        return original(self, document)

    def unavailable(*args):
        raise api.ModelUnavailable()

    monkeypatch.setattr(api.session_store.SessionStore, "write", fail_business_pause)
    monkeypatch.setattr(api, "generate_opponent_turn", unavailable)
    failed = auto_step(sid)
    assert failed.status_code == 500
    status = auto_status(sid)
    assert status["status"] == "error"
    assert status["last_error"]["code"] == "AUTO_PERSISTENCE_FAILED"
    assert stored_document(sid)["auto_status"] == "running"
    assert get_state(sid)["action_history"] == []
    rejected = auto_step(sid)
    assert rejected.status_code == 409
    assert rejected.json()["error"] == "AUTO_STATUS_ERROR"
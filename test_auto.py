"""自动推演（auto_step / auto_status）状态机与 B 真实场景端到端验证。

场景来源：`scenario agent v2/data/scenarios/main_chip_controls.json`，
经 load_scenario.py（C 侧 load_scenario_bridge）转换，不使用最小场景。
对手由脚本替身驱动（离线样本的条款名与真实场景不匹配），我方行动完全由
api.build_auto_action 自动决策：open_issues 非空时 statement，为空时 accept。
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
    """按调用次序依次使用 patches 中的报价，超出后沿用最后一份。"""
    calls = []

    def respond(rec, messages, runtime):
        index = min(len(calls), len(patches) - 1)
        calls.append(index)
        return opponent_with_patch(patches[index])(rec, messages, runtime)

    monkeypatch.setattr(api, "generate_opponent_turn", respond)
    return calls


def test_real_scenario_five_steps_to_full_agreement(monkeypatch):
    """连续推演 5 步：前 4 步双方行动后落盘，第 5 步我方自动 accept 抵达终局。"""
    sid = new_real_session()
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
    for step in range(1, 6):
        resp = auto_step(sid)
        assert resp.status_code == 200, resp.text
        state = resp.json()
        seen_rounds.append(state["round"])
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
            assert mine["action_type"] == "statement"
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

    assert seen_rounds == [2, 3, 4, 5, 5]
    assert opponent_calls == [0, 1, 2, 3]  # 终局步不再调用对手
    assert stored_document(sid)["auto_status"] == "done"
    assert stored_document(sid)["auto_terminal_type"] == "FULL_AGREEMENT"


def test_auto_step_after_done_rejected_and_status_survives_reload(monkeypatch):
    """终局后拒绝继续推进；状态存于会话记录，服务重启（内存清空）后仍可恢复。"""
    sid = new_real_session()
    script_opponent(monkeypatch, [FULL_PATCH])
    assert auto_step(sid).status_code == 200
    assert auto_step(sid).status_code == 200
    before = get_state(sid)
    assert before["status"] == "ended"
    assert auto_status(sid)["status"] == "done"

    resp = auto_step(sid)
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "PHASE_CLOSED"
    assert body["auto_status"] == "done"
    assert body["terminal_type"] == "FULL_AGREEMENT"
    assert body["current_round"] == before["round"]
    assert get_state(sid) == before
    assert auto_status(sid)["status"] == "done"

    # 模拟服务重启：内存会话清空，从磁盘记录恢复终局状态。
    api.SESSIONS.clear()
    restored = auto_status(sid)
    assert restored["status"] == "done"
    assert restored["terminal_type"] == "FULL_AGREEMENT"
    assert restored["current_round"] == before["round"]
    assert restored["last_error"] is None
    rejected = auto_step(sid)
    assert rejected.status_code == 409
    assert rejected.json()["error"] == "PHASE_CLOSED"
    assert get_state(sid) == before


def test_auto_timeout_pauses_then_resume_recovers(monkeypatch):
    """人为制造模型超时：自动暂停置 paused 并落盘，再次 auto_step 即恢复。"""
    monkeypatch.delenv("NEG_OFFLINE", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    sid = new_real_session()
    rec = api.SESSIONS[sid]
    assert rec.mode == "online"
    archive = copy.deepcopy(rec.engine.state.to_archive_dict())

    def timeout_once(req, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(neg.urllib.request, "urlopen", timeout_once)
    monkeypatch.setattr(
        neg.time, "sleep", lambda _: pytest.fail("60 秒超时后不应继续内层重试")
    )

    failed = auto_step(sid)
    assert failed.status_code == 503
    assert failed.json()["error"] == "MODEL_UNAVAILABLE"

    status = auto_status(sid)
    assert status["status"] == "paused"
    assert status["current_round"] == 1
    assert status["terminal_type"] is None
    assert status["last_error"]["code"] == "MODEL_UNAVAILABLE"
    assert status["last_error"]["detail"]

    # 失败步零推进，paused 与错误原因均已落盘，锁已释放。
    state = get_state(sid)
    assert state["round"] == 1
    assert state["action_history"] == []
    assert rec.engine.state.to_archive_dict() == archive
    assert rec.runtime.action_seq == 0
    document = stored_document(sid)
    assert document["auto_status"] == "paused"
    assert document["auto_last_error"]["code"] == "MODEL_UNAVAILABLE"
    assert document["engine_state"]["round"] == 1
    assert not rec.mutation_lock.locked()
    print(f"[timeout] paused at round={status['current_round']} error={status['last_error']['code']}")

    # 对手恢复可用后，再次调用 auto_step 即恢复推进，无需额外复位接口。
    monkeypatch.setattr(api, "generate_opponent_turn", opponent_with_patch(FULL_PATCH))
    resumed = auto_step(sid)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["round"] == 2
    assert len(resumed.json()["action_history"]) == 2
    status = auto_status(sid)
    assert status["status"] == "paused"
    assert status["last_error"] is None
    assert stored_document(sid)["auto_last_error"] is None

    # 恢复后能继续推演到终局。
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
    assert resp.json()["round"] == 2
    status = auto_status(sid)
    assert status["status"] == "paused"
    assert status["current_round"] == 2
    assert stored_document(sid)["auto_status"] == "paused"


def test_auto_status_session_not_found():
    resp = client.get("/session/nope/auto_status")
    assert resp.status_code == 404
    assert resp.json()["error"] == "SESSION_NOT_FOUND"
    assert set(resp.json()) == {"error", "detail"}
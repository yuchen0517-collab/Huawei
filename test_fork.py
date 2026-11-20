"""按手快照、分支推演、接管与两支对比的验收测试。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api
import session_store
from _scenario_fixtures import LEGACY_ID, LEGACY_PATH
from load_scenario import load_scenario

ROOT = Path(__file__).resolve().parent
CHIP_PATH = ROOT / "scenario agent v2" / "data" / "scenarios" / "main_chip_controls.json"
AGENTS = json.loads((ROOT / "agents.json").read_text(encoding="utf-8-sig"))
CN_MARKERS = [task["text"] for task in AGENTS["_scenario"]["player"]["hidden_tasks"]]
CN_MARKERS.append("全球AI治理研究院")
US_MARKERS = [
    AGENTS["us"]["hidden_task_card"],
    "为技术监控铺路",
    "确保对中国的 AI 技术限制不被谈判决议削弱",
]

client = TestClient(api.app, raise_server_exceptions=False)

OFFER_A = {
    "action_type": "offer",
    "offer_patch": {
        "全球算力资源分配": {
            "option": "附带可核查机制",
            "note": "我方提出可核查机制方案。",
        }
    },
    "conditions": [],
    "expected_effect": "",
    "public_message": "我方提出可核查机制方案，供各方讨论。",
}
OFFER_B = copy.deepcopy(OFFER_A)
OFFER_B["offer_patch"]["全球算力资源分配"] = {
    "option": "以既有联盟实践为蓝本设立高风险 AI 出口管制的可核查机制",
    "note": "我方改为以既有联盟实践为蓝本。",
}
OFFER_B["public_message"] = "我方改为以既有联盟实践为蓝本的方案，供各方讨论。"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.setenv("NEG_OFFLINE", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("NEG_SESSION_STORE_DIR", str(tmp_path))
    api.SESSIONS.clear()
    api.FORK_LEDGER.clear()
    yield
    api.SESSIONS.clear()
    api.FORK_LEDGER.clear()


def new_session(scenario_path: Path | None = None) -> str:
    body = {
        "scenario_id": LEGACY_ID,
        "agent": "us",
        "scenario_path": LEGACY_PATH,
    }
    if scenario_path is not None:
        body["scenario_id"] = load_scenario(scenario_path)["scenario_id"]
        body["scenario_path"] = str(scenario_path)
    resp = client.post("/session", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def get_state(sid: str) -> dict:
    resp = client.get(f"/session/{sid}/state")
    assert resp.status_code == 200, resp.text
    return resp.json()


def act(sid: str, payload: dict, client_id: str) -> dict:
    state = get_state(sid)
    body = copy.deepcopy(payload)
    body["client_action_id"] = client_id
    body["base_version"] = state["version"]
    resp = client.post(f"/session/{sid}/action", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def fork(sid: str, body: dict, key: str | None = None) -> dict:
    headers = {"Idempotency-Key": key} if key else None
    resp = client.post(f"/session/{sid}/fork", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def conversation_versions(sid: str) -> list[int]:
    return [item["version"] for item in api.SESSIONS[sid].snapshots]


def test_fork_does_not_touch_original_session():
    sid = new_session()
    before = get_state(sid)
    before_bytes = api.get_session_store().path_for(sid).read_bytes()

    child = fork(sid, {"at_version": 0})
    assert child["session_id"] != sid

    after = get_state(sid)
    after_bytes = api.get_session_store().path_for(sid).read_bytes()
    assert json.dumps(after, ensure_ascii=False, sort_keys=True) == json.dumps(
        before, ensure_ascii=False, sort_keys=True
    )
    assert after_bytes == before_bytes


def test_fork_replays_round_version_offers_and_open_issues():
    sid = new_session()
    midpoint = act(sid, OFFER_A, "fork-state-1")
    child = fork(sid, {"at_version": midpoint["version"], "at_action_id": "a000002"})

    assert child["session_id"] != sid
    for field in ("round", "version", "my_offer", "opponent_offer", "open_issues"):
        assert child[field] == midpoint[field], field
    assert get_state(child["session_id"]) == child


def test_fork_to_version_zero_is_available():
    sid = new_session()
    initial = get_state(sid)
    child = fork(sid, {"at_version": 0})

    assert child["session_id"] != sid
    assert child["version"] == 0
    assert child["round"] == 1
    assert child["my_offer"] == {"version": 0, "offers": {}}
    assert child["open_issues"] == initial["open_issues"]
    assert child["action_history"] == []


def test_fork_beyond_current_version_conflicts():
    sid = new_session()
    act(sid, OFFER_A, "fork-beyond-1")

    resp = client.post(f"/session/{sid}/fork", json={"at_version": 999})
    assert resp.status_code == 409
    assert resp.json()["error"] == "VERSION_CONFLICT"
    assert "没有可用快照" in resp.json()["detail"]

    resp = client.post(f"/session/{sid}/fork", json={"at_action_id": "a999999"})
    assert resp.status_code == 409
    assert resp.json()["error"] == "VERSION_CONFLICT"

    resp = client.post(f"/session/{sid}/fork", json={})
    assert resp.status_code == 422
    assert resp.json()["error"] == "INVALID_REQUEST"

    resp = client.post(
        f"/session/{sid}/fork",
        json={"at_version": 0, "at_action_id": "a000002"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_REQUEST"


def test_fork_by_action_id_and_idempotency_key_replay():
    sid = new_session()
    midpoint = act(sid, OFFER_A, "fork-idem-1")

    first = fork(sid, {"at_action_id": "a000002"}, key="fork-key-1")
    replay = fork(sid, {"at_action_id": "a000002"}, key="fork-key-1")
    assert replay["session_id"] == first["session_id"]
    assert first["version"] == midpoint["version"]
    assert len(api.FORK_LEDGER) == 1

    other = fork(sid, {"at_version": 0}, key="fork-key-2")
    assert other["session_id"] != first["session_id"]


def test_compare_same_source_and_null_terminal():
    sid = new_session()
    child = fork(sid, {"at_version": 0})

    resp = client.get(f"/session/{sid}/compare", params={"other": child["session_id"]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["left"]["session_id"] == sid
    assert body["right"]["session_id"] == child["session_id"]
    assert body["left"]["terminal_type"] is None
    assert body["right"]["terminal_type"] is None
    assert isinstance(body["left"]["round"], int)
    assert isinstance(body["left"]["evaluation"], dict)
    assert "batna_comparison" in body["left"]["evaluation"]

    chip = new_session(CHIP_PATH)
    resp = client.get(f"/session/{sid}/compare", params={"other": chip})
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_REQUEST"


def test_compare_diff_only_lists_different_clause_values(monkeypatch):
    # 固定对手只报数值条款：否则对手的收敛报价会覆盖两支分支在同一枚举条款上的
    # 差异，对比结果看起来「没有分歧」，而本用例要验的正是差异定位。
    fixed = api.offline_opponent.build_offline_turn(load_scenario(LEGACY_PATH), 0)
    monkeypatch.setattr(api, "generate_opponent_turn", lambda *args: copy.deepcopy(fixed))
    sid = new_session()
    midpoint = act(sid, OFFER_A, "compare-diff-1")
    child_id = fork(sid, {"at_version": midpoint["version"]})["session_id"]
    act(child_id, OFFER_B, "compare-diff-2")

    body = client.get(f"/session/{sid}/compare", params={"other": child_id}).json()
    assert body["diff"]
    for item in body["diff"]:
        assert set(item) == {"clause", "left", "right"}
        assert item["left"] != item["right"]
    clauses = {item["clause"] for item in body["diff"]}
    assert "前沿模型评测门槛" not in clauses
    assert "全球算力资源分配" in clauses
    assert body["diverged_at"] == {
        "version": midpoint["version"],
        "action_id": "a000002",
    }


def test_takeover_running_to_paused_and_paused_is_idempotent():
    sid = new_session()
    rec = api.SESSIONS[sid]
    rec.auto_status = "running"
    rec.auto_terminal_type = None
    rec.auto_last_error = api.AutoError("AUTO_TEST", "自动推演过程中的错误必须保留。")

    resp = client.post(f"/session/{sid}/takeover")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "paused"
    assert body["last_error"] == {
        "code": "AUTO_TEST",
        "detail": "自动推演过程中的错误必须保留。",
    }
    document = api.get_session_store().read(sid)
    assert document["auto_status"] == "paused"
    assert document["auto_last_error"] == {
        "code": "AUTO_TEST",
        "detail": "自动推演过程中的错误必须保留。",
    }

    again = client.post(f"/session/{sid}/takeover")
    assert again.status_code == 200
    assert again.json() == body


def test_takeover_busy_returns_session_busy_with_retry_after():
    sid = new_session()
    rec = api.SESSIONS[sid]
    assert rec.mutation_lock.acquire(blocking=False)
    try:
        resp = client.post(f"/session/{sid}/takeover")
        assert resp.status_code == 409
        assert resp.json()["error"] == "SESSION_BUSY"
        assert resp.json()["retry_after"] == 1
    finally:
        rec.mutation_lock.release()


def test_snapshot_history_keeps_only_latest_twenty():
    sid = new_session()
    rec = api.SESSIONS[sid]
    engine = api.restore_engine(rec.engine)
    runtime = rec.runtime
    for step in range(1, 22):
        action_id = api.make_action_id(step)
        engine.state.public_events.append({
            "type": "action",
            "action_id": action_id,
            "actor": "cn",
            "action_type": "statement",
            "card_id": None,
            "round": 1,
            "offer_patch": {},
            "conditions": [],
            "expected_effect": "",
            "public_message": f"第 {step} 手公开表态。",
        })
        engine.state.current_version = step
        runtime = api.RuntimeMetadata(
            messages=runtime.messages,
            offline_cursor=0,
            action_seq=step,
            action_meta=runtime.action_meta + ((action_id, "human", ()),),
        )
        api.persist_session(
            rec, engine, runtime, rec.idempotency_ledger,
            "paused", None, None, 0,
        )

    assert len(conversation_versions(sid)) == api.SNAPSHOT_LIMIT
    assert conversation_versions(sid) == list(range(2, 22))
    document = api.get_session_store().read(sid)
    assert len(document["snapshots"]) == api.SNAPSHOT_LIMIT
    assert 0 not in [item["version"] for item in document["snapshots"]]


def test_fork_and_compare_never_serialize_private_markers():
    sid = new_session()
    midpoint = act(sid, OFFER_A, "leak-1")
    child = fork(sid, {"at_version": midpoint["version"]})
    comparison = client.get(
        f"/session/{sid}/compare", params={"other": child["session_id"]}
    ).json()

    markers = CN_MARKERS + US_MARKERS
    for payload, location in ((child, "fork"), (comparison, "compare")):
        serialized = json.dumps(payload, ensure_ascii=False)
        for marker in markers:
            assert marker not in serialized, f"{location} 泄露私有信息：{marker}"
        for forbidden in (
            "private_state_by_party", "hidden_tasks", "hidden_task_card", "_visibility",
        ):
            assert forbidden not in serialized, f"{location} 泄露 {forbidden}"


def test_fork_keeps_clause_roles_from_override_layer():
    sid = new_session(CHIP_PATH)
    child = fork(sid, {"at_version": 0})
    child_rec = api.SESSIONS[child["session_id"]]

    roles = child_rec.engine.scenario.get("clause_roles")
    assert roles == {
        "condition": "第三国再出口限制",
        "performance": "关键矿产出口安排",
        "exit": "协议退出与救济安排",
    }
    cards = {item["id"]: item for item in child["available_cards"]}
    assert cards["effective_condition"]["target_clause"] == "第三国再出口限制"
    assert cards["performance_node"]["target_clause"] == "关键矿产出口安排"
    assert cards["exit_clause"]["target_clause"] == "协议退出与救济安排"


def test_session_document_round_trips_snapshots_atomically():
    sid = new_session()
    act(sid, OFFER_A, "round-trip-1")
    document = api.get_session_store().read(sid)

    assert document["snapshots"]
    assert session_store.canonical_json(document) == session_store.canonical_json(
        json.loads(session_store.canonical_json(document))
    )
    decoded = api.decode_session_document(document)
    assert decoded.snapshots == document["snapshots"]
    assert decoded.runtime.action_seq == document["snapshots"][-1]["action_seq"]
    assert decoded.session_id == sid
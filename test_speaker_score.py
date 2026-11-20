"""speaker_score 规则启发式与终局收口测试（封板日 11/20）。

覆盖：
- 未评分给 null，不给 0；
- 形状 / 键名 / 0..100 整数 / feedback ≤60 字 / source 固定 rule；
- 同一局重跑两次分数一致（确定性）；
- 三个开关分支：rule / passthrough / off；
- 终局 debrief 的 evaluation.learning_performance 与投影同源；
- 终局后 /action 与 /auto_step 均拒绝 ROUND_LOCKED。
"""

import copy
import json

import pytest
from fastapi.testclient import TestClient

import api
from _scenario_fixtures import legacy_body

client = TestClient(api.app, raise_server_exceptions=False)

REAL_SCENARIO_PATH = "scenario agent v2/data/scenarios/main_chip_controls.json"
REAL_SCENARIO_ID = "scn-chip-controls-0001"

NUMERIC_PATCH = {
    "芯片算力门槛": {"option": 1000, "note": "位于中方 800 以上、美方 1500 以下的安全区间。"},
}
FULL_PATCH = {
    **NUMERIC_PATCH,
    "第三国再出口限制": {"option": "O2", "note": "避开美方对 O1 的硬红线。"},
    "关键矿产出口安排": {"option": "O2", "note": "避开中方对 O3/O4 的硬红线。"},
    "协议退出与救济安排": {"option": "O2", "note": "双方都可接受的协商延长履约期。"},
}

SPEAKER_KEYS = {
    "total", "position_clarity", "diplomatic_tact",
    "emotional_control", "substance_quality", "feedback", "source",
}

AI_OFFER = {
    "client_action_id": "req-score-1",
    "base_version": 0,
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

AI_FULL_OFFER = {
    "client_action_id": "demo-ai-1",
    "base_version": 0,
    "action_type": "offer",
    "card_id": None,
    "offer_patch": {
        "全球算力资源分配": {
            "option": "接受联合国框架下的技术性通报，但监督机制须具备实际约束力",
            "note": "给出可核查的对称安排。",
        },
        "前沿模型评测门槛": {"option": 55, "note": "维持场景初始门槛。"},
        "数据跨境流动": {
            "option": "在联合国框架下建立对称适用的数据跨境通报机制",
            "note": "以多边通报替代单边裁量。",
        },
    },
    "conditions": [],
    "expected_effect": "给出可讨论的具体方案，推动分歧收敛。",
    "public_message": "我方就相关条款提出具体方案，愿在相互尊重基础上继续磋商。",
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.setenv("NEG_OFFLINE", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("NEG_SESSION_STORE_DIR", str(tmp_path))
    monkeypatch.setattr(api, "SPEAKER_SCORE_MODE", "rule")
    api.SESSIONS.clear()
    yield
    api.SESSIONS.clear()


def new_ai_session():
    resp = client.post("/session", json=legacy_body())
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def new_chip_session():
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


def script_opponent(monkeypatch, patches):
    calls = []

    def respond(rec, messages, runtime, *extra):
        index = min(len(calls), len(patches) - 1)
        calls.append(index)
        return {
            "action": {
                "action_type": "offer",
                "offer_patch": copy.deepcopy(patches[index]),
                "conditions": [],
                "expected_effect": "就条款取值给出具体方案，推动分歧收敛。",
            },
            "public_message": "我方就相关条款提出具体方案，愿在相互尊重基础上继续磋商并寻求一致。",
        }

    monkeypatch.setattr(api, "generate_opponent_turn", respond)
    return calls


def assert_score_shape(score):
    assert set(score) == SPEAKER_KEYS
    for key in ("total", "position_clarity", "diplomatic_tact",
                "emotional_control", "substance_quality"):
        assert isinstance(score[key], int)
        assert 0 <= score[key] <= 100
    assert isinstance(score["feedback"], str) and score["feedback"]
    assert len(score["feedback"]) <= 60
    assert score["source"] == "rule"


def test_speaker_score_null_before_first_action():
    sid = new_ai_session()
    state = get_state(sid)
    assert state["action_history"] == []
    assert state["speaker_score"] is None


def test_speaker_score_shape_and_determinism():
    sid = new_ai_session()
    first = client.post(f"/session/{sid}/action", json=AI_OFFER)
    assert first.status_code == 200, first.text
    score = first.json()["speaker_score"]
    assert_score_shape(score)

    # 同一局连续读取两次，分数必须逐字节一致。
    assert get_state(sid)["speaker_score"] == score
    assert get_state(sid)["speaker_score"] == score

    # 同场景、同行动、同脚本对手的另一局，重跑分数也必须一致。
    other = new_ai_session()
    replay = client.post(f"/session/{other}/action", json=AI_OFFER)
    assert replay.status_code == 200, replay.text
    assert replay.json()["speaker_score"] == score



def test_speaker_score_mode_switch(monkeypatch):
    sid = new_ai_session()
    assert client.post(f"/session/{sid}/action", json=AI_OFFER).status_code == 200
    assert get_state(sid)["speaker_score"] is not None

    assert api.SPEAKER_SCORE_STRATEGIES["passthrough"](None, None, {}, []) is None
    assert api.SPEAKER_SCORE_STRATEGIES["off"](None, None, {}, []) is None

    monkeypatch.setattr(api, "SPEAKER_SCORE_MODE", "passthrough")
    assert get_state(sid)["speaker_score"] is None

    monkeypatch.setattr(api, "SPEAKER_SCORE_MODE", "off")
    assert get_state(sid)["speaker_score"] is None

    monkeypatch.setattr(api, "SPEAKER_SCORE_MODE", "rule")
    assert get_state(sid)["speaker_score"] is not None


def test_debrief_not_available_before_terminal():
    sid = new_ai_session()
    resp = client.post(f"/session/{sid}/debrief")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "DEBRIEF_NOT_AVAILABLE"
    assert body["fail_reason"] == "谈判尚未结束，复盘暂不可用"


def test_terminal_action_lock_precedes_card_validation():
    """终局后必须先返回 ROUND_LOCKED，不能被卡牌层的 400 抢先。"""
    sid = new_ai_session()
    assert client.post(f"/session/{sid}/action", json=AI_FULL_OFFER).status_code == 200
    # 不写死步数：离线对手的收敛轮数会随场景条款数变化，推进到终局即可。
    for _ in range(8):
        if get_state(sid)["status"] == "ended":
            break
        assert client.post(f"/session/{sid}/auto_step").status_code == 200
    before = get_state(sid)
    assert before["status"] == "ended"

    # 这个单手报价在卡牌层会先命中 SELF_REVISION_LOCKED；终局锁必须优先。
    payload = {
        "client_action_id": "demo-after-terminal",
        "base_version": before["version"],
        "action_type": "offer",
        "offer_patch": {
            "全球算力资源分配": {
                "option": "接受联合国框架下的技术性通报，但监督机制须具备实际约束力",
                "note": "终局后推进。",
            }
        },
        "conditions": [],
        "expected_effect": "",
        "public_message": "终局后再推进一手。",
    }
    rejected = client.post(f"/session/{sid}/action", json=payload)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["error"] == "ROUND_LOCKED"
    assert rejected.json()["engine_error"] == "PHASE_CLOSED"
    assert get_state(sid) == before


def test_terminal_debrief_learning_performance_and_round_lock(monkeypatch):
    sid = new_chip_session()
    script_opponent(monkeypatch, [NUMERIC_PATCH, NUMERIC_PATCH, NUMERIC_PATCH, FULL_PATCH])
    for _ in range(5):
        resp = client.post(f"/session/{sid}/auto_step")
        assert resp.status_code == 200, resp.text
    state = get_state(sid)
    assert state["status"] == "ended"
    assert state["speaker_score"] is not None
    assert_score_shape(state["speaker_score"])

    debrief = client.post(f"/session/{sid}/debrief")
    assert debrief.status_code == 200, debrief.text
    body = debrief.json()
    assert set(body) == {"debrief", "evaluation"}
    evaluation = body["evaluation"]
    assert evaluation["terminal_type"] == "FULL_AGREEMENT"
    assert evaluation["agreement_quality"]["coverage"] == 1.0
    assert evaluation["learning_performance"] == state["speaker_score"]
    assert evaluation["learning_performance"]["source"] == "rule"
    # 终局三件套：终局类型、协议质量、BATNA 比较、红线检查、证据链接。
    assert "batna_comparison" in evaluation
    assert "redline_check" in evaluation
    assert isinstance(evaluation["evidence_links"], list) and evaluation["evidence_links"]
    assert body["debrief"]["visibility"] == "debrief"
    assert body["debrief"]["status"] == "ended"
    assert body["debrief"]["terminal"]["type"] == "FULL_AGREEMENT"
    assert body["debrief"]["agreement"] is not None

    before = get_state(sid)
    locked_action = {
        "client_action_id": "req-after-terminal",
        "base_version": before["version"],
        "action_type": "offer",
        "offer_patch": copy.deepcopy(FULL_PATCH),
        "conditions": [],
        "expected_effect": "",
        "public_message": "终局后再推进一手。",
    }
    rejected = client.post(f"/session/{sid}/action", json=locked_action)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["error"] == "ROUND_LOCKED"
    assert rejected.json()["engine_error"] == "PHASE_CLOSED"

    rejected_auto = client.post(f"/session/{sid}/auto_step")
    assert rejected_auto.status_code == 409, rejected_auto.text
    assert rejected_auto.json()["error"] == "ROUND_LOCKED"
    assert rejected_auto.json()["engine_error"] == "PHASE_CLOSED"

    assert get_state(sid) == before
    again = client.post(f"/session/{sid}/debrief")
    assert again.status_code == 200
    assert again.json() == body
    json.dumps(again.json(), ensure_ascii=False)
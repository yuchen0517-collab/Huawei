# -*- coding: utf-8 -*-
"""端到端实测：带 effect_labels 的 statement 是否走标签路径结算 Image/Trust。

对照三组（同一 action_type=statement，仅标签不同）：
  A) personal_attack/major   —— 应大幅扣 Image
  B) constructive_proposal/moderate —— 应加 Image
  C) 不带 effect_labels       —— 应走路径2 兜底（reason 为 action_type 推导）
"""
import os
import sys

os.environ["NEG_OFFLINE"] = "1"
os.environ.pop("DEEPSEEK_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient

import api

client = TestClient(api.app)

ATTACK_MSG = "我方对有关方面一味推诿、出尔反尔的做法表示强烈不满，这种态度令人无法接受。"
CONSTRUCTIVE_MSG = "我方愿在联合国框架下提出兼顾各方关切的建设性方案，推动磋商取得实质进展。"


def make_session():
    resp = client.post("/session", json={"scenario_id": "ai_governance", "agent": "us"})
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def play_statement(sid, message, labels=None):
    payload = {
        "action_type": "statement",
        "offer_patch": {},
        "conditions": [],
        "expected_effect": "",
        "public_message": message,
    }
    if labels:
        payload["effect_labels"] = labels
    resp = client.post(f"/session/{sid}/action", json=payload)
    assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"


def report(title, sid, before):
    engine = api.SESSIONS[sid].engine
    after = engine.state.indices["cn"]
    changes = [
        e for e in engine.state.public_events
        if e.get("type") == "index_change" and e.get("party") == "cn"
    ]
    print(f"\n=== {title} ===")
    print(f"  Image: {before['image']} -> {after['image']}   Trust: {before['trust']} -> {after['trust']}")
    for e in changes:
        print(f"  [{e['index']}] {e['before']} -> {e['after']} (delta={e['delta']:+d})  reason={e['reason']}")
    return changes


def snapshot(sid):
    return dict(api.SESSIONS[sid].engine.state.indices["cn"])


def label_mode(sid, actor="cn"):
    """取指定行动方最近一次行动的 label_mode（默认 cn=客户端玩家）。"""
    log = api.SESSIONS[sid].engine.state.behavior_log
    mine = [entry for entry in log if entry.get("actor") == actor]
    return mine[-1].get("label_mode") if mine else None


def main():
    # A: 人身攻击标签
    sid_a = make_session()
    before_a = snapshot(sid_a)
    play_statement(sid_a, ATTACK_MSG, labels=[
        {"label": "personal_attack", "magnitude": "major", "clause": None,
         "reason": "发言含明显指责与情绪化表达"},
    ])
    ev_a = report("A) statement + personal_attack/major", sid_a, before_a)

    # B: 建设性表态标签
    sid_b = make_session()
    before_b = snapshot(sid_b)
    play_statement(sid_b, CONSTRUCTIVE_MSG, labels=[
        {"label": "constructive_proposal", "magnitude": "moderate", "clause": None,
         "reason": "主动提出兼顾各方的方案"},
    ])
    ev_b = report("B) statement + constructive_proposal/moderate", sid_b, before_b)

    # C: offer 不带标签，走路径2 兜底（statement 兜底为 procedural/slight，delta=0 是设计行为）
    sid_c = make_session()
    before_c = snapshot(sid_c)
    resp = client.post(f"/session/{sid_c}/action", json={
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
    })
    assert resp.status_code == 200, resp.text
    ev_c = report("C) offer 无 effect_labels（兜底推导）", sid_c, before_c)

    print("\n=== 判定 ===")
    ok = True
    a_image = [e for e in ev_a if e["index"] == "image"]
    b_image = [e for e in ev_b if e["index"] == "image"]
    if a_image and a_image[0]["delta"] < 0 and label_mode(sid_a) == "effect_labels":
        print("A 通过：personal_attack 走了标签路径（label_mode=effect_labels），Image 下降")
    else:
        ok = False
        print("A 失败：未观察到标签路径的 Image 下降")
    if b_image and b_image[0]["delta"] > 0 and label_mode(sid_b) == "effect_labels":
        print("B 通过：constructive_proposal 走了标签路径（label_mode=effect_labels），Image 上升")
    else:
        ok = False
        print("B 失败：未观察到标签路径的 Image 上升")
    if ev_c and label_mode(sid_c) == "fallback":
        print("C 通过：无标签时走路径2 兜底推导（label_mode=fallback）")
    else:
        ok = False
        print("C 失败：兜底路径不符合预期")
    print("\n总体：" + ("全部通过" if ok else "存在失败项"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

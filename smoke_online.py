"""真机冒烟：用真实 Key 跑一局芯片场景，检查对手 Prompt 与接口行为。

用法：
    $env:DEEPSEEK_API_KEY = "sk-xxxx"; .venv\\Scripts\\python.exe smoke_online.py
    # 未设环境变量时，依次回落到 上级目录/key.txt、仓库根/key.txt

退出码：0 = 成功；2 = 模型不可用（Key 失效等，已确认状态未被污染）；3 = 其他失败。

只发一手行动（我方报价 + 对手回应），用于确认：
1. 对手按场景议题发言，而不是 AI 治理题材；
2. 不多轮次、不泄露我方私牌；
3. 失败时 503 且谈判状态不被污染。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CHIP_PATH = "scenario agent v2/data/scenarios/main_chip_controls.json"
CHIP_ID = "scn-chip-controls-0001"
CN_HIDDEN = "把第三国转口条款的讨论拖到关键矿产安排之后"
CLAUSES = ("芯片算力门槛", "第三国再出口限制", "关键矿产出口安排", "协议退出与救济安排")

OFFER = {
    "client_action_id": "smoke-1",
    "base_version": 0,
    "action_type": "offer",
    "card_id": None,
    "offer_patch": {
        "芯片算力门槛": {"option": 1200, "note": "我方提出可获许可的算力门槛。"},
        "第三国再出口限制": {"option": "O2", "note": "仅对实体清单对象要求许可。"},
    },
    "conditions": [],
    "expected_effect": "把分歧收敛到算力门槛与转口条款。",
    "public_message": "我方愿在可核查的前提下讨论算力门槛与转口安排。",
}


def resolve_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    for candidate in (BASE_DIR.parent / "key.txt", BASE_DIR / "key.txt"):
        if candidate.exists():
            return candidate.read_text(encoding="utf-8-sig").strip()
    return ""


def main() -> int:
    key = resolve_key()
    if not key:
        print("[错误] 未找到 Key：请设置 DEEPSEEK_API_KEY，或把 key.txt 放在仓库根/上级目录。")
        return 3
    os.environ["DEEPSEEK_API_KEY"] = key
    os.environ.pop("NEG_OFFLINE", None)
    os.environ["NEG_SESSION_STORE_DIR"] = tempfile.mkdtemp(prefix="smoke-")

    import api
    from fastapi.testclient import TestClient

    client = TestClient(api.app, raise_server_exceptions=False)
    created = client.post(
        "/session",
        json={"scenario_id": CHIP_ID, "agent": "us", "scenario_path": CHIP_PATH},
    )
    if created.status_code != 200:
        print("[失败] 建会话：", created.status_code, created.text[:300])
        return 3
    session_id = created.json()["session_id"]
    rec = api.SESSIONS[session_id]
    print(f"会话模式={rec.mode} prompt={len(rec.system_prompt)}字 初始指数={rec.initial_indexes}")
    if "芯片算力门槛" not in rec.system_prompt or "全球AI治理" in rec.system_prompt:
        print("[失败] 对手 Prompt 不是按场景生成的")
        return 3

    before = {
        "round": rec.engine.state.round,
        "version": rec.engine.state.current_version,
        "history": len(rec.engine.state.seen_action_ids),
    }
    started = time.time()
    response = client.post(f"/session/{session_id}/action", json=OFFER)
    elapsed = round(time.time() - started, 1)
    print(f"行动响应：{response.status_code}（{elapsed}s）")

    if response.status_code != 200:
        body = response.json()
        error = body.get("error")
        after = {
            "round": rec.engine.state.round,
            "version": rec.engine.state.current_version,
            "history": len(rec.engine.state.seen_action_ids),
        }
        print("错误码：", error, "| 详情：", str(body.get("detail"))[:120])
        print("失败前状态：", before, "失败后状态：", after)
        if after != before:
            print("[失败] 请求失败却污染了谈判状态")
            return 3
        if error == "MODEL_UNAVAILABLE":
            print("[结论] 模型不可用，本轮未写入任何状态，客户端可原样重试。")
            return 2
        print(f"[结论] 行动被拒绝（{error}），状态未变；需排查模型输出或规则。")
        return 3

    body = response.json()
    history = body.get("action_history") or []
    message = history[-1].get("public_message") if history else ""
    text = json.dumps(body, ensure_ascii=False)
    hits = [name for name in CLAUSES if name in text]
    summary = {
        "status": response.status_code,
        "elapsed_s": elapsed,
        "round": body.get("round"),
        "version": body.get("version"),
        "history": len(history),
        "clause_hits": hits,
        "leak_cn_hidden": CN_HIDDEN in text,
        "message_len": len(message or ""),
    }
    print("对手发言：", (message or "")[:300])
    print("SUMMARY", json.dumps(summary, ensure_ascii=False))
    if summary["leak_cn_hidden"]:
        print("[失败] 响应里出现了我方隐藏任务")
        return 3
    if not hits:
        print("[警告] 对手发言未提及任何条款，需人工复核")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

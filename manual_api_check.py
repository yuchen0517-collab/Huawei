import json
import sys
from datetime import datetime
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8765"
LOG_DIR = Path(__file__).resolve().parent / "logs"
RECORDS = []

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


def call(step, method, path, body=None, raw=None, headers=None):
    url = BASE + path
    if raw is not None:
        resp = requests.request(method, url, data=raw, headers=headers, timeout=60)
        sent = raw
    else:
        resp = requests.request(method, url, json=body, headers=headers, timeout=60)
        sent = body
    try:
        data = resp.json()
    except ValueError:
        data = resp.text
    RECORDS.append({
        "step": step,
        "method": method,
        "url": url,
        "request_body": sent,
        "status_code": resp.status_code,
        "response": data,
        "cors_headers": {
            k: v for k, v in resp.headers.items()
            if k.lower().startswith("access-control")
        },
    })
    print(f"\n===== [{step}] {method} {path} -> {resp.status_code} =====")
    if sent is not None:
        print("请求体:", json.dumps(sent, ensure_ascii=False) if not isinstance(sent, str) else sent)
    print(json.dumps(data, ensure_ascii=False, indent=2) if not isinstance(data, str) else data)
    return resp, data


def expect(condition, message):
    if not condition:
        print(f"\n[FAIL] {message}")
        save()
        sys.exit(1)
    print(f"[OK] {message}")


def save():
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"api_http_acceptance_{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(RECORDS, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n验收记录已保存: {path}")


def main():
    resp, data = call(1, "GET", "/")
    expect(resp.status_code == 200 and data == {"status": "ok"}, "健康检查返回精确对象")

    resp, data = call(2, "POST", "/session", body={"scenario_id": "ai_governance", "agent": "us"})
    expect(resp.status_code == 200, "开局成功")
    sid = data["session_id"]
    expect(data["round"] == 1 and data["action_history"] == [], "引擎初始轮次为 1 且历史为空")
    expect(data["my_offer"] == {"version": 0, "offers": {}}, "我方初始报价为空")
    expect(data["mode"] == "offline", "离线模式标注 mode=offline")

    resp, action_state = call(3, "POST", f"/session/{sid}/action", body=VALID_OFFER)
    expect(resp.status_code == 200, "合法行动被接受")
    expect(action_state["round"] == data["round"] + 1, "双方行动后轮次由引擎推进一次")
    expect(len(action_state["action_history"]) == 2, "历史新增两条")
    expect(action_state["my_offer"]["version"] == data["my_offer"]["version"] + 1, "我方报价版本 +1")
    expect(action_state["opponent_offer"]["version"] == 2, "对手报价版本取引擎结果")

    resp, data = call(4, "GET", f"/session/{sid}/state")
    expect(resp.status_code == 200 and data == action_state, "行动后 GET 状态与行动响应一致")

    illegal = {
        "action_type": "offer",
        "offer_patch": {"不存在的条款": {"option": "强行带报价", "note": "非法"}},
        "conditions": [],
        "expected_effect": "",
        "public_message": "我方尝试提交未知条款。",
    }
    resp, data = call(5, "POST", f"/session/{sid}/action", body=illegal)
    expect(resp.status_code == 400 and data.get("error") == "UNKNOWN_CLAUSE", "引擎非法行动返回 400 UNKNOWN_CLAUSE")
    expect(set(data) == {"error", "detail"}, "错误响应只有 error/detail 两字段")

    resp, data = call(6, "GET", f"/session/{sid}/state")
    expect(data == action_state, "引擎拒绝后九字段状态零变更")

    resp, auto_state = call(7, "POST", f"/session/{sid}/auto_step")
    expect(resp.status_code == 200, "auto_step 成功")
    expect(auto_state["round"] == action_state["round"] + 1, "auto_step 恰好推进一轮")
    expect(len(auto_state["action_history"]) == 4, "auto_step 历史再增两条")
    expect(auto_state["action_history"][-2]["origin"] == "auto_player", "自动我方行动 origin=auto_player")

    resp, data = call(8, "POST", f"/session/{sid}/debrief")
    expect(resp.status_code == 202 and data == {"status": "accepted"}, "debrief 返回 202 accepted 占位")

    resp, data = call(9, "GET", f"/session/{sid}/state")
    expect(data == auto_state, "debrief 后状态不变")

    resp, _ = call(10, "OPTIONS", "/session", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    expect(resp.status_code == 200, "CORS 预检成功")
    expect(resp.headers.get("access-control-allow-origin") == "*", "CORS 允许跨域来源")

    resp, data = call(11, "GET", "/session/no-such-id/state")
    expect(resp.status_code == 404 and data.get("error") == "SESSION_NOT_FOUND", "未知会话 404")
    resp, data = call(12, "POST", "/session", body={"scenario_id": "default", "agent": "us"})
    expect(resp.status_code == 400 and data.get("error") == "INVALID_SCENARIO", "非法场景 400")
    resp, data = call(13, "POST", "/session", body={"scenario_id": "ai_governance", "agent": "xx"})
    expect(resp.status_code == 400 and data.get("error") == "INVALID_AGENT", "非法国家 400")
    resp, data = call(14, "GET", "/no_such_path")
    expect(resp.status_code == 404 and data.get("error") == "NOT_FOUND", "未知路由 404")
    resp, data = call(15, "GET", "/session")
    expect(resp.status_code == 405 and data.get("error") == "METHOD_NOT_ALLOWED", "错误方法 405")
    resp, data = call(16, "POST", f"/session/{sid}/action", raw="{bad json",
                      headers={"Content-Type": "application/json"})
    expect(resp.status_code == 400 and data.get("error") == "INVALID_JSON", "畸形 JSON 400")
    resp, data = call(17, "POST", "/session", body={"agent": "us"})
    expect(resp.status_code == 422 and data.get("error") == "INVALID_REQUEST", "缺字段 422")

    save()
    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
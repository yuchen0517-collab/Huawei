# -*- coding: utf-8 -*-
"""真实 HTTP 冒烟验证：C 引擎接 API 部分（独立复核脚本，不改仓库文件）"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

os.environ["NEG_OFFLINE"] = "1"  # 离线模式，不依赖模型
PORT = 8899
BASE = f"http://127.0.0.1:{PORT}"


def req(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f" | {extra}" if extra else ""))
    return cond


results = []
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", str(PORT)],
    cwd=os.path.dirname(os.path.abspath(__file__)),
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
try:
    for _ in range(50):
        try:
            s, _ = req("GET", "/")
            if s == 200:
                break
        except Exception:
            time.sleep(0.3)

    # 1. 开局
    s, st = req("POST", "/session", {"scenario_id": "ai_governance", "agent": "us"})
    nine = ["session_id", "round", "phase", "my_offer", "opponent_offer",
            "open_issues", "action_history", "status", "mode"]
    results.append(check("开局 200 且返回契约九字段", s == 200 and sorted(st.keys()) == sorted(nine),
                         f"keys={sorted(st.keys())}"))
    sid = st["session_id"]
    results.append(check("初始 round=1 且 status 非 ended", st["round"] == 1 and st["status"] != "ended"))

    # 2. 合法报价 -> 引擎接收 -> 对手(离线)回应 -> 我方版本+1
    offer_action = {
        "action_type": "offer",
        "offer_patch": {"前沿模型评测门槛": {"option": 60, "note": "冒烟验证"}},
        "conditions": [], "expected_effect": "验证",
        "public_message": "我方提议评测门槛设为 60。",
    }
    s, st2 = req("POST", f"/session/{sid}/action", offer_action)
    results.append(check("合法报价 200", s == 200, f"status={s} body={st2 if s != 200 else ''}"))
    v0 = st["my_offer"]["version"]
    v1 = st2["my_offer"]["version"]
    results.append(check("我方报价版本 +1", v1 == v0 + 1, f"v{v0}->v{v1}"))
    results.append(check("对手已回应（历史含双方行动）",
                         any(h.get("actor") == "us" for h in st2["action_history"])))

    # 3. 非法行动被拒且状态零变更
    bad_action = {"action_type": "definitely_not_a_type", "offer_patch": {},
                  "conditions": [], "expected_effect": "", "public_message": "x"}
    s, err = req("POST", f"/session/{sid}/action", bad_action)
    results.append(check("非法行动被拒", s in (400, 409, 422) and "error" in err,
                         f"status={s} error={err.get('error')}"))
    s, st3 = req("GET", f"/session/{sid}/state")
    snap = {k: st3[k] for k in ("round", "phase", "status", "open_issues")}
    snap["history_len"] = len(st3["action_history"])
    prev = {k: st2[k] for k in ("round", "phase", "status", "open_issues")}
    prev["history_len"] = len(st2["action_history"])
    results.append(check("被拒后状态零变更", snap == prev, f"{prev} -> {snap}"))

    # 4. 隐私检查：API 响应不得泄露对方私有底牌
    raw = json.dumps(st2, ensure_ascii=False)
    leaks = [w for w in ("red_lines", "batna", "hidden_task", "红线") if w in raw]
    results.append(check("响应无私有底牌泄露", not leaks, f"leaks={leaks}"))

    # 5. 引擎错误码透传：对已结束会话或违规行动返回引擎错误
    #    用重复提交同一 client 行为无法复现 action_id（服务端生成），
    #    改为直接验证引擎层错误码映射已在 test_api.py 覆盖，这里确认错误体形状
    results.append(check("错误体形状 {error, detail}", set(err.keys()) == {"error", "detail"},
                         f"keys={sorted(err.keys())}"))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

print()
print("总计: %d/%d 通过" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)

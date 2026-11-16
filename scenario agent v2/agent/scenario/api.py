"""场景服务接口：编译、读取、自检。

双模式设计
----------
1. **FastAPI 模式**（给 A 集成用）
       from agent.scenario.api import create_router
       app.include_router(create_router())

2. **标准库模式**（今晚就能跑，零依赖）
       py.bat -m agent.scenario.api --port 8000
   浏览器打开 http://127.0.0.1:8000/api/scenarios 就能看到列表。

三条铁律（手册 2.3 / 11.1）
--------------------------
· 场景一律从 data/scenarios 落盘读取，**不存在每次请求重新生成**
· private_state 按调用者身份过滤，**服务端裁剪，不靠前端隐藏**
· 错误统一返回 {code, message, detail}，不返回半成品
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from agent.scenario.compiler import (
    ScenarioCompileError,
    compile_from_narrowing,
    compile_scenario,
)
from agent.scenario.models import Scenario, validate_scenario
from agent.scenario.zopa import evaluate_deal, scenario_feasibility, suggest_deal

BASE_DIR = Path(__file__).resolve().parents[2]
SCENARIO_DIR = BASE_DIR / "data" / "scenarios"
PUBLIC_FIELDS = (
    "scenario_id", "title", "scenario_type", "background", "assumptions",
    "parties", "issues", "public_facts", "max_rounds", "terminal_rules",
    "negotiability",
)

__all__ = ["create_router", "public_view", "list_scenarios", "load_scenario", "main"]


# ---------------------------------------------------------------------------
# 读盘
# ---------------------------------------------------------------------------
def list_scenarios() -> list[dict[str, Any]]:
    """扫描 data/scenarios/*.json，返回摘要列表（不含 private_state）。"""
    items = []
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append({
            "scenario_id": data.get("scenario_id"),
            "title": data.get("title"),
            "scenario_type": data.get("scenario_type"),
            "issue_count": len(data.get("issues") or []),
            "file": path.name,
        })
    return items


def load_scenario(scenario_id: str) -> dict[str, Any] | None:
    """按 scenario_id 找到并读出完整场景；找不到返回 None。"""
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("scenario_id") == scenario_id:
            return data
    return None


# ---------------------------------------------------------------------------
# 私有状态裁剪
# ---------------------------------------------------------------------------
def resolve_side(data: Mapping[str, Any], side: str | None) -> str | None:
    """把 cn/us 映射成场景里的真实 party_id。

    场景的 party_id 可能是 P1/P2、也可能是 cn/us。与 load_scenario.py 的
    alias 规则保持一致：按 parties 列表顺序，第一个是 cn，第二个是 us。
    """
    if not side:
        return None
    private = data.get("private_state_by_party") or {}
    if side in private:
        return side
    parties = [party.get("party_id") for party in data.get("parties") or []]
    slot = {"cn": 0, "us": 1}.get(side)
    if slot is not None and slot < len(parties):
        candidate = parties[slot]
        if candidate in private:
            return candidate
    return None


def public_view(data: Mapping[str, Any], side: str | None) -> dict[str, Any]:
    """只返回 caller 自己那一方的 private_state，对方只给公开估算字段。

    side 为 None 或无法匹配时，两侧 private_state 都不返回（只给公开部分）。
    """
    view = {key: data.get(key) for key in PUBLIC_FIELDS if key in data}
    private = data.get("private_state_by_party") or {}
    resolved = resolve_side(data, side)
    if resolved is not None:
        state = private[resolved]
        view["private_state_by_party"] = {
            resolved: {
                "goals": state.get("goals", []),
                "redlines": state.get("redlines", []),
                "batna": state.get("batna"),
                "hidden_task": state.get("hidden_task", ""),
                "priority_ranking": state.get("priority_ranking", []),
            }
        }
    else:
        view["private_state_by_party"] = {}
    view["viewer_side"] = side
    view["viewer_party_id"] = resolved
    return view


def _visible_to(data: Mapping[str, Any], side: str | None) -> dict[str, Any]:
    """编译结果也要裁：D 直接拿去渲染，不能带对方底牌。"""
    if isinstance(data, dict) and "private_state_by_party" in data:
        return public_view(data, side)
    return data


# ---------------------------------------------------------------------------
# 业务处理（FastAPI 与标准库共用同一套）
# ---------------------------------------------------------------------------
def handle_list() -> dict[str, Any]:
    return {"scenarios": list_scenarios()}


def handle_get(scenario_id: str, side: str | None) -> tuple[int, dict[str, Any]]:
    data = load_scenario(scenario_id)
    if data is None:
        return 404, {"code": "SCENARIO_NOT_FOUND", "message": f"没有这个场景：{scenario_id}", "detail": None}
    return 200, public_view(data, side)


def handle_check(scenario_id: str) -> tuple[int, dict[str, Any]]:
    data = load_scenario(scenario_id)
    if data is None:
        return 404, {"code": "SCENARIO_NOT_FOUND", "message": f"没有这个场景：{scenario_id}", "detail": None}
    problems = validate_scenario(data)
    feasibility = scenario_feasibility(data)
    deal = suggest_deal(data)
    evaluation = evaluate_deal(data, deal) if deal else None
    return 200, {
        "ok": not problems,
        "scenario_id": scenario_id,
        "problems": [problem.to_dict() for problem in problems],
        "feasibility": {
            "zopa_exists": feasibility["zopa_exists"],
            "infeasible_issues": feasibility["infeasible_issues"],
            "per_issue": {
                issue_id: {
                    "feasible": item["feasible"],
                    "suggested": item["suggested"],
                    "detail": item["detail"],
                }
                for issue_id, item in feasibility["per_issue"].items()
            },
        },
        "suggested_deal": deal,
        "evaluation": evaluation,
    }


def handle_compile(body: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    topic = (body.get("topic") or "").strip()
    if not topic:
        return 400, {"code": "INVALID_TOPIC", "message": "topic 不能为空", "detail": None}

    mode = body.get("mode") or "auto"
    side = body.get("side")
    narrowing = (body.get("narrowing") or "").strip()

    try:
        if narrowing:
            result = compile_from_narrowing(topic, narrowing, mode=mode)
        else:
            result = compile_scenario(topic, mode=mode)
    except ScenarioCompileError as exc:
        # 缺 key / 接口异常 → 503，前端据此提示「改用固定场景」
        status = 503 if exc.stage == "llm" else 422
        return status, {
            "code": "COMPILE_FAILED",
            "message": str(exc),
            "detail": exc.to_dict(),
        }

    if result.scenario is None:
        # 规则层拦下：200 + negotiability，前端据 suggestions 渲染可点选方向
        return 200, {
            "ok": False,
            "scenario": None,
            "negotiability": result.negotiability,
            "narrowing_required": result.negotiability.get("verdict") == "needs_narrowing",
        }

    payload = _visible_to(result.scenario.to_dict(), side)
    return 200, {
        "ok": True,
        "attempts": result.attempts,
        "scenario": payload,
        "negotiability": result.negotiability,
        "narrowing_required": False,
    }


# ---------------------------------------------------------------------------
# 模式一：FastAPI 路由
# ---------------------------------------------------------------------------
def create_router():
    """挂到 A 的 app 上：app.include_router(create_router())。"""
    from fastapi import APIRouter, Body, Query  # 延迟导入，标准库模式下不依赖

    router = APIRouter(prefix="/api", tags=["scenario"])

    @router.get("/scenarios")
    def _list():
        return handle_list()

    @router.get("/scenario/{scenario_id}")
    def _get(scenario_id: str, side: str | None = Query(default=None)):
        status, payload = handle_get(scenario_id, side)
        return payload

    @router.post("/scenario/{scenario_id}/check")
    def _check(scenario_id: str):
        status, payload = handle_check(scenario_id)
        return payload

    @router.post("/scenario/compile")
    def _compile(body: dict = Body(...)):
        status, payload = handle_compile(body)
        return payload

    return router


# ---------------------------------------------------------------------------
# 模式二：标准库 HTTP 服务（零依赖，今晚就能跑）
# ---------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    server_version = "ScenarioAPI/1.0"

    def _send(self, status: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _route(self, method: str, body: Mapping[str, Any] | None = None) -> None:
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        query = parse_qs(parsed.query)
        side = (query.get("side") or [None])[0]

        if method == "GET" and parts == ["api", "scenarios"]:
            return self._send(200, handle_list())
        if method == "GET" and len(parts) == 3 and parts[:2] == ["api", "scenario"]:
            status, payload = handle_get(parts[2], side)
            return self._send(status, payload)
        if method == "POST" and len(parts) == 4 and parts[3] == "check":
            status, payload = handle_check(parts[2])
            return self._send(status, payload)
        if method == "POST" and parts == ["api", "scenario", "compile"]:
            status, payload = handle_compile(body or {})
            return self._send(status, payload)

        self._send(404, {"code": "NOT_FOUND", "message": f"没有这个接口：{self.path}", "detail": None})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802
        self._route("GET")

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._send(400, {"code": "INVALID_JSON", "message": "请求体不是合法 JSON", "detail": None})
        self._route("POST", body if isinstance(body, dict) else {})

    def log_message(self, fmt: str, *args) -> None:  # 静音默认日志
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="场景服务（标准库模式）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    print(f"场景服务已启动：http://{args.host}:{args.port}")
    print("  GET  /api/scenarios                       场景列表")
    print("  GET  /api/scenario/<id>?side=cn           读场景（按身份裁剪）")
    print("  POST /api/scenario/<id>/check             自检 + 可行性")
    print("  POST /api/scenario/compile  {\"topic\":...} 编译议题")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

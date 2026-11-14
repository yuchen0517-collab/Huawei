from __future__ import annotations

import copy
import json
import os
import re
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import neg_cli as neg
from fastapi import Body, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

BASE_DIR = Path(__file__).resolve().parent

# B→C 场景转换的唯一实现在成员C 的 load_scenario_bridge（委托 adapter/），
# 位于引擎目录内，需先把该目录加入 sys.path。
ENGINE_DIR = BASE_DIR / "C 11.12 三指数"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from load_scenario_bridge import ENGINE_ROOT, load_scenario, make_scenario

from engine.core import RulesEngine
from engine.state import NegotiationState, Offer
from engine.validator import ERRORS as ENGINE_ERRORS

SCENARIO_ID = "ai_governance"
MY_ACTOR = "cn"
IDENTITY_FIELDS = ("action_id", "actor", "card_id")
TRANSPORT_FIELDS = ("client_action_id", "base_version")
ACTION_FIELDS = ("action_type", "offer_patch", "conditions", "expected_effect")
OPTIONAL_ACTION_FIELDS = ("effect_labels",)


def pick_action_fields(source: dict) -> dict:
    """提取行动字段：必填字段必取，可选字段（effect_labels）有才带。"""
    picked = {k: source[k] for k in ACTION_FIELDS}
    for key in OPTIONAL_ACTION_FIELDS:
        if source.get(key) is not None:
            picked[key] = source[key]
    return picked
PUBLIC_STATE_KEYS = (
    "session_id", "round", "phase", "my_offer", "opponent_offer",
    "open_issues", "action_history", "status", "mode",
)

ACTION_SCHEMA = json.loads(
    (BASE_DIR / "action_schema.json").read_text(encoding="utf-8-sig")
)["schema"]
SCHEMA_VALIDATOR = Draft202012Validator(ACTION_SCHEMA)

PROMPT_MD = neg.load_prompt_markdown()
AGENTS = neg.load_agents()
SCENARIO = AGENTS.get("_scenario", {})

SYSTEM_PROMPTS = {
    key: neg.build_system_prompt(
        PROMPT_MD, cfg, SCENARIO, side=key if key in ("us", "cn") else None
    )
    for key, cfg in AGENTS.items()
    if not key.startswith("_")
}

MODEL_ERROR_DETAIL = "AI 对手暂时不可用或返回内容不合规，本轮未推进，请稍后重试。"


class ApiError(Exception):
    def __init__(self, status_code: int, error: str, detail: str, extra: dict | None = None):
        super().__init__(detail)
        self.status_code = status_code
        self.error = error
        self.detail = detail
        self.extra = extra


class ModelUnavailable(ApiError):
    def __init__(self, detail: str = MODEL_ERROR_DETAIL):
        super().__init__(503, "MODEL_UNAVAILABLE", detail)


@dataclass(frozen=True)
class RuntimeMetadata:
    messages: tuple
    offline_cursor: int
    action_seq: int
    action_meta: tuple = field(default_factory=tuple)


@dataclass
class SessionRecord:
    session_id: str
    scenario_id: str
    my_actor: str
    opponent_actor: str
    mode: str
    system_prompt: str
    initial_indexes: dict
    model_options: SimpleNamespace
    mutation_lock: threading.Lock
    state_lock: threading.Lock
    engine: RulesEngine
    runtime: RuntimeMetadata
    idempotency_ledger: dict = field(default_factory=dict)


SESSIONS: dict[str, SessionRecord] = {}
SESSIONS_LOCK = threading.Lock()


def detect_mode() -> str:
    if os.environ.get("NEG_OFFLINE", "").strip() == "1":
        return "offline"
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return "offline"
    return "online"


def get_session(session_id: str) -> SessionRecord:
    with SESSIONS_LOCK:
        rec = SESSIONS.get(session_id)
    if rec is None:
        raise ApiError(404, "SESSION_NOT_FOUND", "会话不存在或服务已重启，请重新开局。")
    return rec


def make_action_id(seq: int) -> str:
    return f"a{seq:06d}"


def restore_engine(engine: RulesEngine) -> RulesEngine:
    archive = copy.deepcopy(engine.state.to_archive_dict())
    restored = copy.deepcopy(archive)
    restored["offers"] = [Offer(**offer) for offer in restored["offers"]]
    restored["agreement"] = Offer(**restored["agreement"]) if restored["agreement"] else None
    candidate = RulesEngine(copy.deepcopy(engine.scenario), engine.session_id)
    candidate.state = NegotiationState(**restored)
    if candidate.state.to_archive_dict() != archive:
        raise ApiError(500, "INTERNAL_ERROR", "规则引擎快照恢复失败，本轮未推进。")
    return candidate


def latest_offer(public: dict, actor: str) -> dict:
    offers = [offer for offer in public["offers"] if offer.get("actor") == actor]
    if not offers:
        return {"version": 0, "offers": {}}
    latest = max(offers, key=lambda offer: offer["version"])
    return {"version": latest["version"], "offers": copy.deepcopy(latest["clauses"])}


def project_engine_state(rec: SessionRecord, engine: RulesEngine, runtime: RuntimeMetadata) -> dict:
    public = engine.public_state(MY_ACTOR)
    action_meta = {action_id: (origin, warnings) for action_id, origin, warnings in runtime.action_meta}
    history = []
    for event in public["public_events"]:
        if event.get("type") != "action":
            continue
        record = copy.deepcopy(event)
        default_origin = "human" if record.get("actor") == MY_ACTOR else "opponent_ai"
        origin, warnings = action_meta.get(record.get("action_id"), (default_origin, ()))
        record["origin"] = origin
        record["warnings"] = list(warnings)
        history.append(record)
    return {
        "session_id": rec.session_id,
        "round": public["round"],
        "phase": public["phase"],
        "my_offer": latest_offer(public, rec.my_actor),
        "opponent_offer": latest_offer(public, rec.opponent_actor),
        "open_issues": copy.deepcopy(public["open_issues"]),
        "action_history": history,
        "status": public["status"],
        "mode": rec.mode,
    }


def project_state(rec: SessionRecord) -> dict:
    with rec.state_lock:
        return project_engine_state(rec, rec.engine, rec.runtime)


def create_session(req: "CreateSessionRequest") -> dict:
    try:
        scenario = load_scenario(req.scenario_path)
    except (OSError, ValueError) as exc:
        raise ApiError(400, "INVALID_SCENARIO", f"场景文件加载失败：{exc}")
    scenario_id = scenario.get("scenario_id", SCENARIO_ID)
    if req.scenario_id != scenario_id:
        raise ApiError(
            400, "INVALID_SCENARIO",
            f"scenario_id 应为 {scenario_id!r}，收到 {req.scenario_id!r}。",
        )
    agent = req.agent
    if agent != "us" or agent not in AGENTS or not isinstance(AGENTS.get(agent), dict):
        raise ApiError(400, "INVALID_AGENT", f"临时场景仅支持对手国家代码 'us'，收到 {agent!r}。")
    cfg = AGENTS[agent]
    indexes = {k: int(cfg[f"initial_{k}"]) for k in neg.INDEX_KEYS}
    prompt = SYSTEM_PROMPTS[agent]
    with SESSIONS_LOCK:
        session_id = str(uuid.uuid4())
        while session_id in SESSIONS:
            session_id = str(uuid.uuid4())
        engine = RulesEngine(scenario, session_id)
        runtime = RuntimeMetadata(
            messages=({"role": "system", "content": prompt},),
            offline_cursor=0,
            action_seq=0,
        )
        rec = SessionRecord(
            session_id=session_id,
            scenario_id=scenario_id,
            my_actor=MY_ACTOR,
            opponent_actor=agent,
            mode=detect_mode(),
            system_prompt=prompt,
            initial_indexes=indexes,
            model_options=SimpleNamespace(no_json_mode=False, temperature=0.7),
            mutation_lock=threading.Lock(),
            state_lock=threading.Lock(),
            engine=engine,
            runtime=runtime,
        )
        initial_state = project_engine_state(rec, engine, runtime)
        json.dumps(initial_state, ensure_ascii=False)
        SESSIONS[session_id] = rec
    return initial_state


def schema_detail(err) -> str:
    path = ".".join(str(p) for p in err.absolute_path)
    where = f"字段 {path}" if path else "行动对象"
    validator = err.validator
    if validator == "required":
        match = re.search(r"'([^']+)'", err.message)
        return f"{where}缺少必填字段 {match.group(1) if match else ''}。"
    if validator == "additionalProperties":
        match = re.search(r"'([^']+)'", err.message)
        return f"{where}存在不允许的额外字段 {match.group(1) if match else ''}。"
    if validator == "enum":
        return f"{where}取值 {err.instance!r} 不在允许范围内。"
    if validator == "type":
        return f"{where}类型不正确，应为 {err.validator_value}。"
    if validator == "maxProperties":
        return "非报价类行动的 offer_patch 必须为空对象 {}。"
    if validator == "minLength":
        return f"{where}不能为空。"
    return f"{where}不符合要求：{err.message}"


def check_flat_schema(flat: dict, opponent: bool = False) -> None:
    err = next(SCHEMA_VALIDATOR.iter_errors(flat), None)
    if err is not None:
        if opponent:
            raise ModelUnavailable()
        raise ApiError(400, "INVALID_ACTION", schema_detail(err))


def run_validate_action(wrapped: dict, opponent: bool = False) -> list:
    try:
        _, warns = neg.validate_action(wrapped)
    except ValueError as e:
        if opponent:
            raise ModelUnavailable()
        raise ApiError(400, "INVALID_ACTION", str(e))
    return list(warns)


def extract_transport_fields(payload: Any) -> tuple[dict, str, int]:
    if not isinstance(payload, dict):
        raise ApiError(422, "INVALID_REQUEST", "请求体顶层必须是 JSON 对象。")
    client_action_id = payload.get("client_action_id")
    if client_action_id is None or (isinstance(client_action_id, str) and not client_action_id.strip()):
        raise ApiError(422, "INVALID_REQUEST", "缺少必填字段 client_action_id。")
    if not isinstance(client_action_id, str):
        raise ApiError(422, "INVALID_REQUEST", "字段 client_action_id 必须是非空字符串。")
    if "base_version" not in payload:
        raise ApiError(422, "INVALID_REQUEST", "缺少必填字段 base_version。")
    base_version = payload["base_version"]
    if isinstance(base_version, bool) or not isinstance(base_version, int) or base_version < 0:
        raise ApiError(422, "INVALID_REQUEST", "字段 base_version 必须是大于等于 0 的整数。")
    action_payload = {k: v for k, v in payload.items() if k not in TRANSPORT_FIELDS}
    return action_payload, client_action_id, base_version


def adapt_client_action(payload: Any, rec: SessionRecord, action_id: str) -> tuple[dict, list]:
    if not isinstance(payload, dict):
        raise ApiError(422, "INVALID_REQUEST", "请求体顶层必须是 JSON 对象。")
    flat = {k: v for k, v in payload.items() if k not in IDENTITY_FIELDS}
    flat["action_id"] = action_id
    flat["actor"] = rec.my_actor
    flat["card_id"] = None
    check_flat_schema(flat)
    wrapped = {
        "action": pick_action_fields(flat),
        "public_message": flat["public_message"],
    }
    warns = run_validate_action(wrapped)
    flat["public_message"] = flat["public_message"].strip()
    return flat, warns


def build_auto_action(rec: SessionRecord, next_round: int, action_id: str) -> tuple[dict, list]:
    text = neg.CHINA_LINES[(next_round - 1) % len(neg.CHINA_LINES)].replace("\n", " ")
    flat = {
        "action_id": action_id,
        "actor": rec.my_actor,
        "card_id": None,
        "action_type": "statement",
        "offer_patch": {},
        "conditions": [],
        "expected_effect": "",
        "public_message": text,
    }
    check_flat_schema(flat, opponent=True)
    wrapped = {
        "action": pick_action_fields(flat),
        "public_message": flat["public_message"],
    }
    warns = run_validate_action(wrapped, opponent=True)
    return flat, warns


def generate_opponent_turn(rec: SessionRecord, candidate_messages: list, runtime: RuntimeMetadata) -> dict:
    if rec.mode == "offline":
        return neg.OFFLINE_RESPONSES[runtime.offline_cursor % len(neg.OFFLINE_RESPONSES)]
    try:
        obj, _, _ = neg.call_with_retry(
            list(candidate_messages), rec.system_prompt, rec.model_options
        )
    except SystemExit:
        raise ModelUnavailable()
    except Exception:
        raise ModelUnavailable()
    if obj is None:
        raise ModelUnavailable()
    return obj


def normalize_opponent_turn(raw_obj: Any, rec: SessionRecord, action_id: str) -> tuple[dict, list, dict]:
    if not isinstance(raw_obj, dict):
        raise ModelUnavailable()
    obj = copy.deepcopy(raw_obj)
    action = obj.get("action")
    if not isinstance(action, dict):
        raise ModelUnavailable()
    action["action_id"] = action_id
    action["actor"] = rec.opponent_actor
    action["card_id"] = None
    action.setdefault("conditions", [])
    action.setdefault("expected_effect", "")
    flat = {k: action.get(k) for k in IDENTITY_FIELDS + ACTION_FIELDS}
    if action.get("effect_labels") is not None:
        flat["effect_labels"] = action["effect_labels"]
    flat["public_message"] = obj.get("public_message")
    check_flat_schema(flat, opponent=True)
    try:
        checked, warns = neg.validate_action(obj)
    except ValueError:
        raise ModelUnavailable()
    checked_action = checked["action"]
    opp_flat = {
        "action_id": checked_action["action_id"],
        "actor": checked_action["actor"],
        "card_id": checked_action["card_id"],
        "action_type": checked_action["action_type"],
        "offer_patch": checked_action["offer_patch"],
        "conditions": checked_action["conditions"],
        "expected_effect": checked_action["expected_effect"],
        "public_message": checked["public_message"].strip(),
    }
    if checked_action.get("effect_labels") is not None:
        opp_flat["effect_labels"] = checked_action["effect_labels"]
    return opp_flat, list(warns), checked


def submit_engine_action(engine: RulesEngine, flat: dict) -> list:
    ok, code, _, events = engine.submit_action(copy.deepcopy(flat))
    if ok:
        return events
    error = code or "INTERNAL_ERROR"
    status_code = 409 if code in {
        "VERSION_CONFLICT", "DUPLICATE_ACTION", "PHASE_CLOSED",
    } else 400
    if code is None:
        status_code = 500
    detail = ENGINE_ERRORS.get(error, "规则引擎拒绝了该行动，本轮未推进。")
    raise ApiError(status_code, error, detail)


def run_turn(rec: SessionRecord, payload: Any = None, auto: bool = False) -> dict:
    action_payload = payload
    client_action_id = None
    base_version = None
    if not auto:
        action_payload, client_action_id, base_version = extract_transport_fields(payload)
    if not rec.mutation_lock.acquire(blocking=False):
        raise ApiError(409, "SESSION_BUSY", "本会话有另一轮正在处理，请稍后重试；本次未推进。")
    try:
        if not auto:
            cached = rec.idempotency_ledger.get(client_action_id)
            if cached is not None:
                return copy.deepcopy(cached)
        with rec.state_lock:
            engine = rec.engine
            runtime = rec.runtime
        candidate = restore_engine(engine)
        if not auto and base_version != candidate.state.current_version:
            raise ApiError(
                409, "VERSION_CONFLICT",
                "客户端基线版本与服务端当前版本不一致，请按 current_state 刷新后重试，本轮未推进。",
                extra={"current_state": project_engine_state(rec, candidate, runtime)},
            )
        current_round = candidate.public_state(MY_ACTOR)["round"]
        my_id = make_action_id(runtime.action_seq + 1)
        opp_id = make_action_id(runtime.action_seq + 2)
        if auto:
            my_flat, my_warns = build_auto_action(rec, current_round, my_id)
            origin = "auto_player"
        else:
            my_flat, my_warns = adapt_client_action(action_payload, rec, my_id)
            origin = "human"
        user_msg = neg.build_user_message(
            current_round, rec.initial_indexes, my_flat["public_message"]
        )
        candidate_messages = list(runtime.messages) + [{"role": "user", "content": user_msg}]
        submit_engine_action(candidate, my_flat)
        candidate_meta = runtime.action_meta + ((my_id, origin, tuple(my_warns)),)
        candidate_seq = runtime.action_seq + 1
        candidate_cursor = runtime.offline_cursor
        if candidate.public_state(MY_ACTOR)["status"] != "ended":
            raw_opp = generate_opponent_turn(rec, candidate_messages, runtime)
            opp_flat, opp_warns, opp_checked = normalize_opponent_turn(raw_opp, rec, opp_id)
            submit_engine_action(candidate, opp_flat)
            assistant_obj = {k: v for k, v in opp_checked.items() if not k.startswith("_")}
            candidate_messages.append(
                {"role": "assistant", "content": json.dumps(assistant_obj, ensure_ascii=False)}
            )
            candidate_meta += ((opp_id, "opponent_ai", tuple(opp_warns)),)
            candidate_seq += 1
            candidate_cursor += 1 if rec.mode == "offline" else 0
        candidate_public = candidate.public_state(MY_ACTOR)
        if candidate_public["status"] != "ended" and candidate_public["round"] == current_round:
            candidate.next_round()
        new_runtime = RuntimeMetadata(
            messages=tuple(candidate_messages),
            offline_cursor=candidate_cursor,
            action_seq=candidate_seq,
            action_meta=candidate_meta,
        )
        state = project_engine_state(rec, candidate, new_runtime)
        json.dumps(state, ensure_ascii=False)
        with rec.state_lock:
            rec.engine = candidate
            rec.runtime = new_runtime
        if not auto:
            rec.idempotency_ledger[client_action_id] = copy.deepcopy(state)
        return state
    finally:
        rec.mutation_lock.release()


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str
    agent: str
    scenario_path: str | None = None


app = FastAPI(title="谈判 HTTP API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    content = {"error": exc.error, "detail": exc.detail}
    if exc.extra:
        content.update(exc.extra)
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    for err in errors:
        if err.get("type") == "json_invalid":
            return JSONResponse(
                status_code=400,
                content={"error": "INVALID_JSON", "detail": "请求体不是合法 JSON。"},
            )
    parts = []
    for err in errors[:3]:
        loc = ".".join(str(x) for x in err.get("loc", []) if x != "body") or "请求体"
        err_type = err.get("type", "")
        if err_type == "missing":
            parts.append(f"缺少字段 {loc}")
        elif err_type == "extra_forbidden":
            parts.append(f"存在不允许的额外字段 {loc}")
        elif err_type == "string_type":
            parts.append(f"字段 {loc} 必须是字符串")
        else:
            parts.append(f"字段 {loc} 不合法（{err.get('msg', '')}）")
    detail = "；".join(parts) if parts else "请求参数校验失败"
    return JSONResponse(
        status_code=422,
        content={"error": "INVALID_REQUEST", "detail": detail + "。"},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={"error": "NOT_FOUND", "detail": "请求的路径不存在。"},
        )
    if exc.status_code == 405:
        return JSONResponse(
            status_code=405,
            content={"error": "METHOD_NOT_ALLOWED", "detail": "该路径不支持此 HTTP 方法。"},
            headers=getattr(exc, "headers", None),
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "HTTP_ERROR", "detail": str(exc.detail)},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "detail": "服务内部错误，请稍后重试。"},
    )


@app.get("/")
def health() -> dict:
    return {"status": "ok"}


@app.post("/session")
def create_session_endpoint(req: CreateSessionRequest) -> dict:
    return create_session(req)


@app.get("/session/{session_id}/state")
def state_endpoint(session_id: str) -> dict:
    return project_state(get_session(session_id))


@app.post("/session/{session_id}/action")
async def action_endpoint(session_id: str, request: Request) -> dict:
    rec = get_session(session_id)
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise ApiError(400, "INVALID_JSON", "请求体不是合法 JSON。")
    return await run_in_threadpool(run_turn, rec, payload, False)


@app.post("/session/{session_id}/auto_step")
def auto_step_endpoint(session_id: str) -> dict:
    return run_turn(get_session(session_id), auto=True)


@app.post("/session/{session_id}/debrief", status_code=202)
def debrief_endpoint(session_id: str) -> dict:
    get_session(session_id)
    return {"status": "accepted"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
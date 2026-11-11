from __future__ import annotations

import copy
import json
import os
import re
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
SCENARIO_ID = "ai_governance"
MY_ACTOR = "cn"
IDENTITY_FIELDS = ("action_id", "actor", "card_id")
ACTION_FIELDS = ("action_type", "offer_patch", "conditions", "expected_effect")
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
AGENDA = tuple(SCENARIO.get("agenda") or [])
SYSTEM_PROMPTS = {
    key: neg.build_system_prompt(
        PROMPT_MD, cfg, SCENARIO, side=key if key in ("us", "cn") else None
    )
    for key, cfg in AGENTS.items()
    if not key.startswith("_")
}

MODEL_ERROR_DETAIL = "AI 对手暂时不可用或返回内容不合规，本轮未推进，请稍后重试。"


class ApiError(Exception):
    def __init__(self, status_code: int, error: str, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.error = error
        self.detail = detail


class ModelUnavailable(ApiError):
    def __init__(self, detail: str = MODEL_ERROR_DETAIL):
        super().__init__(503, "MODEL_UNAVAILABLE", detail)


@dataclass(frozen=True)
class OfferSide:
    version: int = 0
    offers: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TurnSnapshot:
    round: int
    status: str
    my_offer: OfferSide
    opponent_offer: OfferSide
    open_issues: tuple
    action_history: tuple
    messages: tuple
    offline_cursor: int
    action_seq: int


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
    snapshot: TurnSnapshot


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


def phase_of(round_no: int) -> str:
    if round_no <= 3:
        return "opening"
    if round_no <= 8:
        return "bargaining"
    return "closing"


def make_action_id(seq: int) -> str:
    return f"a{seq:06d}"


def project_snapshot(rec: SessionRecord, snap: TurnSnapshot) -> dict:
    return {
        "session_id": rec.session_id,
        "round": snap.round,
        "phase": phase_of(snap.round),
        "my_offer": {
            "version": snap.my_offer.version,
            "offers": copy.deepcopy(snap.my_offer.offers),
        },
        "opponent_offer": {
            "version": snap.opponent_offer.version,
            "offers": copy.deepcopy(snap.opponent_offer.offers),
        },
        "open_issues": list(snap.open_issues),
        "action_history": copy.deepcopy(list(snap.action_history)),
        "status": snap.status,
        "mode": rec.mode,
    }


def project_state(rec: SessionRecord) -> dict:
    with rec.state_lock:
        snap = rec.snapshot
    return project_snapshot(rec, snap)


def create_session(req: "CreateSessionRequest") -> dict:
    if req.scenario_id != SCENARIO_ID:
        raise ApiError(400, "INVALID_SCENARIO", "scenario_id 仅支持 ai_governance。")
    agent = req.agent
    if agent.startswith("_") or agent not in AGENTS or not isinstance(AGENTS.get(agent), dict):
        valid = "、".join(k for k in AGENTS if not k.startswith("_"))
        raise ApiError(400, "INVALID_AGENT", f"未知对手国家代码 {agent!r}，可选：{valid}。")
    cfg = AGENTS[agent]
    indexes = {k: int(cfg[f"initial_{k}"]) for k in neg.INDEX_KEYS}
    prompt = SYSTEM_PROMPTS[agent]
    snapshot = TurnSnapshot(
        round=0,
        status="active",
        my_offer=OfferSide(),
        opponent_offer=OfferSide(),
        open_issues=AGENDA,
        action_history=(),
        messages=({"role": "system", "content": prompt},),
        offline_cursor=0,
        action_seq=0,
    )
    with SESSIONS_LOCK:
        session_id = str(uuid.uuid4())
        while session_id in SESSIONS:
            session_id = str(uuid.uuid4())
        rec = SessionRecord(
            session_id=session_id,
            scenario_id=SCENARIO_ID,
            my_actor=MY_ACTOR,
            opponent_actor=agent,
            mode=detect_mode(),
            system_prompt=prompt,
            initial_indexes=indexes,
            model_options=SimpleNamespace(no_json_mode=False, temperature=0.7),
            mutation_lock=threading.Lock(),
            state_lock=threading.Lock(),
            snapshot=snapshot,
        )
        SESSIONS[session_id] = rec
    return project_state(rec)


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


def adapt_client_action(payload: Any, rec: SessionRecord, action_id: str) -> tuple[dict, list]:
    if not isinstance(payload, dict):
        raise ApiError(422, "INVALID_REQUEST", "请求体顶层必须是 JSON 对象。")
    flat = {k: v for k, v in payload.items() if k not in IDENTITY_FIELDS}
    flat["action_id"] = action_id
    flat["actor"] = rec.my_actor
    flat["card_id"] = None
    check_flat_schema(flat)
    wrapped = {
        "action": {k: flat[k] for k in ACTION_FIELDS},
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
        "action": {k: flat[k] for k in ACTION_FIELDS},
        "public_message": flat["public_message"],
    }
    warns = run_validate_action(wrapped, opponent=True)
    return flat, warns


def generate_opponent_turn(rec: SessionRecord, candidate_messages: list, snap: TurnSnapshot) -> dict:
    if rec.mode == "offline":
        return neg.OFFLINE_RESPONSES[snap.offline_cursor % len(neg.OFFLINE_RESPONSES)]
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
    return opp_flat, list(warns), checked


def make_history_record(round_no: int, origin: str, flat: dict, warns: list) -> dict:
    return {
        "round": round_no,
        "actor": flat["actor"],
        "origin": origin,
        "action_id": flat["action_id"],
        "card_id": flat["card_id"],
        "action_type": flat["action_type"],
        "offer_patch": copy.deepcopy(flat["offer_patch"]),
        "conditions": list(flat["conditions"]),
        "expected_effect": flat["expected_effect"],
        "public_message": flat["public_message"],
        "warnings": list(warns),
    }


def apply_offer(side: OfferSide, flat: dict, round_no: int) -> OfferSide:
    patch = flat["offer_patch"]
    if not patch:
        return side
    offers = copy.deepcopy(side.offers)
    for topic, item in patch.items():
        offers[topic] = {
            "option": item["option"],
            "note": item["note"],
            "round": round_no,
            "action_id": flat["action_id"],
        }
    return OfferSide(version=side.version + 1, offers=offers)


def run_turn(rec: SessionRecord, payload: Any = None, auto: bool = False) -> dict:
    if not rec.mutation_lock.acquire(blocking=False):
        raise ApiError(409, "SESSION_BUSY", "本会话有另一轮正在处理，请稍后重试；本次未推进。")
    try:
        with rec.state_lock:
            snap = rec.snapshot
        next_round = snap.round + 1
        my_id = make_action_id(snap.action_seq + 1)
        opp_id = make_action_id(snap.action_seq + 2)
        if auto:
            my_flat, my_warns = build_auto_action(rec, next_round, my_id)
            origin = "auto_player"
        else:
            my_flat, my_warns = adapt_client_action(payload, rec, my_id)
            origin = "human"
        user_msg = neg.build_user_message(
            next_round, rec.initial_indexes, my_flat["public_message"]
        )
        candidate_messages = list(snap.messages) + [{"role": "user", "content": user_msg}]
        raw_opp = generate_opponent_turn(rec, candidate_messages, snap)
        opp_flat, opp_warns, opp_checked = normalize_opponent_turn(raw_opp, rec, opp_id)
        my_record = make_history_record(next_round, origin, my_flat, my_warns)
        opp_record = make_history_record(next_round, "opponent_ai", opp_flat, opp_warns)
        assistant_obj = {k: v for k, v in opp_checked.items() if not k.startswith("_")}
        new_snap = TurnSnapshot(
            round=next_round,
            status=snap.status,
            my_offer=apply_offer(snap.my_offer, my_flat, next_round),
            opponent_offer=apply_offer(snap.opponent_offer, opp_flat, next_round),
            open_issues=snap.open_issues,
            action_history=snap.action_history + (my_record, opp_record),
            messages=tuple(candidate_messages) + (
                {"role": "assistant", "content": json.dumps(assistant_obj, ensure_ascii=False)},
            ),
            offline_cursor=snap.offline_cursor + (1 if rec.mode == "offline" else 0),
            action_seq=snap.action_seq + 2,
        )
        state = project_snapshot(rec, new_snap)
        json.dumps(state, ensure_ascii=False)
        with rec.state_lock:
            rec.snapshot = new_snap
        return state
    finally:
        rec.mutation_lock.release()


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str
    agent: str


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
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error, "detail": exc.detail},
    )


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
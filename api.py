from __future__ import annotations

import copy
import dataclasses
import json
import math
import os
import re
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import neg_cli as neg
import session_store
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

from load_scenario_bridge import (
    ENGINE_ROOT,
    debrief_for,
    evaluate_for,
    load_scenario,
    make_scenario,
    submit_for,
)

from engine.core import IllegalDebriefAccess, RulesEngine
from engine.state import NegotiationState, Offer
from engine.terminal import TERMINAL_TYPES
from engine.validator import ERRORS as ENGINE_ERRORS
from engine.validator import validate_action as validate_engine_action

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
INTERNAL_ERROR_DETAIL = "服务内部错误，请稍后重试。"
SESSION_RECORD_ERROR_DETAIL = "会话记录无法恢复，自动推演已停止。"
AUTO_RECORD_INVALID_DETAIL = "自动推演会话记录不一致，已禁止自动推进。"
AUTO_INTERRUPTED_DETAIL = "上次自动推演在完成前中断，已恢复到最后已提交状态。"
AUTO_PAUSED_PERSISTENCE_DETAIL = "会话持久化失败，本轮未推进，可重试自动推演。"
AUTO_ERROR_PERSISTENCE_DETAIL = "会话持久化结果无法确认，已禁止自动推进。"
AUTO_STATUS_ERROR_DETAIL = "自动推演记录不可安全恢复，已禁止自动推进。"
PHASE_CLOSED_DETAIL = "谈判已结束，不能继续自动推进。"
AUTO_FIELDS = ("auto_status", "auto_terminal_type", "auto_last_error")
AutoStatus = Literal["running", "paused", "done", "error"]


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
class AutoError:
    code: str
    detail: str


class AutoErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    detail: str


class AutoStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    status: AutoStatus
    current_round: int
    terminal_type: str | None
    last_error: AutoErrorResponse | None


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
    auto_status: AutoStatus = "paused"
    auto_terminal_type: str | None = None
    auto_last_error: AutoError | None = None


SESSIONS: dict[str, SessionRecord] = {}
SESSIONS_LOCK = threading.Lock()


def detect_mode() -> str:
    if os.environ.get("NEG_OFFLINE", "").strip() == "1":
        return "offline"
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return "offline"
    return "online"


def get_session_store() -> session_store.SessionStore:
    configured = os.environ.get("NEG_SESSION_STORE_DIR", "").strip()
    root = Path(configured) if configured else BASE_DIR / "runtime" / "sessions"
    return session_store.SessionStore(root)


def internal_api_error() -> ApiError:
    return ApiError(500, "INTERNAL_ERROR", INTERNAL_ERROR_DETAIL)


def get_session(session_id: str) -> SessionRecord:
    with SESSIONS_LOCK:
        rec = SESSIONS.get(session_id)
    if rec is not None:
        return rec
    with SESSIONS_LOCK:
        rec = SESSIONS.get(session_id)
        if rec is not None:
            return rec
        try:
            document = get_session_store().read(session_id)
        except (session_store.SessionStoreNotFound, session_store.InvalidSessionId):
            raise ApiError(404, "SESSION_NOT_FOUND", "会话不存在或服务已重启，请重新开局。")
        except session_store.SessionStoreError:
            raise internal_api_error()
        rec = decode_session_document(document)
        if rec.session_id != session_id:
            raise internal_api_error()
        if (
            document.get("auto_status") == "running"
            and rec.auto_status == "paused"
            and rec.auto_last_error is not None
            and rec.auto_last_error.code == "AUTO_INTERRUPTED"
        ):
            try:
                persist_session(
                    rec,
                    rec.engine,
                    rec.runtime,
                    rec.idempotency_ledger,
                    "paused",
                    None,
                    rec.auto_last_error,
                )
            except Exception:
                raise internal_api_error()
        SESSIONS[session_id] = rec
        return rec


def make_action_id(seq: int) -> str:
    return f"a{seq:06d}"


def restore_engine_from_archive(scenario: dict, session_id: str, archive: dict) -> RulesEngine:
    try:
        if not isinstance(scenario, dict) or not isinstance(archive, dict):
            raise ValueError()
        original = copy.deepcopy(archive)
        restored = copy.deepcopy(original)
        # to_archive_dict() 会带 `_visibility="god_view"` 等存档标记键，
        # 不是 NegotiationState 字段，重建前必须剔除（标记会在重新导出时再生成）。
        state_fields = {f.name for f in dataclasses.fields(NegotiationState)}
        restored = {k: v for k, v in restored.items() if k in state_fields}
        restored["offers"] = [Offer(**offer) for offer in restored["offers"]]
        restored["agreement"] = Offer(**restored["agreement"]) if restored["agreement"] else None
        candidate = RulesEngine(copy.deepcopy(scenario), session_id)
        candidate.state = NegotiationState(**restored)
        if candidate.state.to_archive_dict() != original:
            raise ValueError()
        if candidate.state.session_id != session_id:
            raise ValueError()
        if candidate.state.scenario_id != scenario.get("scenario_id"):
            raise ValueError()
        if (
            isinstance(candidate.state.round, bool)
            or not isinstance(candidate.state.round, int)
            or candidate.state.round < 1
        ):
            raise ValueError()
        return candidate
    except Exception:
        raise ApiError(500, "INTERNAL_ERROR", "规则引擎快照恢复失败，本轮未推进。")


def restore_engine(engine: RulesEngine) -> RulesEngine:
    return restore_engine_from_archive(
        engine.scenario,
        engine.session_id,
        engine.state.to_archive_dict(),
    )


def engine_record_facts(engine: RulesEngine) -> tuple[str, str | None, bool]:
    state = engine.state
    if state.status == "active" and state.phase != "ended" and state.terminal is None:
        return "active", None, True
    if state.status == "ended" and state.phase == "ended" and isinstance(state.terminal, dict):
        terminal_type = state.terminal.get("type")
        if isinstance(terminal_type, str) and terminal_type in TERMINAL_TYPES:
            return "ended", terminal_type, True
    return "invalid", None, False


def auto_error_dict(error: AutoError | dict | None) -> dict | None:
    if error is None:
        return None
    if isinstance(error, AutoError):
        code, detail = error.code, error.detail
    elif isinstance(error, dict) and set(error) == {"code", "detail"}:
        code, detail = error.get("code"), error.get("detail")
    else:
        raise ValueError()
    if not isinstance(code, str) or re.fullmatch(r"[A-Z][A-Z0-9_]*", code) is None:
        raise ValueError()
    if not isinstance(detail, str) or not detail.strip():
        raise ValueError()
    return {"code": code, "detail": detail}


def invalid_auto_error() -> AutoError:
    return AutoError("AUTO_RECORD_INVALID", AUTO_RECORD_INVALID_DETAIL)


def normalize_auto_fields(document: dict, engine: RulesEngine) -> tuple[AutoStatus, str | None, AutoError | None]:
    fact_status, fact_terminal, facts_valid = engine_record_facts(engine)
    if not facts_valid:
        return "error", None, invalid_auto_error()
    if not any(key in document for key in AUTO_FIELDS):
        if fact_status == "ended":
            return "done", fact_terminal, None
        return "paused", None, None
    try:
        status = document["auto_status"]
        terminal_type = document["auto_terminal_type"]
        error_data = auto_error_dict(document["auto_last_error"])
        error = AutoError(**error_data) if error_data is not None else None
        if status not in ("running", "paused", "done", "error"):
            raise ValueError()
        if terminal_type is not None and (
            not isinstance(terminal_type, str) or terminal_type not in TERMINAL_TYPES
        ):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        return "error", fact_terminal, invalid_auto_error()
    if status == "error":
        if error is None:
            return "error", fact_terminal, invalid_auto_error()
        if fact_status == "active" and terminal_type is None:
            return "error", None, error
        if fact_status == "ended" and terminal_type in (None, fact_terminal):
            return "error", fact_terminal, error
        return "error", fact_terminal, invalid_auto_error()
    if fact_status == "ended":
        if status == "done" and terminal_type == fact_terminal and error is None:
            return "done", fact_terminal, None
        return "error", fact_terminal, invalid_auto_error()
    if status == "paused" and terminal_type is None:
        return "paused", None, error
    if status == "running" and terminal_type is None and error is None:
        return "paused", None, AutoError("AUTO_INTERRUPTED", AUTO_INTERRUPTED_DETAIL)
    return "error", None, invalid_auto_error()


def validate_auto_combination(
    engine: RulesEngine,
    status: str,
    terminal_type: str | None,
    error: AutoError | dict | None,
) -> dict | None:
    error_data = auto_error_dict(error)
    fact_status, fact_terminal, facts_valid = engine_record_facts(engine)
    if not facts_valid:
        raise ValueError()
    if status == "done":
        valid = fact_status == "ended" and terminal_type == fact_terminal and error_data is None
    elif status == "paused":
        valid = fact_status == "active" and terminal_type is None
    elif status == "running":
        valid = fact_status == "active" and terminal_type is None and error_data is None
    elif status == "error":
        valid = error_data is not None and (
            (fact_status == "active" and terminal_type is None)
            or (fact_status == "ended" and terminal_type == fact_terminal)
        )
    else:
        valid = False
    if not valid:
        raise ValueError()
    return error_data


def validate_idempotency_ledger(ledger: dict, session_id: str, mode: str) -> dict:
    if not isinstance(ledger, dict):
        raise ValueError()
    validated = {}
    for client_action_id, state in ledger.items():
        if not isinstance(client_action_id, str) or not client_action_id:
            raise ValueError()
        if not isinstance(state, dict) or set(state) != set(PUBLIC_STATE_KEYS):
            raise ValueError()
        if state.get("session_id") != session_id or state.get("mode") != mode:
            raise ValueError()
        validated[client_action_id] = copy.deepcopy(state)
    return validated


def encode_session_document(
    rec: SessionRecord,
    engine: RulesEngine,
    runtime: RuntimeMetadata,
    idempotency_ledger: dict,
    auto_status: AutoStatus,
    auto_terminal_type: str | None,
    auto_last_error: AutoError | dict | None,
) -> dict:
    try:
        error_data = validate_auto_combination(
            engine,
            auto_status,
            auto_terminal_type,
            auto_last_error,
        )
        ledger = validate_idempotency_ledger(idempotency_ledger, rec.session_id, rec.mode)
        return {
            "schema_version": 1,
            "session_id": rec.session_id,
            "scenario_id": rec.scenario_id,
            "my_actor": rec.my_actor,
            "opponent_actor": rec.opponent_actor,
            "mode": rec.mode,
            "system_prompt": rec.system_prompt,
            "initial_indexes": copy.deepcopy(rec.initial_indexes),
            "model_options": {
                "no_json_mode": rec.model_options.no_json_mode,
                "temperature": rec.model_options.temperature,
            },
            "scenario": copy.deepcopy(engine.scenario),
            "engine_state": engine.state.to_archive_dict(),
            "runtime": {
                "messages": copy.deepcopy(list(runtime.messages)),
                "offline_cursor": runtime.offline_cursor,
                "action_seq": runtime.action_seq,
                "action_meta": [
                    [action_id, origin, list(warnings)]
                    for action_id, origin, warnings in runtime.action_meta
                ],
            },
            "idempotency_ledger": ledger,
            "auto_status": auto_status,
            "auto_terminal_type": auto_terminal_type,
            "auto_last_error": error_data,
        }
    except (AttributeError, TypeError, ValueError):
        raise internal_api_error()


def decode_session_document(document: dict) -> SessionRecord:
    required = {
        "session_id",
        "scenario_id",
        "my_actor",
        "opponent_actor",
        "mode",
        "system_prompt",
        "initial_indexes",
        "model_options",
        "scenario",
        "engine_state",
        "runtime",
        "idempotency_ledger",
    }
    try:
        if not isinstance(document, dict) or not required.issubset(document):
            raise ValueError()
        if set(document) - required - set(AUTO_FIELDS) - {"schema_version"}:
            raise ValueError()
        if "schema_version" in document and (
            isinstance(document["schema_version"], bool) or document["schema_version"] != 1
        ):
            raise ValueError()
        session_id = document["session_id"]
        scenario_id = document["scenario_id"]
        my_actor = document["my_actor"]
        opponent_actor = document["opponent_actor"]
        mode = document["mode"]
        system_prompt = document["system_prompt"]
        if not all(isinstance(value, str) and value for value in (
            session_id, scenario_id, my_actor, opponent_actor
        )):
            raise ValueError()
        if my_actor == opponent_actor or mode not in ("offline", "online"):
            raise ValueError()
        if not isinstance(system_prompt, str):
            raise ValueError()
        initial_indexes = document["initial_indexes"]
        if not isinstance(initial_indexes, dict) or set(initial_indexes) != set(neg.INDEX_KEYS):
            raise ValueError()
        if any(isinstance(value, bool) or not isinstance(value, int) for value in initial_indexes.values()):
            raise ValueError()
        options = document["model_options"]
        if not isinstance(options, dict) or set(options) != {"no_json_mode", "temperature"}:
            raise ValueError()
        if not isinstance(options["no_json_mode"], bool):
            raise ValueError()
        temperature = options["temperature"]
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            raise ValueError()
        if not math.isfinite(float(temperature)):
            raise ValueError()
        scenario = document["scenario"]
        if not isinstance(scenario, dict) or scenario.get("scenario_id") != scenario_id:
            raise ValueError()
        parties = scenario.get("parties")
        if not isinstance(parties, list):
            raise ValueError()
        party_ids = {party.get("id") for party in parties if isinstance(party, dict)}
        if my_actor not in party_ids or opponent_actor not in party_ids:
            raise ValueError()
        runtime_data = document["runtime"]
        if not isinstance(runtime_data, dict) or set(runtime_data) != {
            "messages", "offline_cursor", "action_seq", "action_meta"
        }:
            raise ValueError()
        messages = runtime_data["messages"]
        if not isinstance(messages, list):
            raise ValueError()
        for message in messages:
            if not isinstance(message, dict) or set(message) != {"role", "content"}:
                raise ValueError()
            if message["role"] not in ("system", "user", "assistant"):
                raise ValueError()
            if not isinstance(message["content"], str):
                raise ValueError()
        offline_cursor = runtime_data["offline_cursor"]
        action_seq = runtime_data["action_seq"]
        for value in (offline_cursor, action_seq):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError()
        action_meta = []
        for item in runtime_data["action_meta"]:
            if not isinstance(item, list) or len(item) != 3:
                raise ValueError()
            action_id, origin, warnings = item
            if not all(isinstance(value, str) and value for value in (action_id, origin)):
                raise ValueError()
            if not isinstance(warnings, list) or any(not isinstance(value, str) for value in warnings):
                raise ValueError()
            action_meta.append((action_id, origin, tuple(warnings)))
        runtime = RuntimeMetadata(
            messages=tuple(copy.deepcopy(messages)),
            offline_cursor=offline_cursor,
            action_seq=action_seq,
            action_meta=tuple(action_meta),
        )
        engine = restore_engine_from_archive(scenario, session_id, document["engine_state"])
        if engine.state.scenario_id != scenario_id:
            raise ValueError()
        ledger = validate_idempotency_ledger(document["idempotency_ledger"], session_id, mode)
        rec = SessionRecord(
            session_id=session_id,
            scenario_id=scenario_id,
            my_actor=my_actor,
            opponent_actor=opponent_actor,
            mode=mode,
            system_prompt=system_prompt,
            initial_indexes=copy.deepcopy(initial_indexes),
            model_options=SimpleNamespace(
                no_json_mode=options["no_json_mode"],
                temperature=float(temperature),
            ),
            mutation_lock=threading.Lock(),
            state_lock=threading.Lock(),
            engine=engine,
            runtime=runtime,
            idempotency_ledger=ledger,
        )
        status, terminal_type, error = normalize_auto_fields(document, engine)
        rec.auto_status = status
        rec.auto_terminal_type = terminal_type
        rec.auto_last_error = error
        return rec
    except ApiError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ApiError(500, "INTERNAL_ERROR", SESSION_RECORD_ERROR_DETAIL)


def persist_session(
    rec: SessionRecord,
    engine: RulesEngine,
    runtime: RuntimeMetadata,
    idempotency_ledger: dict,
    auto_status: AutoStatus,
    auto_terminal_type: str | None,
    auto_last_error: AutoError | dict | None,
) -> dict:
    document = encode_session_document(
        rec,
        engine,
        runtime,
        idempotency_ledger,
        auto_status,
        auto_terminal_type,
        auto_last_error,
    )
    get_session_store().write(document)
    return document


def project_auto_status(rec: SessionRecord) -> AutoStatusResponse:
    with rec.state_lock:
        fact_status, fact_terminal, facts_valid = engine_record_facts(rec.engine)
        status = rec.auto_status
        terminal_type = rec.auto_terminal_type
        error = rec.auto_last_error
        if not facts_valid:
            status, terminal_type, error = "error", None, invalid_auto_error()
        elif fact_status == "ended" and status != "error":
            if status == "done" and terminal_type == fact_terminal and error is None:
                terminal_type = fact_terminal
            else:
                status, terminal_type, error = "error", fact_terminal, invalid_auto_error()
        elif fact_status == "active" and status != "error":
            if status == "done" or terminal_type is not None:
                status, terminal_type, error = "error", None, invalid_auto_error()
            elif status == "running" and error is not None:
                status, terminal_type, error = "error", None, invalid_auto_error()
        error_data = auto_error_dict(error)
        return AutoStatusResponse(
            session_id=rec.session_id,
            status=status,
            current_round=rec.engine.state.round,
            terminal_type=terminal_type,
            last_error=AutoErrorResponse(**error_data) if error_data is not None else None,
        )


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
            auto_status="paused",
            auto_terminal_type=None,
            auto_last_error=None,
        )
        initial_state = project_engine_state(rec, engine, runtime)
        json.dumps(initial_state, ensure_ascii=False)
        try:
            persist_session(
                rec,
                engine,
                runtime,
                rec.idempotency_ledger,
                "paused",
                None,
                None,
            )
        except Exception:
            raise internal_api_error()
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


def build_auto_action(rec: SessionRecord, engine: RulesEngine, action_id: str) -> tuple[dict, list]:
    accepting = not engine.state.open_issues
    if accepting:
        text = "我方接受当前协议，确认达成完全一致。"
        action_type = "accept"
    else:
        text = neg.CHINA_LINES[(engine.state.round - 1) % len(neg.CHINA_LINES)].replace("\n", " ")
        action_type = "statement"
    flat = {
        "action_id": action_id,
        "actor": rec.my_actor,
        "card_id": None,
        "action_type": action_type,
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
    if accepting:
        ok, code, _ = validate_engine_action(
            copy.deepcopy(flat),
            engine.state,
            engine.scenario,
        )
        if not ok:
            raise engine_action_error(code)
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


def engine_action_error(code: str | None) -> ApiError:
    error = code or "INTERNAL_ERROR"
    status_code = 409 if code in {
        "VERSION_CONFLICT", "DUPLICATE_ACTION", "PHASE_CLOSED",
    } else 400
    if code is None:
        status_code = 500
    detail = ENGINE_ERRORS.get(error, "规则引擎拒绝了该行动，本轮未推进。")
    return ApiError(status_code, error, detail)


def submit_engine_action(engine: RulesEngine, flat: dict) -> list:
    # 身份收口走 C 侧 submit_for（强制 actor=viewer，丢弃客户端自带 actor），
    # 与 adapt_client_action 的 flat["actor"] = rec.my_actor 同一口径。
    ok, code, _, events = submit_for(engine, flat["actor"], copy.deepcopy(flat))
    if ok:
        return events
    raise engine_action_error(code)


def set_auto_fields(
    rec: SessionRecord,
    status: AutoStatus,
    terminal_type: str | None,
    error: AutoError | None,
) -> None:
    with rec.state_lock:
        rec.auto_status = status
        rec.auto_terminal_type = terminal_type
        rec.auto_last_error = error


def mark_auto_persistence_error(rec: SessionRecord) -> None:
    fact_status, fact_terminal, facts_valid = engine_record_facts(rec.engine)
    terminal_type = fact_terminal if facts_valid and fact_status == "ended" else None
    set_auto_fields(
        rec,
        "error",
        terminal_type,
        AutoError("AUTO_PERSISTENCE_FAILED", AUTO_ERROR_PERSISTENCE_DETAIL),
    )


def pause_auto_or_error(
    rec: SessionRecord,
    engine: RulesEngine,
    runtime: RuntimeMetadata,
    ledger: dict,
    error: AutoError,
) -> None:
    try:
        persist_session(rec, engine, runtime, ledger, "paused", None, error)
    except Exception:
        mark_auto_persistence_error(rec)
        raise internal_api_error()
    set_auto_fields(rec, "paused", None, error)


def fail_auto_system(
    rec: SessionRecord,
    engine: RulesEngine,
    runtime: RuntimeMetadata,
    ledger: dict,
) -> None:
    error = invalid_auto_error()
    try:
        persist_session(rec, engine, runtime, ledger, "error", None, error)
    except Exception:
        mark_auto_persistence_error(rec)
    else:
        set_auto_fields(rec, "error", None, error)
    raise internal_api_error()


def check_auto_gate(rec: SessionRecord, engine: RulesEngine) -> None:
    fact_status, fact_terminal, facts_valid = engine_record_facts(engine)
    if rec.auto_status == "error":
        raise ApiError(409, "AUTO_STATUS_ERROR", AUTO_STATUS_ERROR_DETAIL)
    if facts_valid and fact_status == "ended":
        if (
            rec.auto_status == "done"
            and rec.auto_terminal_type == fact_terminal
            and rec.auto_last_error is None
        ):
            raise ApiError(
                409,
                "PHASE_CLOSED",
                PHASE_CLOSED_DETAIL,
                extra={
                    "auto_status": "done",
                    "current_round": engine.state.round,
                    "terminal_type": fact_terminal,
                },
            )
        set_auto_fields(rec, "error", fact_terminal, invalid_auto_error())
        raise ApiError(409, "AUTO_STATUS_ERROR", AUTO_STATUS_ERROR_DETAIL)
    if not facts_valid or rec.auto_status == "done":
        set_auto_fields(rec, "error", None, invalid_auto_error())
        raise ApiError(409, "AUTO_STATUS_ERROR", AUTO_STATUS_ERROR_DETAIL)
    if rec.auto_status != "paused":
        set_auto_fields(rec, "error", None, invalid_auto_error())
        raise ApiError(409, "AUTO_STATUS_ERROR", AUTO_STATUS_ERROR_DETAIL)


def is_ordinary_auto_error(exc: ApiError) -> bool:
    return exc.status_code < 500 or exc.error == "MODEL_UNAVAILABLE"


def run_turn(rec: SessionRecord, payload: Any = None, auto: bool = False) -> dict:
    action_payload = payload
    client_action_id = None
    base_version = None
    if not auto:
        action_payload, client_action_id, base_version = extract_transport_fields(payload)
    if not rec.mutation_lock.acquire(blocking=False):
        raise ApiError(409, "SESSION_BUSY", "本会话有另一轮正在处理，请稍后重试；本次未推进。")
    auto_started = False
    business_active = False
    try:
        if not auto:
            cached = rec.idempotency_ledger.get(client_action_id)
            if cached is not None:
                return copy.deepcopy(cached)
        with rec.state_lock:
            engine = rec.engine
            runtime = rec.runtime
            ledger = copy.deepcopy(rec.idempotency_ledger)
        if auto:
            check_auto_gate(rec, engine)
            try:
                persist_session(
                    rec,
                    engine,
                    runtime,
                    ledger,
                    "running",
                    None,
                    None,
                )
            except session_store.SessionStoreCommitUnknown:
                mark_auto_persistence_error(rec)
                raise internal_api_error()
            except Exception:
                pause_auto_or_error(
                    rec,
                    engine,
                    runtime,
                    ledger,
                    AutoError("AUTO_PERSISTENCE_FAILED", AUTO_PAUSED_PERSISTENCE_DETAIL),
                )
                raise internal_api_error()
            auto_started = True
            set_auto_fields(rec, "running", None, None)
            business_active = True
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
            my_flat, my_warns = build_auto_action(rec, candidate, my_id)
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
        fact_status, fact_terminal, facts_valid = engine_record_facts(candidate)
        if not facts_valid:
            raise ApiError(500, "INTERNAL_ERROR", SESSION_RECORD_ERROR_DETAIL)
        if fact_status == "ended":
            final_auto_status = "done"
            final_terminal_type = fact_terminal
            final_auto_error = None
        elif auto:
            final_auto_status = "paused"
            final_terminal_type = None
            final_auto_error = None
        else:
            final_auto_status = rec.auto_status
            final_terminal_type = rec.auto_terminal_type
            final_auto_error = rec.auto_last_error
        state = project_engine_state(rec, candidate, new_runtime)
        json.dumps(state, ensure_ascii=False)
        new_ledger = copy.deepcopy(ledger)
        if not auto:
            new_ledger[client_action_id] = copy.deepcopy(state)
        business_active = False
        try:
            persist_session(
                rec,
                candidate,
                new_runtime,
                new_ledger,
                final_auto_status,
                final_terminal_type,
                final_auto_error,
            )
        except session_store.SessionStoreCommitUnknown:
            mark_auto_persistence_error(rec)
            raise internal_api_error()
        except Exception:
            if auto:
                pause_auto_or_error(
                    rec,
                    engine,
                    runtime,
                    ledger,
                    AutoError("AUTO_PERSISTENCE_FAILED", AUTO_PAUSED_PERSISTENCE_DETAIL),
                )
            raise internal_api_error()
        with rec.state_lock:
            rec.engine = candidate
            rec.runtime = new_runtime
            rec.idempotency_ledger = new_ledger
            rec.auto_status = final_auto_status
            rec.auto_terminal_type = final_terminal_type
            rec.auto_last_error = final_auto_error
        return state
    except ApiError as exc:
        if auto and business_active:
            business_active = False
            if is_ordinary_auto_error(exc):
                pause_auto_or_error(
                    rec,
                    engine,
                    runtime,
                    ledger,
                    AutoError(exc.error, exc.detail),
                )
                raise
            fail_auto_system(rec, engine, runtime, ledger)
        raise
    except Exception:
        if auto and business_active:
            business_active = False
            pause_auto_or_error(
                rec,
                engine,
                runtime,
                ledger,
                AutoError("INTERNAL_ERROR", INTERNAL_ERROR_DETAIL),
            )
            raise internal_api_error()
        if auto and auto_started:
            mark_auto_persistence_error(rec)
        raise internal_api_error()
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


@app.get("/session/{session_id}/auto_status")
def auto_status_endpoint(session_id: str) -> AutoStatusResponse:
    return project_auto_status(get_session(session_id))


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


@app.post("/session/{session_id}/debrief")
def debrief_endpoint(session_id: str) -> dict:
    rec = get_session(session_id)
    with rec.state_lock:
        engine = rec.engine
        try:
            debrief = debrief_for(engine, MY_ACTOR)
        except IllegalDebriefAccess as exc:
            raise ApiError(409, "DEBRIEF_NOT_AVAILABLE", str(exc))
        # 对外评价唯一出口：evaluate_for 会把他方 batna / net_gain /
        # better_than_batna 置 None，禁止直出 engine.evaluate()。
        evaluation = evaluate_for(engine, MY_ACTOR)
    result = {"debrief": debrief, "evaluation": evaluation}
    json.dumps(result, ensure_ascii=False)
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
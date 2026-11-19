#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import random
import os
import re
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "demo1.1"))

import server as legacy  # noqa: E402
from diplomacy import (  # noqa: E402
    DiplomacySettlement,
    accept_channel_draft,
    add_channel_message,
    channel_for,
    create_proposal,
    ensure_diplomacy,
    follow_through,
    open_backchannel,
    open_channel,
    proposal_for,
    public_diplomacy,
)
from diplomacy_agent import DiplomacyAgent  # noqa: E402
from view_diplomat import (  # noqa: E402
    build_view,
    report_for,
    risk_for,
    snapshot_stances,
    stamp_rounds,
)

SETTLEMENT = DiplomacySettlement()
HOST = os.environ.get("DEMO_HOST", "0.0.0.0")
PORT = int(os.environ.get("DEMO_DIPLOMAT_PORT", "8010"))
# 非正式沟通：NPC 主动发起的频率控制
NPC_BACKCHANNEL_RATE = float(os.environ.get("DEMO_NPC_BACKCHANNEL", "0.22"))
NPC_BACKCHANNEL_GAP = max(0, int(os.environ.get("DEMO_NPC_BACKCHANNEL_GAP", "5")))
NPC_BACKCHANNEL_MAX = max(1, int(os.environ.get("DEMO_NPC_BACKCHANNEL_MAX", "6")))
# 观战推演的长度控制
OBSERVE_MAX_TURNS = max(1, int(os.environ.get("DEMO_OBSERVE_TURNS", "18")))
OBSERVE_MIN_GAP = max(0.0, float(os.environ.get("DEMO_OBSERVE_GAP", "3")))
OBSERVE_CONVERGE = max(2, int(os.environ.get("DEMO_OBSERVE_CONVERGE", "3")))
# 多边：玩家每轮之后自动跟几位 NPC 回应
MULTI_AUTO_REPLIES = max(1, int(os.environ.get("DEMO_MULTI_REPLIES", "2")))
# 与 legacy 的卡牌目录保持一致，费用随目录走
CARD_COSTS = {card["id"]: int(card["cost"]) for card in legacy.all_strategy_cards({})}
ACTION_POINTS = 3


def new_state(scene=None) -> dict:
    st = legacy.initial_state(scene)
    ensure_diplomacy(st)
    st["diplomacy_agents"] = {}
    return st


def ensure_state(st: dict) -> dict:
    ensure_diplomacy(st)
    st.setdefault("diplomacy_agents", {})
    return st


def agent_for(st: dict, key: str) -> DiplomacyAgent:
    agents = st["diplomacy_agents"]
    if key not in agents:
        agents[key] = DiplomacyAgent(key, legacy.PARTY.get(key, key))
    return agents[key]


def state_payload(st: dict, perspective="player", party=None) -> dict:
    ensure_state(st)
    raw = legacy.public_state(st)
    raw.pop("diplomacy", None)
    raw.pop("diplomacy_agents", None)
    raw["diplomacy"] = public_diplomacy(st, perspective=perspective, party=party)
    raw["diplomacy_agents"] = {
        key: agent.public_info() for key, agent in st["diplomacy_agents"].items()
    }
    return raw


def model_caller(messages, prompt):
    return legacy.engine.call_with_retry(messages, prompt, legacy.SHIM)


def caller_if_online():
    key = legacy.current_key()
    if key:
        os.environ["DEEPSEEK_API_KEY"] = key
        return model_caller
    return None


def require_player_channel(st: dict, channel: dict) -> None:
    if st.get("mode") == "observe":
        raise ValueError("观战模式只能查看暗线，不能代替国家发送私下消息")
    if st.get("you_key") not in channel["participants"]:
        raise ValueError("你不在该沟通渠道中")


# ---------------------------------------------------------------- v2 契约层

def _v2_view(st: dict, payload: dict | None = None) -> dict:
    payload = payload or {}
    perspective = str(payload.get("perspective") or "player")
    party = payload.get("party") or payload.get("follow")
    return build_view(st, perspective=perspective, party=party)


def _compose_card_text(st: dict, card_ids: list[str]) -> str:
    hand = {str(card.get("id")): card for card in legacy.strategy_cards(st)}
    parts = [str(hand[cid].get("speech") or "") for cid in card_ids if cid in hand]
    return "\n".join(part for part in parts if part).strip()


def _session_scene(payload: dict) -> dict:
    rivals = payload.get("rivals")
    if not isinstance(rivals, list) or not rivals:
        rivals = [str(payload.get("rival") or "us")]
    mode = str(payload.get("mode") or "multi").strip().lower()
    mode = {"bilateral": "duel", "multilateral": "multi"}.get(mode, mode)
    topic_id = str(payload.get("topic_id") or payload.get("topicId") or "")
    topic = str(payload.get("topic") or "").strip()
    if not topic and topic_id:
        # 只给 topic_id 时必须把议题名补上，否则 scene_ctx 会回落到默认议题
        try:
            meta = legacy.engine.load_knowledge(topic_id).get("_meta") or {}
            topic = str(meta.get("name") or "").strip()
        except Exception:  # noqa: BLE001
            topic = ""
    if not topic:
        topic = topic_id
    return {
        "agent": str(payload.get("rival") or rivals[0]),
        "player": payload.get("player") or "cn",
        "rivals": [str(item) for item in rivals if str(item).strip()],
        "mode": mode,
        "topic": topic,
        "topic_id": topic_id,
    }


def new_v2_state(payload: dict) -> dict:
    st = new_state(_session_scene(payload))
    rounds = payload.get("rounds")
    if rounds not in (None, ""):
        try:
            st["max_rounds"] = max(1, min(30, int(rounds)))
        except (TypeError, ValueError):
            pass
    # 观战：推演长度（默认 18 轮，最多 27 轮）
    try:
        st["max_turns"] = max(1, min(27, int(payload.get("max_turns")
                                            or (18 if st.get("mode") == "observe" else 30))))
    except (TypeError, ValueError):
        st["max_turns"] = 18
    st["turn_count"] = 0
    st["finished"] = False
    st["_last_deltas"] = {"player": {}, "agent": {}}
    _seed_stances(st)
    snapshot_stances(st)
    return st


STANCE_SCORE = {"support": 72, "swing": 50, "oppose": 28}


def _seed_stances(st: dict) -> None:
    """开局立场：先看议题知识库的 _meta.stances，再看 agents.json 的通用立场。

    立场是「议题取向」：同一个国家在算力议题和海洋法议题上的立场本来就不同，
    所以议题级配置优先；没有配置的按摇摆处理。
    """
    data = ensure_diplomacy(st)
    meta = {}
    try:
        meta = legacy.engine.load_knowledge(str((st.get("scene") or {}).get("topic_id") or "")).get("_meta") or {}
    except Exception:  # noqa: BLE001
        meta = {}
    topic_stances = meta.get("stances") if isinstance(meta, dict) else {}
    if not isinstance(topic_stances, dict):
        topic_stances = {}

    for key, row in (data.get("issue_stances") or {}).items():
        cfg = legacy.AGENTS.get(key) or {}
        stance = topic_stances.get(key)
        if not isinstance(stance, dict):
            stance = cfg.get("stance") if isinstance(cfg.get("stance"), dict) else {}
        position = str(stance.get("position") or "").strip().lower()
        if position not in STANCE_SCORE:
            continue
        row["stance"] = position
        row["support_score"] = STANCE_SCORE[position]
        row["confidence"] = 0.5 if topic_stances.get(key) else 0.4
        row["updated_round"] = 0
        reason = str(stance.get("reason") or "").strip()
        conditions = stance.get("conditions") or []
        if reason:
            row["evidence"] = [{"round": 0, "type": "initial", "text": reason[:80],
                                "source": "topic" if topic_stances.get(key) else "config"}]
        if isinstance(conditions, list) and conditions:
            row["conditions"] = [str(item)[:40] for item in conditions][:2]


def _deal_row(st: dict, channel_id: str | None) -> dict | None:
    for deal in _v2_view(st).get("deals") or []:
        if deal.get("id") == channel_id:
            return deal
    return None


PLAYER_STANCE = {
    "offer": "support", "concede": "support",
    "demand": "oppose", "threat": "oppose", "batna": "oppose",
    "probe": "swing", "disclose": "swing", "procedure": "swing",
}
STANCE_ANCHOR = {"support": 72, "swing": 50, "oppose": 28}


def _card_actions(st: dict, card_ids: list[str]) -> list[str]:
    catalog = {card["id"]: card for card in legacy.all_strategy_cards(st)}
    return [str((catalog.get(cid) or {}).get("action") or "") for cid in card_ids]


def _record_player_claim(st: dict, card_ids: list[str], target: str | None, text: str) -> None:
    """引擎已在结算时算过玩家的宣称；这里只补「被识破」对目标关系的惩罚。"""
    message = next((m for m in reversed(st.get("messages") or [])
                    if m.get("role") == "player"), None)
    verdict = (message or {}).get("bluff") or {}
    if not verdict.get("exposed") or not target:
        return
    player = st.get("you_key")
    relations = ((st.get("diplomacy") or {}).get("relations") or {})
    if target in relations and player in relations[target]:
        row = relations[target][player]
        row["trust"] = max(0, min(100, float(row.get("trust", 50)) - 3))
        row.setdefault("evidence", []).append({
            "round": st.get("round"),
            "text": "识破" + legacy.PARTY.get(player, player) + "的虚张声势",
            "trust_delta": -3,
        })
        row["evidence"] = row["evidence"][-6:]


def _apply_player_stance(st: dict, card_ids: list[str], target: str | None) -> None:
    """玩家这一侧的立场由本轮打出的卡决定，并可选地指向某个对象。

    NPC 的立场由模型输出（neg_cli.normalize_diplomacy），玩家没有模型，
    所以用卡牌语义做等价映射，避免"我方永远摇摆"。
    """
    if not card_ids:
        return
    catalog = {card["id"]: card for card in legacy.all_strategy_cards(st)}
    actions = [str((catalog.get(cid) or {}).get("action") or "") for cid in card_ids]
    positions = [PLAYER_STANCE[action] for action in actions if action in PLAYER_STANCE]
    if not positions:
        return
    if "support" in positions:
        position = "support"
    elif "oppose" in positions:
        position = "oppose"
    else:
        position = "swing"

    data = ensure_diplomacy(st)
    player = st.get("you_key") or ""
    row = data["issue_stances"].setdefault(player, {
        "stance": "swing", "support_score": 50, "confidence": 0.25,
        "evidence": [], "updated_round": 0,
    })
    row["stance"] = position
    row["support_score"] = int(round(
        0.5 * float(row.get("support_score", 50)) + 0.5 * STANCE_ANCHOR[position]))
    row["confidence"] = min(1.0, float(row.get("confidence", 0.25)) + 0.1)
    row["updated_round"] = int(st.get("round") or 0)
    row.setdefault("evidence", []).append({
        "round": int(st.get("round") or 0),
        "type": "card_play",
        "text": "我方以「" + "、".join(_card_names(st, card_ids)) + "」表明"
                + {"support": "支持", "oppose": "反对", "swing": "摇摆"}.get(position, "摇摆")
                + "立场",
    })
    row["evidence"] = row["evidence"][-8:]

    if target and target in (st.get("party_indexes") or {}) and target != player:
        relation = data["relations"].setdefault(player, {}).setdefault(target, {
            "trust": 50, "hostility": 20, "confidence": 0.25, "evidence": [],
        })
        delta = 2 if position == "support" else (-2 if position == "oppose" else 1)
        relation["trust"] = max(0, min(100, float(relation.get("trust", 50)) + delta))
        relation["hostility"] = max(0, min(100, float(relation.get("hostility", 20)) - delta))
        relation["confidence"] = min(1.0, float(relation.get("confidence", 0.25)) + 0.1)
        relation.setdefault("evidence", []).append({
            "round": int(st.get("round") or 0),
            "text": "我方把本轮方案直接递给了" + legacy.PARTY.get(target, target),
            "trust_delta": delta,
        })
        relation["evidence"] = relation["evidence"][-6:]

    for message in reversed(st.get("messages") or []):
        if message.get("role") == "player":
            message["stance"] = position
            message["addressed_to"] = [target] if target else []
            break


def _check_convergence(st: dict, round_no: int) -> None:
    """连续 N 轮立场没变、没有暗线、没有事件 → 判定议题收敛，提前结束。"""
    data = ensure_diplomacy(st)
    stances = data.get("issue_stances") or {}
    sig = "|".join(str((stances.get(k) or {}).get("stance")) for k in sorted(stances))
    st["_stance_sig"] = sig
    prev = st.get("_converge_sig")
    st["_converge_sig"] = sig
    channels = len(data.get("channels") or [])
    events = len(st.get("events") or [])
    changed = sig != prev
    quiet = (not changed
             and channels == int(st.get("_converge_channels") or -1)
             and events == int(st.get("_converge_events") or -1))
    st["_converge_channels"] = channels
    st["_converge_events"] = events
    st["_quiet_rounds"] = (0 if not quiet else int(st.get("_quiet_rounds") or 0) + 1)
    if int(st["_quiet_rounds"]) >= OBSERVE_CONVERGE and int(st.get("turn_count") or 0) >= 4:
        st["finished"] = True
        st["finish_reason"] = "议题已收敛（连续 %d 轮无新变化）" % OBSERVE_CONVERGE


def _card_names(st: dict, card_ids: list[str]) -> list[str]:
    """把卡牌 id 换成人能读的名字（找不到就退回 id）。"""
    catalog = {}
    try:
        # 手牌 + 牌库全表，用过的卡（已进弃牌堆）也能查到名字
        for c in legacy.strategy_cards(st):
            catalog[str(c.get("id"))] = str(c.get("name") or "")
        bucket = legacy._deck_bucket(st, str(st.get("you_key") or ""))
        for cid, card in (bucket.get("all") or {}).items():
            catalog.setdefault(str(cid), str(card.get("name") or ""))
    except Exception as exc:  # noqa: BLE001
        print("  [cards] 名称解析跳过：" + str(exc))
    return [catalog.get(str(cid)) or str(cid) for cid in card_ids]


def _pick_next_multi_speaker(st: dict) -> None:
    """多边 NPC 之间互相回应：按名单轮转，跳过玩家和刚说过话的人。"""
    rivals = [r for r in (st.get("rivals") or []) if r and r != st.get("you_key")]
    if not rivals:
        return
    last = str(st.get("speaker_key") or "")
    # 规则一：上一位点名了谁，谁就先回应
    msgs = st.get("messages") or []
    cued = []
    for msg in reversed(msgs):
        if msg.get("role") in ("player", "agent") and msg.get("key") != last:
            cued = [k for k in (msg.get("addressed_to") or []) if k in rivals]
            break
    if cued:
        st["_force_speaker"] = cued[0]
        st["_cue_reason"] = "cued"
        return
    # 规则二：没人被点名，就按名单轮值（他可以对全体发言或主动点名别人）
    idx = rivals.index(last) if last in rivals else -1
    st["_force_speaker"] = rivals[(idx + 1) % len(rivals)]
    st["_cue_reason"] = "rotate"


def _player_speech(st: dict, card_ids: list[str]) -> str:
    """玩家只出牌时，让模型写一段正式发言（失败返回空串）。"""
    names = _card_names(st, card_ids)
    if not names:
        return ""
    who = legacy.PARTY.get(st.get("you_key") or "", "我方")
    topic = str(st.get("topic") or "当前议题")
    prompt = ("你是" + who + "代表团的外交官，正在「" + topic + "」的会场上发言。\n"
              "本轮你方决定采取的动作由这些策略体现：" + "、".join(names) + "。\n"
              "请用 2-4 句正式、克制的中文发言表达：你方立场、你方愿意给出什么、要求对方做什么。\n"
              "不要提「卡牌」「行动点」等游戏词汇，不要使用 Markdown，只输出发言正文。")
    try:
        raw = legacy.engine.call_deepseek(
            [{"role": "user", "content": prompt}], json_mode=False)
    except BaseException as exc:  # noqa: BLE001  未配置密钥时引擎会 SystemExit
        print("  [player] 发言生成失败：" + str(exc))
        return ""
    if isinstance(raw, dict):
        raw = raw.get("content") or raw.get("text") or ""
    elif isinstance(raw, (tuple, list)):
        raw = raw[0] if raw else ""
    out = str(raw or "").strip()
    # 去掉模型偶尔自带的引号/括号包裹
    if out[:1] in "（(\"'" and out[-1:] in "）)\"'":
        out = out[1:-1].strip()
    return out[:600]


def run_v2_turn(st: dict, payload: dict) -> dict:
    """执行一轮：玩家出牌 → 轮值国家 Agent 回应 → 结算 → 返回 view。"""
    text = str(payload.get("text") or "").strip()
    raw_ids = payload.get("card_ids")
    card_ids = [str(cid) for cid in raw_ids] if isinstance(raw_ids, list) else []
    auto = bool(payload.get("auto")) and st.get("mode") in ("observe", "multi")
    if auto:
        if st.get("finished"):
            return {"ok": True, "view": _v2_view(st, payload), "finished": True,
                    "reason": st.get("finish_reason") or "推演已结束"}
        now = time.time()
        if now - float(st.get("last_turn_at") or 0) < OBSERVE_MIN_GAP:
            return {"ok": False, "error": "推演速度过快，请稍候再继续"}
        limit = int(st.get("max_turns") or OBSERVE_MAX_TURNS)
        if int(st.get("turn_count") or 0) >= limit:
            st["finished"] = True
            st["finish_reason"] = "轮次用尽（%d 轮）" % limit
            return {"ok": True, "view": _v2_view(st, payload), "finished": True,
                    "reason": st["finish_reason"]}
        st["last_turn_at"] = now
    if not auto and not text and not card_ids:
        return {"error": "请选择策略卡，或输入一段公开发言"}

    hand = {str(card.get("id")): int(card.get("cost") or 1) for card in legacy.strategy_cards(st)}
    if len(set(card_ids)) != len(card_ids):
        return {"error": "同一张牌不能在一轮内重复使用"}
    unknown = [cid for cid in card_ids if cid not in hand]
    if unknown:
        return {"error": "未知策略卡：" + "、".join(unknown)}
    if sum(hand[cid] for cid in card_ids) > ACTION_POINTS:
        return {"error": "行动点不足：本轮最多消耗 " + str(ACTION_POINTS) + " 点"}
    actions_now = _card_actions(st, card_ids)
    if actions_now and all(action == "bluff" for action in actions_now):
        return {"error": "「虚张声势」必须配合一张动作卡使用"}
    if not auto and not text:
        # 只出牌不打字：让模型按卡牌生成一段完整发言，失败再退回模板
        text = _player_speech(st, card_ids) or _compose_card_text(st, card_ids)
    if not auto and not text:
        return {"error": "策略卡没有生成可用的发言内容"}

    start = len(st.get("messages") or [])
    events_before = len(st.get("events") or [])
    target = str(payload.get("target") or "").strip() or None
    if target and target not in (st.get("party_indexes") or {}):
        target = None
    if target and st.get("mode") != "observe":
        # 点名谁，就由谁回应本轮
        st["_force_speaker"] = target
    elif auto and st.get("mode") == "multi":
        _pick_next_multi_speaker(st)
    with legacy.SESS_LOCK:
        result = legacy.do_turn(st, text, auto=auto, card_ids=card_ids)
    st.pop("_force_speaker", None)
    if result.get("error"):
        return {"error": result["error"]}

    round_no = int(st.get("round") or 0)
    stamp_rounds(st, round_no, start)
    # 被点名统计：连续被追问的成员会在提示词里收到减压提示
    try:
        msgs = st.get("messages") or []
        last = msgs[-1] if msgs else {}
        counts = st.setdefault("_cue_count", {})
        for key in (last.get("addressed_to") or []):
            counts[key] = int(counts.get(key) or 0) + 1
    except Exception as exc:  # noqa: BLE001
        print("  [cue] 计数跳过：" + str(exc))
    st["_last_deltas"] = result.get("deltas") or {"player": {}, "agent": {}}
    try:
        legacy.consume_cards(st, card_ids)
    except Exception as exc:  # noqa: BLE001
        print("  [deck] 弃牌跳过：" + str(exc))
    try:
        _record_player_claim(st, card_ids, target, text)
    except Exception as exc:  # noqa: BLE001
        print("  [bluff] 玩家宣称记录跳过：" + str(exc))
    try:
        _apply_player_stance(st, card_ids, target)
    except Exception as exc:  # noqa: BLE001
        print("  [diplomacy] 玩家立场映射跳过：" + str(exc))
    st["risk"] = risk_for(st, text, st.get("speaker_key"))
    try:
        SETTLEMENT.record_public_turn(st)
    except Exception as exc:  # noqa: BLE001
        print("  [diplomacy] 立场/关系结算跳过：" + str(exc))
    try:
        _maybe_npc_backchannel(st, round_no)
    except Exception as exc:  # noqa: BLE001
        print("  [diplomacy] NPC 暗线跳过：" + str(exc))
    try:
        follow_through(st, round_no)
    except Exception as exc:  # noqa: BLE001
        print("  [diplomacy] 暗线跟进跳过：" + str(exc))

    events = st.get("events") or []
    event = events[-1] if len(events) > events_before else None
    warnings = result.get("warnings") or []
    # 先出视图（camp.changed 要和本轮开始前的立场比），再刷新快照
    if auto:
        st["turn_count"] = int(st.get("turn_count") or 0) + 1
        _check_convergence(st, round_no)
        if st.get("mode") == "multi":
            st["_auto_left"] = max(0, int(st.get("_auto_left") or 0) - 1)
    elif st.get("mode") == "multi":
        # 玩家这一轮结束后，安排两位 NPC 依次回应
        st["_auto_left"] = MULTI_AUTO_REPLIES
    view = _v2_view(st, payload)
    snapshot_stances(st)
    view["auto_left"] = int(st.get("_auto_left") or 0)
    return {
        "ok": True,
        "view": view,
        "event": event,
        "warning": warnings[-1] if warnings else None,
        "deltas": st["_last_deltas"],
        "settle_notes": [],
        "fact_check": {},
    }


def deal_v2(st: dict, payload: dict) -> dict:
    action = str(payload.get("action") or "").strip()
    player = st.get("you_key") or ""
    key = str(payload.get("key") or st.get("speaker_key") or "")
    if action == "invite":
        if st.get("mode") == "observe":
            return {"ok": False, "error": "观战模式不能主动发起沟通"}
        if key == player or key not in (st.get("party_indexes") or {}):
            return {"ok": False, "error": "无效的沟通对象"}
        channel = open_channel(st, player, key, legacy.PARTY.get(key, key))
        return {
            "ok": True,
            "view": _v2_view(st, payload),
            "message": "对方接受了沟通请求 · 可交换非约束性意向，公开确认前不结算",
            "result": {"deal": _deal_row(st, channel["id"])},
        }

    if action in ("accept", "confirm", "decline"):
        deal_id = payload.get("deal_id")
        channel = channel_for(st, str(deal_id)) if deal_id else None
        if channel is None:
            mine = [item for item in ensure_diplomacy(st)["channels"]
                    if player in (item.get("participants") or [])]
            channel = mine[-1] if mine else None
        if channel is None:
            return {"ok": False, "error": "没有可处理的非正式渠道"}

        if action == "accept":
            accept_channel_draft(st, channel)
            return {
                "ok": True,
                "view": _v2_view(st, payload),
                "message": "意向已记录 · 需用正式卡牌公开确认后才结算",
                "result": {"deal": _deal_row(st, channel["id"])},
            }
        if action == "confirm":
            if (channel.get("draft") or {}).get("status") != "accepted":
                return {"ok": False, "error": "须先接受非正式意向，才能公开确认"}
            proposal = create_proposal(st, channel, "非正式意向公开确认", player, stage="principle")
            SETTLEMENT.confirm_proposal(st, proposal)
            channel["draft"]["status"] = "confirmed"
            return {
                "ok": True,
                "view": _v2_view(st, payload),
                "message": "已公开确认 · 利益与信任已结算",
                "result": {"deal": _deal_row(st, channel["id"])},
            }
        channel["status"] = "closed"
        channel["draft"]["status"] = "declined"
        return {
            "ok": True,
            "view": _v2_view(st, payload),
            "message": "已暂不回应该沟通请求 · 公开路线不受影响",
            "result": {"deal": _deal_row(st, channel["id"])},
        }

    if action == "secret":
        return {"ok": False, "error": "本场景未开放秘密附件：需议题授权才能申请"}
    return {"ok": False, "error": "未知动作：" + (action or "(空)")}


def _split_cfg_lines(text: str) -> list[str]:
    chunks = re.split(r"(?:\s*\d+\s*[.、．:：]\s*)|[\n；;]+", str(text or ""))
    return [chunk.strip(" ．.、;；") for chunk in chunks if chunk.strip(" ．.、;；")]


def _npc_offer(cfg: dict, label: str = "", partner: str = "") -> str:
    """从角色配置里取一个像样的交换条件，凑不齐就退回通用表述。"""
    strat = cfg.get("strategy")
    coop_src = (strat or {}).get("cooperate_conditions") if isinstance(strat, dict) else None
    coop = [str(item).strip() for item in (coop_src or [])
            if len(str(item).strip()) >= 4]
    interests = _split_cfg_lines(cfg.get("core_interests_ranked") or "")
    if coop:
        base = coop[len(label) % len(coop)]
    elif len(interests) > 1:
        base = interests[1]
    else:
        base = "程序性安排"
    return "以「" + base[:16] + "」换取" + (partner or "对方") + "在表决上的支持"


def _initiative_of(key: str) -> float:
    """主体主动发起非正式沟通的倾向（0~1，写在 agents.json 的 initiative）。"""
    cfg = legacy.AGENTS.get(key) or {}
    try:
        return max(0.0, min(1.0, float(cfg.get("initiative", 0.5))))
    except (TypeError, ValueError):
        return 0.5


def _maybe_npc_backchannel(st: dict, round_no: int) -> dict | None:
    """按各主体的发起倾向，随机让一方主动开启非正式沟通。"""
    if not round_no:
        return None
    mode = st.get("mode")
    data = ensure_diplomacy(st)
    channels = data.get("channels") or []
    if len(channels) >= NPC_BACKCHANNEL_MAX:
        return None
    # 冷却：最近 GAP 轮内已有新渠道就不再发起
    if any(int(c.get("created_round") or 0) > round_no - NPC_BACKCHANNEL_GAP for c in channels):
        return None
    # 同一对组合只邀请一次：已经谈过的就不再重复骚扰
    talked = {tuple(sorted(c.get("participants") or [])) for c in channels}
    # 即便之前的渠道被拒绝/关闭，也不再重启同一对组合
    for pair in (st.get("_bpairs") or []):
        talked.add(tuple(sorted(pair)))
    # 同一主体重复邀请已在 talked 里挡住；其他主体可以继续来找你

    parties = list((st.get("party_indexes") or {}).keys())
    player = st.get("you_key")
    if mode == "observe":
        pool = [p for p in parties if len(parties) >= 3]
    else:
        pool = [p for p in parties if p != player]
    if not pool:
        return None

    # 按倾向加权抽一个发起方
    weights = [_initiative_of(p) for p in pool]
    if sum(weights) <= 0:
        return None
    initiator = random.choices(pool, weights=weights, k=1)[0]
    # 发起概率 = 该主体的倾向 × 基础频率
    if random.random() > _initiative_of(initiator) * NPC_BACKCHANNEL_RATE:
        return None

    if mode == "observe":
        others = [p for p in parties if p != initiator
                  and tuple(sorted((p, initiator))) not in talked]
        target = random.choice(others) if others else None
    else:
        target = player if tuple(sorted((initiator, player))) not in talked else None
    if not target:
        return None

    st.setdefault("_bpairs", []).append(sorted((initiator, target)))
    label_i = legacy.PARTY.get(initiator, initiator)
    label_t = legacy.PARTY.get(target, target)
    return open_backchannel(
        st, initiator, target,
        _npc_offer(legacy.AGENTS.get(initiator) or {}, label_i, label_t),
        _npc_offer(legacy.AGENTS.get(target) or {}, label_t, label_i),
        round_no, label_i, label_t,
    )


def intel_v2(st: dict, payload: dict) -> dict:
    """「识破」是私密情报：只有持有人能动它（留着 / 放风 / 出售 / 揭穿）。"""
    ledger = legacy.diplomacy.intel_for(st, st.get("you_key") or "")
    intel_id = str(payload.get("intel_id") or "")
    entry = next((item for item in ledger if item.get("id") == intel_id), None)
    if entry is None:
        return {"ok": False, "error": "没有这条情报"}
    result = legacy.diplomacy.intel_act(
        st, entry, payload.get("action"), payload.get("target"), legacy.PARTY.get)
    result["view"] = _v2_view(st, payload)
    return result


def end_v2(st: dict, payload: dict) -> dict:
    st["finished"] = True
    if st.get("started_at"):
        st["elapsed"] = int(time.time() - st["started_at"])
    return {"ok": True, "view": _v2_view(st, payload), "report": report_for(st)}


class Handler(legacy.Handler):
    server_version = "DiplomatDemo/2.0"

    def _current(self):
        sid, st, created = self._with_session()
        ensure_state(st)
        return sid, st, created

    def _json_state(self, st, sid=None, perspective="player", party=None):
        self._json(200, state_payload(st, perspective, party), sid)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            self._static("index.html")
            return
        if path == "/api/v2/ping":
            self._json(200, {"ok": True, "time": time.time(),
                             "offline": not legacy.current_key()})
            return
        if path == "/api/v2/meta":
            self._json(200, {"ok": True, "modes": ["bilateral", "multi", "observe"],
                             "topic_ids": ["compute-chip", "unclos", "dst"],
                             "offline": not legacy.current_key()})
            return
        if path == "/api/v2/state":
            _sid, st, _created = self._current()
            query = parse_qs(parsed.query)
            payload = {
                "perspective": (query.get("perspective") or ["player"])[0],
                "follow": (query.get("follow") or [None])[0],
                "party": (query.get("party") or [None])[0],
            }
            self._json(200, {"ok": True, "view": _v2_view(st, payload),
                             "offline": not legacy.current_key(),
                             "model": legacy.engine.MODEL})
            return
        if path == "/api/state":
            sid, st = self._peek_session()
            created = False
            if st is None:
                sid, st, created = self._current()
            ensure_state(st)
            query = parse_qs(parsed.query)
            perspective = (query.get("perspective") or ["player"])[0]
            party = (query.get("party") or [None])[0]
            self._json_state(st, sid if created else None, perspective, party)
            return
        if path == "/api/analysis":
            _sid, st, _created = self._current()
            query = parse_qs(parsed.query)
            perspective = (query.get("perspective") or ["player"])[0]
            party = (query.get("party") or [None])[0]
            self._json(200, public_diplomacy(st, perspective=perspective, party=party))
            return
        if path == "/api/kb":
            topic_id = (parse_qs(parsed.query).get("topicId") or [""])[0]
            self._json(200, legacy.kb_digest(topic_id))
            return
        if path == "/api/brain":
            self._json(200, legacy._brain_status(legacy.engine))
            return
        if path.startswith("/api/"):
            self._json(404, {"error": "not found"})
            return
        if legacy.FIXED_SID:
            self._static(path)
            return
        sid, st, created = self._current()
        self._static(path, sid if created else None)

    def _read_payload(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            return None

    def do_POST(self):
        payload = self._read_payload()
        if payload is None:
            self._json(400, {"error": "请求体不是合法 JSON"})
            return
        sid, st, created = self._current()
        cookie = sid if created else None
        path = urlparse(self.path).path
        try:
            if path == "/api/v2/session":
                with legacy.SESS_LOCK:
                    fresh = new_v2_state(payload)
                    legacy.SESSIONS[sid] = fresh
                self._json(200, {"ok": True, "view": _v2_view(fresh, payload),
                                 "offline": not legacy.current_key(),
                                 "model": legacy.engine.MODEL}, cookie)
                return

            if path == "/api/v2/say":
                result = run_v2_turn(st, payload)
                self._json(200 if result.get("ok") else 400, result, cookie)
                return

            if path == "/api/v2/deal":
                result = deal_v2(st, payload)
                self._json(200 if result.get("ok") else 400, result, cookie)
                return

            if path == "/api/v2/intel":
                result = intel_v2(st, payload)
                self._json(200 if result.get("ok") else 400, result, cookie)
                return

            if path == "/api/v2/debug/intel":
                # 演示/调试用：只在 DEMO_DEBUG=1 时开，用来给"情报账本"造一条样例
                if os.environ.get("DEMO_DEBUG") != "1":
                    self._json(404, {"error": "not found"}, cookie)
                    return
                entry = legacy.diplomacy.add_intel(
                    st, holder=st.get("you_key") or "cn",
                    target=str(payload.get("target") or st.get("speaker_key") or "us"),
                    round_no=int(st.get("round") or 0) + 2,
                    claim=str(payload.get("claim") or "threat"),
                    real=str(payload.get("real") or "probe"),
                    credibility=float(payload.get("credibility") or 0.33))
                self._json(200, {"ok": True, "entry": entry,
                                 "view": _v2_view(st, payload)}, cookie)
                return

            if path == "/api/v2/end":
                self._json(200, dict(end_v2(st, payload), event=None, warning=None), cookie)
                return

            if path == "/api/session":
                rivals = payload.get("rivals")
                agent = str(payload.get("rival") or (rivals[0] if rivals else "us"))
                if not isinstance(rivals, list) or not rivals:
                    rivals = [agent]
                scene = {
                    "agent": agent,
                    "player": payload.get("you") or "cn",
                    "rivals": rivals,
                    "mode": str(payload.get("mode") or "duel"),
                    "topic": str(payload.get("topic") or ""),
                    "topic_id": str(payload.get("topicId") or ""),
                }
                with legacy.SESS_LOCK:
                    legacy.SESSIONS[sid] = new_state(scene)
                    if payload.get("rounds") not in (None, ""):
                        legacy.SESSIONS[sid]["max_rounds"] = max(1, min(30, int(payload["rounds"])))
                    st = legacy.SESSIONS[sid]
                self._json(200, {"ok": True, "state": state_payload(st)}, cookie)
                return

            if path == "/api/reset":
                with legacy.SESS_LOCK:
                    keep = st.get("scene")
                    legacy.SESSIONS[sid] = new_state(keep)
                self._json(200, {"ok": True}, cookie)
                return

            if path == "/api/finish":
                st["finished"] = True
                if st.get("started_at"):
                    st["elapsed"] = int(time.time() - st["started_at"])
                self._json(200, {"ok": True, "state": state_payload(st)}, cookie)
                return

            if path == "/api/say":
                text = str(payload.get("text") or "").strip()
                auto = bool(payload.get("auto")) and st.get("mode") == "observe"
                if not text and not auto:
                    self._json(400, {"error": "发言不能为空"}, cookie)
                    return
                card_ids = payload.get("card_ids") or []
                if not isinstance(card_ids, list) or len(set(card_ids)) != len(card_ids):
                    self._json(400, {"error": "卡牌选择无效"}, cookie)
                    return
                hand_costs = {card["id"]: int(card.get("cost") or 1)
                              for card in legacy.strategy_cards(st)}
                if any(card not in hand_costs for card in card_ids):
                    self._json(400, {"error": "未知策略卡"}, cookie)
                    return
                if sum(hand_costs[card] for card in card_ids) > ACTION_POINTS:
                    self._json(400, {"error": "行动点不足"}, cookie)
                    return
                with legacy.SESS_LOCK:
                    result = legacy.do_turn(st, text, auto=auto)
                    if "error" not in result:
                        SETTLEMENT.record_public_turn(st)
                        result["state"] = state_payload(st)
                self._json(200, result, cookie)
                return

            if path == "/api/channels":
                if st.get("mode") == "observe":
                    self._json(400, {"error": "观战模式不能新建玩家密谈"}, cookie)
                    return
                target = str(payload.get("target") or "").strip()
                participants = set((st.get("party_indexes") or {}).keys())
                if target not in participants or target == st.get("you_key"):
                    self._json(400, {"error": "无效的沟通对象"}, cookie)
                    return
                channel = open_channel(st, st["you_key"], target, legacy.PARTY.get(target, target))
                self._json(200, {"ok": True, "channel": channel, "state": state_payload(st)}, cookie)
                return

            parts = [part for part in path.split("/") if part]
            if len(parts) == 3 and parts[:2] == ["api", "channels"]:
                channel = channel_for(st, parts[2])
                if channel is None:
                    self._json(404, {"error": "渠道不存在"}, cookie)
                    return
                require_player_channel(st, channel)
                self._json(200, {"ok": True, "channel": channel}, cookie)
                return

            if len(parts) == 4 and parts[:2] == ["api", "channels"]:
                channel = channel_for(st, parts[2])
                if channel is None:
                    self._json(404, {"error": "渠道不存在"}, cookie)
                    return
                require_player_channel(st, channel)
                action = parts[3]
                if action == "message":
                    text = str(payload.get("text") or "").strip()
                    if not text:
                        self._json(400, {"error": "私下消息不能为空"}, cookie)
                        return
                    player = st["you_key"]
                    target = next(key for key in channel["participants"] if key != player)
                    add_channel_message(st, channel, player, text)
                    prompt = legacy.system_prompt_now(st.get("scene"), speaker=target)
                    turn = agent_for(st, target).act_private(
                        system_prompt=prompt,
                        channel=channel,
                        public_messages=st["messages"],
                        text=text,
                        topic=st.get("topic") or "",
                        call_model=caller_if_online(),
                    )
                    obj = turn["obj"]
                    add_channel_message(st, channel, target, obj["response"])
                    for field in ("our_term", "their_term"):
                        if str(obj.get(field) or "").strip():
                            channel["draft"][field] = str(obj[field]).strip()[:240]
                    channel["draft"]["status"] = "pending"
                    self._json(200, {"ok": True, "reply": obj, "state": state_payload(st)}, cookie)
                    return
                if action == "accept":
                    draft = accept_channel_draft(st, channel)
                    self._json(200, {"ok": True, "draft": draft, "state": state_payload(st)}, cookie)
                    return

            if path == "/api/proposals":
                channel = None
                if payload.get("channel_id"):
                    channel = channel_for(st, str(payload["channel_id"]))
                    if channel is None:
                        self._json(404, {"error": "渠道不存在"}, cookie)
                        return
                    require_player_channel(st, channel)
                proposal = create_proposal(
                    st,
                    channel,
                    str(payload.get("title") or "公开协调提案"),
                    st.get("you_key") or st.get("speaker_key"),
                )
                self._json(200, {"ok": True, "proposal": proposal, "state": state_payload(st)}, cookie)
                return

            if len(parts) == 4 and parts[:2] == ["api", "proposals"]:
                proposal = proposal_for(st, parts[2])
                if proposal is None:
                    self._json(404, {"error": "提案不存在"}, cookie)
                    return
                action = parts[3]
                if action == "confirm":
                    if proposal.get("channel_id"):
                        channel = channel_for(st, proposal["channel_id"])
                        require_player_channel(st, channel)
                    SETTLEMENT.confirm_proposal(st, proposal)
                    self._json(200, {"ok": True, "proposal": proposal, "state": state_payload(st)}, cookie)
                    return
                if action == "vote":
                    if proposal.get("confirmed"):
                        self._json(400, {"error": "已确认提案无需再次表决"}, cookie)
                        return
                    player = st.get("you_key")
                    if st.get("mode") != "observe":
                        vote = str(payload.get("vote") or "")
                        SETTLEMENT.register_vote(proposal, player, vote, "玩家公开表决")
                    caller = caller_if_online()
                    for key in st.get("party_indexes") or {}:
                        if key in proposal["votes"]:
                            continue
                        prompt = legacy.system_prompt_now(st.get("scene"), speaker=key)
                        stance = st["diplomacy"]["issue_stances"][key]
                        decision = agent_for(st, key).assess_proposal(
                            system_prompt=prompt,
                            proposal=proposal,
                            stance=stance,
                            topic=st.get("topic") or "",
                            call_model=caller,
                        )
                        SETTLEMENT.register_vote(proposal, key, decision["vote"], decision["reason"])
                    summary = SETTLEMENT.finish_vote(st, proposal)
                    self._json(200, {"ok": True, "summary": summary, "proposal": proposal,
                                     "state": state_payload(st)}, cookie)
                    return

            self._json(404, {"error": "not found"}, cookie)
        except ValueError as exc:
            self._json(400, {"error": str(exc)}, cookie)
        except SystemExit as exc:
            self._json(502, {"error": "模型调用失败：" + str(exc)}, cookie)
        except Exception as exc:
            self._json(500, {"error": type(exc).__name__ + ": " + str(exc)}, cookie)


def main():
    print("=" * 64)
    print("  Diplomat 2.0 · 独立新版服务（旧版保持不变）")
    print("  新机制：议题阵营 / 关系矩阵 / 非正式渠道 / 提案表决 / 视角隔离")
    print(f"  入口：http://127.0.0.1:{PORT}/")
    print(f"  模型：{legacy.engine.MODEL if legacy.current_key() else '离线演示'}")
    print("=" * 64)
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(
            f"http://127.0.0.1:{PORT}/")).start()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.serve_forever()


if __name__ == "__main__":
    main()

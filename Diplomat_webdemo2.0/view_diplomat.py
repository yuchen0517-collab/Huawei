#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把多智能体会话状态映射成 webdemo 2.0 前端使用的 view 契约。

前端（site/diplomat/assets/live.js）只认一个 view 对象：三指数、阵营、关系矩阵、
情报区间、外交渠道、谈判树、手牌、解说。这里负责把 demo1.1 的 CountryAgent 状态
和 diplomacy.py 的议题/关系/渠道数据翻译成那个形状，不改动任何结算逻辑。
"""

from __future__ import annotations

import copy
import re

import server as legacy
from diplomacy import ensure_diplomacy, intel_for

MODE_MAP = {"duel": "bilateral", "multi": "multi", "observe": "observe"}
MODE_LABEL = {"bilateral": "双边谈判", "multi": "多边磋商", "observe": "九方观战"}
STANCE_LABEL = {"support": "支持", "swing": "摇摆", "oppose": "反对"}
CHANGE_LABEL = {"up": "立场上移", "down": "立场下移", "hold": "立场未变"}
INDEX_KEYS = ("interest", "image", "trust")
INDEX_LABEL = {"interest": "主体利益", "image": "国际形象", "trust": "盟友信任"}
ACTION_LABEL_CN = {
    "offer": "出价", "concede": "让步", "demand": "索价", "threat": "威胁",
    "disclose": "揭露", "probe": "试探", "procedure": "程序", "batna": "底线",
}

# 卡牌在 UI 上要显示的博弈模型读数和预计影响，结算仍走 legacy 的 deltas。
CARD_META = {
    "fact": {"model": "信号与甄别", "desc": "通过澄清信息降低误判，让对方暴露真实接受边界"},
    "exchange": {"model": "条件交换博弈", "desc": "以明确对价实现互惠，让双方都能保留核心利益"},
    "redline": {"model": "承诺与威慑", "desc": "用可信的拒绝抬高对方要价成本，守住不可交易区"},
    "probe": {"model": "信号与甄别", "desc": "先不承诺，用试探问题换情报，测试对方接受边界"},
    "concede": {"model": "重复博弈 · 互惠", "desc": "在小事上先让一步，换取对方后续合作意愿"},
    "package": {"model": "猎鹿博弈 · 协调均衡", "desc": "把多个议题打包，引导各方选择共同收益更高的点"},
}

TRIGGER_FALLBACK = ("取消管制", "解除制裁", "单方面", "核查我方", "歧视性")


def _clamp(value, low=0.0, high=100.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = low
    return max(low, min(high, round(number, 1)))


def _label(key: str) -> str:
    return legacy.PARTY.get(key, key)


def _flag(key: str) -> str:
    return legacy.FLAG.get(key, "🏳")


def _participants(st: dict) -> list[str]:
    diplomacy = ensure_diplomacy(st)
    keys = list((st.get("party_indexes") or {}).keys())
    for key in [st.get("you_key")] + list(st.get("rivals") or []):
        if key and key not in keys:
            keys.append(key)
    for key in diplomacy.get("issue_stances") or {}:
        if key not in keys:
            keys.append(key)
    return keys


def _indexes(st: dict, key: str) -> dict:
    row = (st.get("party_indexes") or {}).get(key) or {}
    return {field: _clamp(row.get(field, 50)) for field in INDEX_KEYS}


def _stance_row(st: dict, key: str) -> dict:
    diplomacy = ensure_diplomacy(st)
    stance = (diplomacy.get("issue_stances") or {}).get(key) or {}
    position = stance.get("stance") or "swing"
    evidence = stance.get("evidence") or []
    reason = str((evidence[-1] or {}).get("text") or "") if evidence else ""
    previous = (diplomacy.get("prev_stances") or {}).get(key)
    order = {"oppose": 0, "swing": 1, "support": 2}
    if previous is None or previous == position:
        change = "hold"
    else:
        change = "up" if order.get(position, 1) > order.get(previous, 1) else "down"
    return {
        "position": position,
        "position_label": STANCE_LABEL.get(position, "摇摆"),
        "change": change,
        "change_label": CHANGE_LABEL.get(change, ""),
        "reason": reason[:40],
        "support_score": int(stance.get("support_score", 50)),
        "confidence": round(float(stance.get("confidence", 0.25)), 2),
    }


def _camp(st: dict, parties: list[str]) -> dict:
    rows = []
    counts = {"support": 0, "swing": 0, "oppose": 0}
    changed = []
    previous = (ensure_diplomacy(st).get("prev_stances") or {})
    for key in parties:
        row = _stance_row(st, key)
        position = row["position"] if row["position"] in counts else "swing"
        counts[position] += 1
        rows.append({
            "key": key,
            "label": _label(key),
            "position": position,
            "position_label": STANCE_LABEL.get(position, "摇摆"),
            "reason": row["reason"] or "尚未公开发表议题立场",
        })
        old = previous.get(key)
        if old and old != position:
            changed.append({"key": _label(key), "from": old, "to": position})
    return {"counts": counts, "rows": rows, "changed": changed}


def _relation_cell(rel: dict) -> dict:
    trust = _clamp(rel.get("trust", 50))
    hostility = _clamp(rel.get("hostility", 20))
    affinity = _clamp(round(50 + (trust - 50) * 0.8 + (50 - hostility) * 0.4, 1))
    return {"trust": trust, "hostility": hostility, "affinity": affinity}


def _relations(st: dict, parties: list[str], viewer: str | None, full: bool) -> dict:
    diplomacy = ensure_diplomacy(st)
    cells = []
    for src in parties:
        for dst in parties:
            if src == dst:
                continue
            rel = ((diplomacy.get("relations") or {}).get(src) or {}).get(dst) or {}
            values = _relation_cell(rel)
            cell = {"src": src, "dst": dst}
            if full or src == viewer:
                cell["values"] = {key: {"kind": "exact", "value": values[key]} for key in values}
            elif dst == viewer and float(rel.get("confidence", 0)) >= 0.5:
                cell["values"] = {
                    key: {"kind": "estimate",
                          "range": [int(max(0, values[key] - 8)), int(min(100, values[key] + 8))]}
                    for key in values
                }
            else:
                cell["values"] = {key: {"kind": "unknown"} for key in values}
            cells.append(cell)
    return {
        "parties": parties,
        "labels": [_label(key) for key in parties],
        "cells": cells,
        "full": bool(full),
    }


def _tree(st: dict, viewer: str | None, full: bool) -> dict:
    nodes = []
    seq = 0
    last_public = None
    for message in st.get("messages") or []:
        role = message.get("role")
        if role not in ("player", "agent"):
            continue
        seq += 1
        speaker = str(message.get("key") or (st.get("you_key") if role == "player" else "")) or "?"
        node = {
            "id": "n" + str(seq),
            "round": int(message.get("round") or 0),
            "speaker": speaker,
            "speaker_label": _label(speaker),
            "kind": "claim" if role == "player" else "respond",
            "kind_label": "我方主张" if role == "player" else "公开回应",
            "claim": str(message.get("text") or "")[:120],
            "visibility": "public",
            "fictional": False,
            "responds_to": last_public,
            "basis": [],
        }
        last_public = node["id"]
        nodes.append(node)

    diplomacy = ensure_diplomacy(st)
    for entry in diplomacy.get("public_followups") or []:
        seq += 1
        participants = entry.get("participants") or []
        speaker = participants[0] if participants else "?"
        nodes.append({
            "id": "p" + str(seq),
            "round": int(entry.get("round") or 0),
            "speaker": speaker,
            "speaker_label": _label(speaker),
            "kind": "followup",
            "kind_label": "无下文" if entry.get("failed") else "公开呼应",
            "claim": str(entry.get("text") or "")[:120],
            "visibility": "public",
            "fictional": False,
            "responds_to": last_public,
            "basis": [],
        })
    for line in diplomacy.get("dark_lines") or []:
        participants = line.get("participants") or []
        if not full and viewer not in participants:
            continue
        seq += 1
        speaker = participants[0] if participants else "?"
        nodes.append({
            "id": "d" + str(seq),
            "round": int(line.get("round") or 0),
            "speaker": speaker,
            "speaker_label": _label(speaker),
            "kind": "nonpublic",
            "kind_label": "非公开意向",
            "claim": str(line.get("text") or "")[:120],
            "visibility": participants,
            "fictional": True,
            "fictional_label": "虚构 · 非史实",
            "responds_to": last_public,
            "basis": [],
        })
    return {"nodes": nodes}


def _policy(rel: dict) -> dict:
    trust = _clamp(rel.get("trust", 50))
    if trust >= 60:
        return {"policy": "open", "label": "可沟通", "disclosure": "须向授权团队备案",
                "secret_annex": False, "reason": "互信 " + str(int(trust)) + "，接受非正式接触"}
    if trust >= 35:
        return {"policy": "restricted", "label": "受限开放", "disclosure": "须备案 · 不进入公开直播",
                "secret_annex": False, "reason": "互信 " + str(int(trust)) + "，只谈程序性议题"}
    return {"policy": "closed", "label": "仅正式", "disclosure": "不接受非正式渠道",
            "secret_annex": False, "reason": "互信 " + str(int(trust)) + "，暂不接受密谈"}


def _channel_policies(st: dict, parties: list[str], player: str | None) -> list[dict]:
    diplomacy = ensure_diplomacy(st)
    rows = []
    for key in parties:
        if key == player:
            continue
        rel = ((diplomacy.get("relations") or {}).get(key) or {}).get(player or "") or {}
        policy = _policy(rel)
        rows.append({
            "key": key,
            "label": _label(key),
            "policy": policy["policy"],
            "policy_label": policy["label"],
            "disclosure": policy["disclosure"],
            "secret_annex": policy["secret_annex"],
            "reason": policy["reason"],
        })
    return rows


def _deals(st: dict, viewer: str | None = None, full: bool = False) -> list[dict]:
    diplomacy = ensure_diplomacy(st)
    out = []
    for channel in diplomacy.get("channels") or []:
        participants = channel.get("participants") or []
        if not full and viewer and viewer not in participants:
            continue
        if not full and not viewer:
            continue
        draft = channel.get("draft") or {}
        status = draft.get("status") or "pending"
        if status in ("confirmed", "publicized"):
            deal_status = "confirmed"
            status_label = "已公开确认" if status == "confirmed" else "已公开呼应"
        elif status == "accepted":
            deal_status, status_label = "intent", "待公开确认"
        elif status in ("declined", "broken"):
            deal_status, status_label = "expired", "未形成约束"
        else:
            deal_status, status_label = "draft", "待回复"
        participants = channel.get("participants") or []
        other = next((key for key in participants if key != st.get("you_key")),
                     participants[-1] if participants else "?")
        if full and len(participants) >= 2:
            # 全知视角看的是"谁跟谁"，不是"谁跟我"
            other = participants[1] if participants[0] == st.get("you_key") else participants[0]
        out.append({
            "id": channel.get("id"),
            "party": other,
            "party_label": _label(other),
            "participants": participants,
            "participant_labels": [_label(key) for key in participants],
            "status": deal_status,
            "status_label": status_label,
            "our_term": str(draft.get("our_term") or ""),
            "their_term": str(draft.get("their_term") or ""),
            "initiator": channel.get("initiator", "user"),
            "disclosure": "须向授权团队备案",
            "fictional": bool(channel.get("fictional")),
            "visibility": channel.get("visibility", "authorized"),
            "round": int(channel.get("created_round") or 0),
        })
    return out


def _ladder(policy: dict) -> list[dict]:
    open_state = "open" if policy.get("policy") == "open" else "restricted"
    return [
        {"no": "01", "name": "正式会场", "state": "open",
         "desc": "公开记录、正式提案与表决", "note": "始终可用"},
        {"no": "02", "name": "授权非正式沟通", "state": open_state,
         "desc": "经授权团队备案的双边接触", "note": policy.get("label", "受限")},
        {"no": "03", "name": "代表团层面对话", "state": open_state,
         "desc": "不记录文本的口头试探", "note": "不产生约束"},
        {"no": "04", "name": "秘密附件", "state": "closed",
         "desc": "仅限场景授权时开放", "note": "本场景不开放"},
        {"no": "05", "name": "公开确认", "state": "open",
         "desc": "用正式卡牌把意向转为约束", "note": "结算在此发生"},
    ]


def _split_lines(text: str) -> list[str]:
    chunks = re.split(r"(?:\s*\d+\s*[.、．:：]\s*)|[\n；;]+", str(text or ""))
    return [chunk.strip(" ．.、;；") for chunk in chunks if chunk and chunk.strip(" ．.、;；")]


def _intel(st: dict, opponent: str, viewer: str | None, full: bool) -> dict:
    diplomacy = ensure_diplomacy(st)
    stance = (diplomacy.get("issue_stances") or {}).get(opponent) or {}
    evidence = list(stance.get("evidence") or [])
    center = _indexes(st, opponent)["interest"]
    confidence = min(0.95, 0.25 + len(evidence) * 0.1)
    radius = max(3, int(14 - confidence * 10))

    cfg = {}
    try:
        cfg = legacy.scene_ctx(st.get("scene"), speaker=opponent).get("agent_cfg") or {}
    except Exception:  # noqa: BLE001
        cfg = {}
    red_lines = _split_lines(cfg.get("red_lines") or "")
    interests = _split_lines(cfg.get("core_interests_ranked") or "")
    cooperate = list(((cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}) or {}).get("cooperate_conditions") or [])
    tradeable = cooperate[:1] or interests[:1] or ["程序性安排与技术援助"]
    sensitive = interests[:1] or red_lines[1:2] or ["具体数字与时限"]
    redline = red_lines[:1] or ["核心主权与安全关切"]

    def zone(kind: str, label: str, item: str, note: str) -> dict:
        hits = len([row for row in evidence if kind[:4] in str(row.get("text") or "")])
        level = "high" if full else ("high" if hits >= 2 else "mid" if hits else "low")
        return {"kind": kind, "label": label, "item": item, "note": note,
                "confidence": level,
                "confidence_label": {"high": "高", "mid": "中", "low": "低"}[level]}

    return {
        "target": opponent,
        "interest_range": ([max(0, int(center - radius)), min(100, int(center + radius))]
                           if not full else [int(center), int(center)]),
        "confidence": "high" if full else ("high" if len(evidence) >= 3 else "mid" if evidence else "low"),
        "evidence_count": len(evidence),
        "accuracy": 96 if full else min(92, int(round(18 + 22 * min(len(evidence), 4) + confidence * 30))),
        "zones": [
            zone("tradeable", "可交易区", tradeable[0], "公开表态里反复出现的交换物"),
            zone("sensitive", "敏感区", sensitive[0], "触碰即抬高要价，但仍有空间"),
            zone("redline", "红线区", redline[0], "越线将触发强硬回应"),
        ],
    }


def _evidence(st: dict, opponent: str) -> list[dict]:
    diplomacy = ensure_diplomacy(st)
    stance = (diplomacy.get("issue_stances") or {}).get(opponent) or {}
    rows = []
    for entry in stance.get("evidence") or []:
        rows.append({
            "round": int(entry.get("round") or 0),
            "text": str(entry.get("text") or "")[:90],
            "source": "公开发言",
            "confidence": "mid",
        })
    return rows


def _trust_view(rel: dict) -> dict:
    trust = _clamp(rel.get("trust", 50))
    level = "较低" if trust < 36 else ("中等" if trust < 66 else "较高")
    trend = rel.get("trend")
    return {
        "value": int(trust),
        "label": level,
        "trend": trend or "flat",
        "trend_label": {"warming": "回暖", "cooling": "转冷", "flat": "持平"}.get(trend or "flat", "持平"),
        "confidence": "mid",
        "confidence_label": "中" if float(rel.get("confidence", 0)) >= 0.4 else "低",
    }


def _window(rel: dict, threshold: int = 60) -> dict:
    trust = _clamp(rel.get("trust", 50))
    basis = int(float(rel.get("confidence", 0)) * 10)
    if trust >= threshold:
        return {"stage": "open", "label": "开放", "basis": max(1, basis)}
    if trust >= 35:
        return {"stage": "limited", "label": "有限开放", "basis": max(1, basis)}
    return {"stage": "closed", "label": "尚未打开", "basis": 0}


def _hand(st: dict) -> list[dict]:
    try:
        cards = legacy.strategy_cards(st)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for index, card in enumerate(cards):
        meta = {"model": card.get("model") or "信号与甄别",
                "desc": (CARD_META.get(card.get("id")) or {}).get("desc", "")}
        effects = []
        for field, delta in zip(INDEX_KEYS, card.get("deltas") or []):
            if delta:
                effects.append(INDEX_LABEL[field] + (" +" if delta > 0 else " −") + str(abs(int(delta))))
        out.append({
            "id": card.get("id"),
            "name": card.get("name"),
            "kind": card.get("kind"),
            "type": card.get("kind"),
            "cost": int(card.get("cost") or 0),
            "rarity": card.get("rarity", "common"),
            "icon": card.get("icon", ""),
            "color": card.get("color", "#c9a061"),
            "desc": card.get("desc") or "",
            "detail": card.get("detail") or card.get("desc") or "",
            "effects": effects,
            "model_label": meta["model"],
            "model_desc": meta["desc"],
            "recommended": bool(card.get("recommended")),
            "action": card.get("action", ""),
            "tags": card.get("tags") or [],
        })
    return out


def _bluff_public(message: dict) -> dict | None:
    """识破是私密情报：对外只给「宣称/可信度/自己是否看穿」，不给看穿者名单。"""
    info = message.get("bluff")
    if not isinstance(info, dict):
        return None
    return {
        "claimed_action": info.get("claimed_action"),
        "real_action": info.get("real_action"),
        "claimed_strength": info.get("claimed_strength"),
        "credibility": info.get("credibility"),
        "player_noticed": bool(info.get("player_noticed")),
    }


def _messages(st: dict, full: bool = False) -> list[dict]:
    rows = []
    for message in st.get("messages") or []:
        role = message.get("role")
        if role not in ("player", "agent"):
            continue
        key = message.get("key") or st.get("you_key")
        # 对方的真实牌面只给全知视角；参与方只看得到"宣称"
        cards = message.get("cards") or []
        if role == "agent" and not full:
            cards = []
        rows.append({
            "role": role,
            "key": key,
            "speaker": key,
            "label": _label(key),
            "round": int(message.get("round") or 0),
            "text": str(message.get("text") or ""),
            "stance": message.get("stance"),
            "addressed_to": message.get("addressed_to") or [],
            "cards": cards,
            "claim": message.get("claim") or {},
            "bluff": _bluff_public(message),
            "fact_check": message.get("fact_check") or {},
        })
    return rows


def _recent_rounds(st: dict, rows: list[dict]) -> list[dict]:
    seen = {}
    for row in rows:
        if row["role"] != "agent":
            continue
        seen[row["round"]] = {"round": row["round"], "speaker": row["label"],
                              "summary": (row["text"] or "")[:30]}
    return [seen[key] for key in sorted(seen)][-4:]


def _narrator(st: dict, opponent: str, camp: dict) -> dict:
    last = st.get("last") or {}
    summary = str(last.get("summary") or "").strip()
    mood = str(last.get("mood") or "").strip()
    label = _label(opponent)
    counts = camp.get("counts") or {}
    swing = counts.get("swing", 0)
    if summary:
        neutral = label + "本轮" + (mood or "表态") + "，落点在「" + summary[:40] + "」。目前还有 " + str(swing) + " 方摇摆。"
        partisan = "站在" + label + "一侧看，这一轮没有实质退让；要把摇摆方拉过来，得先看它拿什么换。"
        snark = label + "把话说满了——" + (mood or "姿态很高") + "，可真正让利的条款一个字没提。"
    else:
        neutral = "本轮尚未开始。选择策略卡并提交，系统会结算三指数、情报信号与阵营变化。"
        partisan = "开局先看谁先出价；别急着让，先让对方把条件说完。"
        snark = "会议刚开始，各位代表还在念稿。"
    return {"neutral": neutral, "partisan": partisan, "snark": snark,
            "persona_labels": {"neutral": "中立分析师", "partisan": "偏袒发言方", "snark": "毒舌评论员"}}


def build_view(st: dict, perspective: str = "player", party: str | None = None) -> dict:
    """把会话状态翻译成前端 view。任何异常都不应冒到 HTTP 层。"""
    ensure_diplomacy(st)
    mode = MODE_MAP.get(str(st.get("mode")), "multi")
    observing = mode == "observe"
    full = bool(observing and perspective == "omniscient")
    viewer = st.get("you_key")
    if observing and perspective == "party" and party:
        viewer = party
    player = st.get("you_key") if not observing else None

    parties = _participants(st)
    speaker = str(st.get("speaker_key") or "") or (parties[0] if parties else "us")
    if speaker not in parties:
        speaker = parties[0] if parties else speaker

    relations = ensure_diplomacy(st).get("relations") or {}
    diplomacy = ensure_diplomacy(st)

    def rel_of(src: str, dst: str) -> dict:
        return ((relations.get(src) or {}).get(dst) or {})

    camp = _camp(st, parties)

    party_rows = []
    for key in parties:
        exact = bool(full or key == viewer)
        row = {
            "key": key,
            "label": _label(key),
            "flag": _flag(key),
            "stance": _stance_row(st, key),
            "is_player": key == (player or viewer),
            "exact": exact,
        }
        if exact:
            row["indexes"] = _indexes(st, key)
        else:
            idx = _indexes(st, key)
            estimate = _intel(st, key, viewer, False)["interest_range"]
            row["public_image"] = idx["image"]
            row["indexes_range"] = {
                "interest": estimate,
                "image": [int(max(0, idx["image"] - 6)), int(min(100, idx["image"] + 6))],
                "trust": "?",
            }
        party_rows.append(row)

    opponent_key = speaker if speaker != (player or viewer) else next(
        (key for key in parties if key != (player or viewer)), speaker)
    opp_idx = _indexes(st, opponent_key)
    opponent = {
        "key": opponent_key,
        "label": _label(opponent_key),
        "flag": _flag(opponent_key),
        "is_player": opponent_key == player,
        "exact": bool(full or opponent_key == viewer),
        "stance": _stance_row(st, opponent_key),
        "intel": _intel(st, opponent_key, viewer, full),
        "evidence": _evidence(st, opponent_key),
        "inner_os": "",
        "inner_os_limited": not full,
        "fictional": False,
    }
    if full:
        opponent["indexes"] = opp_idx
        last_summary = str((st.get("last") or {}).get("summary") or "")
        opponent["inner_os"] = last_summary or "本轮没有留下可读的内部摘要"
    else:
        opponent["public_image"] = opp_idx["image"]
        opponent["indexes_range"] = {"interest": opponent["intel"]["interest_range"],
                                     "image": [int(max(0, opp_idx["image"] - 6)),
                                               int(min(100, opp_idx["image"] + 6))],
                                     "trust": "?"}
        if mode != "observe":
            opponent["trust_toward_player"] = _trust_view(rel_of(opponent_key, player or viewer or ""))
            opponent["window"] = _window(rel_of(opponent_key, player or viewer or ""))
            opponent["channel"] = _policy(rel_of(opponent_key, player or viewer or ""))

    policies = _channel_policies(st, parties, player or viewer)
    opponent_policy = next((item for item in policies if item["key"] == opponent_key),
                           _policy(rel_of(opponent_key, player or viewer or "")))
    deals = _deals(st, viewer=None if full else (player or viewer), full=full)

    player_block = None
    if player:
        player_block = {
            "key": player,
            "label": _label(player),
            "flag": _flag(player),
            "indexes": _indexes(st, player),
            "stance": _stance_row(st, player),
            "hidden_tasks": [
                {"text": str(task.get("text") or task.get("priority") or ""),
                 "priority": str(task.get("priority") or ""),
                 "done": bool(task.get("done")),
                 "done_round": int(task.get("done_round") or 0)}
                for task in (st.get("tasks") or [])
            ],
        }

    message_rows = _messages(st, full)
    last_record = st.get("last") or {}
    deltas = st.get("_last_deltas") or {}
    risk = st.get("risk") or {}

    return {
        "mode": mode,
        "mode_label": MODE_LABEL.get(mode, mode),
        "round": int(st.get("round") or 0),
        "round_total": int(st.get("max_rounds") or 12),
        "max_rounds": int(st.get("max_rounds") or 12),
        "next_round": min(int(st.get("round") or 0) + 1, int(st.get("max_rounds") or 12)),
        "topic": st.get("topic") or "",
        "topic_id": str((st.get("scene") or {}).get("topic_id") or ""),
        "venue": "",
        "agenda": [],
        "perspective": perspective,
        "full": full,
        "speaker": speaker,
        "speaker_label": _label(speaker),
        "player": player_block,
        "opponent": opponent,
        "parties": party_rows,
        "camp": camp,
        "relations": _relations(st, parties, viewer, full),
        "tree": _tree(st, viewer, full),
        "channel": {
            "ladder": _ladder(opponent_policy),
            "deals": deals,
            "key": opponent_key,
        },
        "channel_policies": policies,
        "deals": deals,
        "pending_invite": None,
        "intel": _intel(st, opponent_key, viewer, full),
        "evidence": _evidence(st, opponent_key),
        "intel_ledger": [
            {
                "id": entry.get("id"),
                "target": entry.get("target"),
                "target_label": _label(entry.get("target")),
                "round": int(entry.get("round") or 0),
                "claim_label": ACTION_LABEL_CN.get(entry.get("claim"), entry.get("claim") or ""),
                "real_label": ACTION_LABEL_CN.get(entry.get("real"), entry.get("real") or ""),
                "credibility": entry.get("credibility"),
                "status": entry.get("status", "held"),
                "sold_to": entry.get("sold_to") or [],
            }
            for entry in intel_for(st, player or viewer or "")
        ],
        "risk": risk,
        "hand": _hand(st) if player else [],
        "action_points": {"max": 3, "remaining": 3},
        "last": {
            "deltas": deltas,
            "settle_notes": ([st["last_settle_note"]] if st.get("last_settle_note") else []),
            "summary": str(last_record.get("summary") or ""),
            "mood": str(last_record.get("mood") or ""),
            "fact_check": {"flagged": []},
        },
        "messages": message_rows,
        "recent_rounds": _recent_rounds(st, message_rows),
        "narrator": _narrator(st, (speaker if observing else opponent_key), camp),
        "events": (st.get("events") or [])[-3:],
        "finished": bool(st.get("finished")),
        "fictional_label": "虚构 · 非史实",
    }


def snapshot_stances(st: dict) -> None:
    """把当前立场存成上一轮快照，供 camp.changed 与 stance.change 使用。"""
    diplomacy = ensure_diplomacy(st)
    diplomacy["prev_stances"] = {
        key: str((row or {}).get("stance") or "swing")
        for key, row in (diplomacy.get("issue_stances") or {}).items()
    }


def stamp_rounds(st: dict, round_no: int, start: int) -> None:
    """给本轮新增的发言盖上轮流次标，前端按轮渲染。"""
    for message in (st.get("messages") or [])[start:]:
        if message.get("role") in ("player", "agent"):
            message.setdefault("round", round_no)


def risk_for(st: dict, text: str, speaker: str | None = None) -> dict:
    """按对手的触发词与红线，给玩家本轮方案一个研判等级。"""
    text = str(text or "")
    cfg = {}
    try:
        cfg = legacy.scene_ctx(st.get("scene"), speaker=speaker or st.get("speaker_key")).get("agent_cfg") or {}
    except Exception:  # noqa: BLE001
        cfg = {}
    triggers = list(((cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}) or {}).get("escalate_triggers") or []) or list(TRIGGER_FALLBACK)
    red_lines = _split_lines(cfg.get("red_lines") or "")
    red_hit = [item for item in red_lines if item and item in text]
    trigger_hit = [item for item in triggers if item and item in text]
    if red_hit:
        return {"level": "high", "label": "触及红线",
                "message": "「" + red_hit[0][:18] + "」接近对方不可交易区，强硬回应概率高",
                "basis": max(1, len(trigger_hit) + 1)}
    if trigger_hit:
        return {"level": "mid", "label": "进入敏感区",
                "message": "「" + trigger_hit[0][:18] + "」可能扩大对方审查权，建议先换对价",
                "basis": max(1, len(trigger_hit))}
    return {"level": "low", "label": "常规区", "message": "", "basis": 0}


def report_for(st: dict) -> dict:
    """结束时的复盘摘要，形状对齐 live.js 的 showSummary。"""
    view = build_view(st, "player")
    camp = view["camp"]
    deals = view["deals"]
    stats = {
        "total": len(deals),
        "confirmed": len([d for d in deals if d["status"] == "confirmed"]),
        "broken": 0,
        "expired": 0,
    }
    intel = {}
    for row in view["parties"]:
        if row["key"] == st.get("you_key"):
            continue
        item = _intel(st, row["key"], st.get("you_key"), False)
        intel[row["key"]] = {"evidence": item["evidence_count"], "accuracy": item["accuracy"]}
    return {
        "mode": view["mode"],
        "topic": view["topic"],
        "rounds": view["round"],
        "labels": {row["key"]: row["label"] for row in view["parties"]},
        "indexes": {row["key"]: _indexes(st, row["key"]) for row in view["parties"]},
        "camp": camp,
        "deal_stats": stats,
        "intel": intel,
        "tasks": copy.deepcopy((view.get("player") or {}).get("hidden_tasks") or []),
    }

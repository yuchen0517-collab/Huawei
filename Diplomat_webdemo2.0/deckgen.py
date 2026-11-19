#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按各方背景设定生成牌库：机制对称，内容非对称。

同一套结构动作（出价 / 让步 / 索价 / 威胁 / 揭露 / 试探 / 程序），
但每家的牌来自自己的底线（BATNA）、筹码（核心利益）、软肋（红线）与信息。
"""

from __future__ import annotations

import hashlib
import re

ACTION_LABEL = {
    "offer": "出价",
    "concede": "让步",
    "demand": "索价",
    "threat": "威胁",
    "disclose": "揭露",
    "probe": "试探",
    "procedure": "程序",
    "batna": "底线",
}

MODEL_BY_ACTION = {
    "offer": "条件交换博弈",
    "concede": "重复博弈 · 互惠",
    "demand": "讨价还价 · 索价",
    "threat": "承诺与威慑",
    "disclose": "信号与甄别",
    "probe": "信号与甄别",
    "procedure": "序贯博弈 · 程序",
    "batna": "承诺与威慑",
}

# 结构动作的基准数值（主体利益、国际形象、盟友信任）与费用
ACTION_BASE = {
    "offer": {"cost": 2, "deltas": (4, 1, 3)},
    "concede": {"cost": 1, "deltas": (3, 2, 5)},
    "demand": {"cost": 1, "deltas": (2, -1, -2)},
    "threat": {"cost": 2, "deltas": (3, -4, -5)},
    "disclose": {"cost": 1, "deltas": (1, 3, 1)},
    "probe": {"cost": 1, "deltas": (1, 0, 2)},
    "procedure": {"cost": 1, "deltas": (1, 2, 1)},
    "batna": {"cost": 3, "deltas": (6, -7, -9)},
}

SPEECH = {
    "offer": "我方愿在「{name}」上作出安排：{line} 作为对应，请贵方在核心条款上给出同等明确的对价。",
    "concede": "为推动「{topic}」取得进展，我方可以先在「{name}」上让一步：{line} 这不等于接受全部要求，贵方也应同步降低其他限制。",
    "demand": "我方要求贵方在「{name}」上给出明确安排：{line} 这是继续谈下去的前提，而不是可以留到以后再说的事。",
    "threat": "我方必须把话说清楚：{line} 如果这一点得不到回应，我方将重新评估参与本框架的程度。",
    "disclose": "我方可以先公开一点：{line} 把话说在前面，是为了避免各方误判。",
    "probe": "在正式表态之前，我方想问一句：{line} 答案会决定我方愿意走到哪一步。",
    "procedure": "我方动议：{line} 程序先定下来，实质问题才谈得动。",
    "batna": "我方需要提醒各位：{line} 这不是虚张声势，请各位在表决之前想清楚。",
}


def _items(text) -> list[str]:
    """把 '1. xxx 2. yyy' 或换行/分号分隔的配置拆成条目。"""
    chunks = re.split(r"(?:\s*\d+\s*[.、．:：]\s*)|[\n；;]+", str(text or ""))
    return [chunk.strip(" ．.、;；") for chunk in chunks if chunk and chunk.strip(" ．.、;；")]


def _short(text: str, limit: int = 10) -> str:
    text = re.sub(r"[（(].*?[)）]", "", str(text or "")).strip(" ，。、;；")
    text = text.replace("绝不接受", "").replace("不接受", "").strip()
    return text[:limit] if text else "核心关切"


def _goal_items(text) -> list[str]:
    """从隐藏任务里抽出可公开的信息点。"""
    out = []
    for chunk in _items(text):
        chunk = re.sub(r"^目标\s*\d*\s*[（(][^)）]*[)）]\s*[:：]?", "", chunk).strip()
        if chunk:
            out.append(chunk)
    return out


def _make_card(party: str, kind: str, index: int, name: str, line: str,
               action: str, topic: str, **extra) -> dict:
    base = ACTION_BASE.get(action, ACTION_BASE["probe"])
    card_id = party + ":" + kind + ":" + str(index)
    speech = SPEECH.get(action, SPEECH["probe"]).format(
        name=name, line=line, topic=topic)
    card = {
        "id": card_id,
        "name": name,
        "en": ACTION_LABEL.get(action, action).upper(),
        "kind": ACTION_LABEL.get(action, "动作"),
        "model": MODEL_BY_ACTION.get(action, "信号与甄别"),
        "action": action,
        "cost": int(extra.pop("cost", base["cost"])),
        "deltas": list(extra.pop("deltas", base["deltas"])),
        "rarity": extra.pop("rarity", "common"),
        "icon": extra.pop("icon", "probe"),
        "desc": extra.pop("desc", ""),
        "detail": line,
        "line": line,
        "speech": speech,
        "tags": extra.pop("tags", []),
        "target": extra.pop("target", "all" if action in ("disclose", "procedure") else "single"),
    }
    card.update(extra)
    return card


ICON_BY_ACTION = {
    "offer": "scale", "concede": "dove", "demand": "key", "threat": "bolt",
    "disclose": "seal", "probe": "compass", "procedure": "gavel", "batna": "door",
}


def _bluff_card(party: str, topic: str) -> dict:
    """0 费修饰卡：不能单独打，配合一张动作卡把宣称强度抬高 3 点。"""
    card = _make_card(
        party, "bluff", 0, "虚张声势",
        "嘴上加码：把要做的事说得比实际更硬，赌对方不敢试探。",
        "probe", topic, cost=0, deltas=(0, 0, 0), rarity="uncommon",
        icon="bolt", desc="配合一张动作卡：宣称强度 +3，可信度会下降。",
        tags=["修饰"])
    card["action"] = "bluff"
    card["kind"] = "修饰"
    card["speech"] = ""
    return card


def _deck_from_seed(party: str, seed: dict, topic: str) -> list[dict]:
    """用 agents.json 里手写的 deck 种子生成整副牌。"""
    cards: list[dict] = []
    index = 0

    batna = seed.get("batna") if isinstance(seed.get("batna"), dict) else None
    if batna:
        index += 1
        cards.append(_make_card(
            party, "batna", index, str(batna.get("name") or "摊牌"),
            str(batna.get("line") or ""), "batna", topic,
            rarity="rare", icon=ICON_BY_ACTION["batna"],
            desc="亮出替代方案，逼对方重估不谈的代价。",
            tags=["底线", "一局一次"], once=True))

    for i, chip in enumerate((seed.get("chips") or [])[:5]):
        if not isinstance(chip, dict):
            continue
        index += 1
        action = "offer" if i % 2 == 0 else "concede"
        cards.append(_make_card(
            party, "chip", index, str(chip.get("name") or "筹码")[:8],
            str(chip.get("line") or ""), action, topic,
            icon=ICON_BY_ACTION[action],
            desc=("可以让出去的实物或安排。" if action == "offer"
                  else "先让一步，换对方降低整体要求。"),
            tags=["筹码"]))

    for i, weak in enumerate((seed.get("weakness") or [])[:3]):
        if not isinstance(weak, dict):
            continue
        index += 1
        cards.append(_make_card(
            party, "weak", index, str(weak.get("name") or "软肋")[:8],
            str(weak.get("line") or ""), "disclose", topic, cost=1, icon="shield",
            desc="主动摊开软肋换收敛；也可能被对方抓住施压。",
            tags=["软肋"], weakness=True))

    for i, info in enumerate((seed.get("info") or [])[:3]):
        if not isinstance(info, dict):
            continue
        index += 1
        action = "probe" if i % 2 == 0 else "disclose"
        cards.append(_make_card(
            party, "info", index, str(info.get("name") or "信息")[:8],
            str(info.get("line") or ""), action, topic,
            icon="intel", desc="换情报或换善意；说多少由你决定。", tags=["信息"]))

    generic = [
        ("程序动议", "把争议拆成议程、顺序与时限，先解决程序。", "procedure", "gavel"),
        ("试探气球", "不承诺，先问执行主体、标准与披露范围。", "probe", "compass"),
        ("对等索价", "要求对方把口头善意变成可核查的对价。", "demand", "key"),
    ]
    for name, line, action, icon in generic:
        index += 1
        cards.append(_make_card(
            party, "util", index, name, line, action, topic, icon=icon,
            desc="标准工具牌，任何一方都有。", tags=["通用"]))

    cards.append(_bluff_card(party, topic))
    for card in cards:
        card["owner"] = party
        card["color"] = CARD_COLOR.get(card["kind"], "#c9a061")
    return cards


def build_deck(party: str, cfg: dict, topic: str, stance: dict | None = None,
               max_cards: int = 12) -> list[dict]:
    """优先用手写种子；没有种子就按人设字段自动生成。"""
    cfg = cfg or {}
    seed = cfg.get("deck")
    if isinstance(seed, dict) and (seed.get("chips") or seed.get("batna")):
        return _deck_from_seed(party, seed, topic or "本议题")
    return _build_from_profile(party, cfg, topic, stance, max_cards)


def _build_from_profile(party: str, cfg: dict, topic: str, stance: dict | None = None,
                        max_cards: int = 12) -> list[dict]:
    """从一份角色配置生成 12 张牌：1 底线 + 5 筹码 + 3 信息/软肋 + 3 通用。"""
    cfg = cfg or {}
    topic = topic or "本议题"
    stance = stance or {}
    cards: list[dict] = []
    index = 0

    # ---- 底线卡：BATNA ----
    batna = str(cfg.get("batna") or "").strip()
    if batna:
        clause = batna
        if "，" in clause:
            clause = clause.split("，", 1)[-1]
        index += 1
        cards.append(_make_card(
            party, "batna", index, "摊牌 · " + _short(batna.replace("若谈判破裂，", ""), 6),
            clause[:60], "batna", topic, rarity="rare", icon=ICON_BY_ACTION["batna"],
            desc="亮出替代方案，逼对方重估不谈的代价。",
            tags=["底线", "一局一次"], once=True))

    # ---- 筹码卡：核心利益里可以让出去的部分 ----
    interests = _items(cfg.get("core_interests_ranked"))
    coop = list((cfg.get("strategy") or {}).get("cooperate_conditions") or [])
    chips = interests[:3] + [str(item) for item in coop[:2]]
    for raw in chips[:5]:
        index += 1
        name = _short(raw, 8)
        action = "offer" if index % 2 else "concede"
        cards.append(_make_card(
            party, "chip", index, name,
            "我方在「" + _short(raw, 12) + "」上留有余地，可以谈具体数字与时限。",
            action, topic, icon=ICON_BY_ACTION[action],
            desc="手里能让的东西：换对价、换时间、换支持。",
            tags=["筹码"]))

    # ---- 软肋卡：红线被触碰时的自曝/防守 ----
    red_lines = _items(cfg.get("red_lines"))
    for raw in red_lines[:2]:
        index += 1
        name = _short(raw, 8)
        cards.append(_make_card(
            party, "weak", index, name,
            "我方提前说明：在「" + _short(raw, 12) + "」上，国内压力很大，退让空间有限。",
            "disclose", topic, cost=1, icon="shield",
            desc="主动摊开软肋，换取对方收敛；也可能被对方抓住施压。",
            tags=["软肋"], weakness=True))

    # ---- 信息卡：从隐藏任务里抽可公开的部分 ----
    goals = _goal_items(cfg.get("hidden_task_card"))
    for raw in goals[:2]:
        index += 1
        name = _short(raw, 8) or "信息"
        cards.append(_make_card(
            party, "info", index, name,
            "我方可以透露一点真实关切：" + _short(raw, 26) + "。",
            "probe" if index % 2 == 0 else "disclose", topic, icon="intel",
            desc="换情报或换善意；说多少由你决定。",
            tags=["信息"]))

    # ---- 通用牌：保证手牌有便宜的试探与程序工具 ----
    generic = [
        ("程序动议", "把争议拆成议程、顺序与时限，先解决程序。", "procedure", "gavel"),
        ("试探气球", "不承诺，先问执行主体、标准与披露范围。", "probe", "compass"),
        ("对等索价", "要求对方把口头善意变成可核查的对价。", "demand", "key"),
    ]
    for name, line, action, icon in generic:
        index += 1
        cards.append(_make_card(
            party, "util", index, name, line, action, topic, icon=icon,
            desc="标准工具牌，任何一方都有。", tags=["通用"]))

    cards.append(_bluff_card(party, topic))
    for card in cards:
        card["owner"] = party
        card["color"] = CARD_COLOR.get(card["kind"], "#c9a061")
    return cards[:max_cards]


CARD_COLOR = {
    "修饰": "#b5a0ce",
    "出价": "#86c48f", "让步": "#8fbf9d", "索价": "#c9a061", "威胁": "#d98d7c",
    "揭露": "#82a9ce", "试探": "#a997c5", "程序": "#7fb8c9", "动作": "#c9a061",
}


def deck_signature(deck: list[dict], seed: str = "") -> str:
    raw = seed + "|" + "|".join(card["id"] for card in deck)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]

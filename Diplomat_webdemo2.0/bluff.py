#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""虚张声势评估：牌是真的，话可以是假的。

结构动作由系统结算（数值只认牌面），但对外表述可以夸大或淡化。
这里只做三件事：算出「宣称强度 vs 实际强度」的偏差、检查话里有没有对应的动作语言、
再给一个可信度，供对方（和情报系统）判断要不要当真。
"""

from __future__ import annotations

ACTION_STRENGTH = {
    "batna": 10,
    "threat": 8,
    "demand": 6,
    "offer": 5,
    "concede": 4,
    "disclose": 4,
    "probe": 3,
    "procedure": 3,
}

ACTION_WORDS = {
    "threat": ("退出", "最后", "否则", "代价", "报复", "不排除", "后果", "重新评估"),
    "offer": ("提供", "可以给", "交换", "安排", "对价", "开放", "愿意拿"),
    "concede": ("让步", "接受", "下调", "放宽", "先让", "退一步"),
    "demand": ("要求", "必须", "前提", "应当", "需要贵方", "请贵方"),
    "probe": ("请问", "是否", "澄清", "说明", "确认一下", "想知道", "想问", "问一句", "由谁", "依据什么"),
    "disclose": ("透露", "公开", "可以说明", "实话说", "告诉各位"),
    "procedure": ("议程", "程序", "时限", "顺序", "动议", "表决"),
    "batna": ("退出", "不签署", "另起", "替代", "不参与", "重新评估"),
}


def _clamp(value, low, high):
    return max(low, min(high, value))


def true_action(card_actions: list[str]) -> str:
    """一副牌里最强的那个动作，作为本轮的真实结构意图。"""
    actions = [action for action in (card_actions or []) if action]
    if not actions:
        return "probe"
    return max(actions, key=lambda action: ACTION_STRENGTH.get(action, 3))


def assess(card_actions: list[str], claim: dict | None, text: str,
           record: dict | None = None) -> dict:
    """返回 bluff / deviation / credibility 三个判断。"""
    real = true_action(card_actions)
    real_strength = ACTION_STRENGTH.get(real, 3)

    claim = claim if isinstance(claim, dict) else {}
    claimed = str(claim.get("action") or "").strip().lower()
    if claimed not in ACTION_STRENGTH:
        claimed = real
    try:
        strength = int(round(float(claim.get("strength") or real_strength)))
    except (TypeError, ValueError):
        strength = real_strength
    strength = int(_clamp(strength, 1, 10))

    bluff = max(0, strength - real_strength)
    mismatch = 1 if claimed != real else 0
    words = ACTION_WORDS.get(claimed, ())
    deviation = 0 if any(word in str(text or "") for word in words) else 1

    record = record or {}
    fulfilled = int(record.get("fulfilled") or 0)
    broken = int(record.get("broken") or 0)

    credibility = (0.95
                   - 0.06 * bluff
                   - 0.15 * deviation
                   - 0.05 * mismatch
                   + 0.06 * min(2, fulfilled)
                   - 0.10 * min(2, broken))
    credibility = round(_clamp(credibility, 0.2, 0.95), 2)

    return {
        "real_action": real,
        "claimed_action": claimed,
        "real_strength": real_strength,
        "claimed_strength": strength,
        "bluff": bluff,
        "mismatch": mismatch,
        "deviation": deviation,
        "credibility": credibility,
        "exposed": credibility < 0.40,
    }


def update_record(record: dict, result: dict) -> dict:
    """按本轮表现更新履约/被识破记录。"""
    record = dict(record or {})
    if result.get("exposed"):
        record["broken"] = int(record.get("broken") or 0) + 1
    elif not result.get("bluff") and not result.get("deviation"):
        record["fulfilled"] = int(record.get("fulfilled") or 0) + 1
    return record


EXPOSED_SCALE = 0.6


def settle_scale(exposed: bool) -> float:
    """被识破时，本轮卡牌收益打折。"""
    return EXPOSED_SCALE if exposed else 1.0


def catch_chance(credibility: float, evidence: int = 0, broken: int = 0) -> float:
    """每个观察方看穿这次发言的概率。

    可信度越低越容易被看穿；手里证据多的人更容易看穿；对方历史上被识破过也会加分。
    """
    chance = (1.0 - float(credibility)) * 1.1
    chance += 0.08 * min(3, int(evidence or 0))
    chance += 0.06 * min(2, int(broken or 0))
    return round(max(0.05, min(0.95, chance)), 3)


def catch_rolls(chances: dict, seed, round_no: int, speaker: str) -> dict:
    """按 (seed, 轮次, 发言者, 观察方) 决定每一次判定，同一局可复现。"""
    import random
    out = {}
    for key, chance in (chances or {}).items():
        roll = random.Random("%s|%s|%s|%s" % (seed, round_no, speaker, key)).random()
        out[key] = roll < float(chance or 0)
    return out

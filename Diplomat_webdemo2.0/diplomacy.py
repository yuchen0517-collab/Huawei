#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import copy
import time
import uuid


STAGES = ("principle", "commitment", "allocation", "completed")
# 闭门接触要谈成"公开呼应"，双方互信至少要到这里
FOLLOW_THROUGH_TRUST = 65
# 每谈一次闭门，互信涨多少（涨太慢永远够不到门槛）
BACKCHANNEL_TRUST_GAIN = 6


def _participants(st: dict) -> list[str]:
    keys = list((st.get("party_indexes") or {}).keys())
    for key in [st.get("you_key")] + list(st.get("rivals") or []):
        if key and key not in keys:
            keys.append(key)
    return keys


def _issue_id(st: dict) -> str:
    return str((st.get("scene") or {}).get("topic_id") or st.get("topic") or "current_issue")


def _relation(trust=50, hostility=20, confidence=0.25) -> dict:
    return {
        "trust": trust,
        "hostility": hostility,
        "confidence": confidence,
        "evidence": [],
    }


def ensure_diplomacy(st: dict) -> dict:
    data = st.setdefault("diplomacy", {})
    data.setdefault("issue_id", _issue_id(st))
    data.setdefault("issue_stances", {})
    data.setdefault("relations", {})
    data.setdefault("channels", [])
    data.setdefault("proposals", [])
    data.setdefault("dark_lines", [])
    data.setdefault("signals", [])
    data.setdefault("motives", {})
    data.setdefault("last_analysis_round", 0)
    for key in _participants(st):
        data["issue_stances"].setdefault(key, {
            "stance": "swing",
            "support_score": 50,
            "confidence": 0.25,
            "evidence": [],
            "updated_round": 0,
        })
        data["relations"].setdefault(key, {})
        for other in _participants(st):
            if other != key:
                data["relations"][key].setdefault(other, _relation())
    return data


def channel_for(st: dict, channel_id: str) -> dict | None:
    data = ensure_diplomacy(st)
    return next((item for item in data["channels"] if item["id"] == channel_id), None)


def proposal_for(st: dict, proposal_id: str) -> dict | None:
    data = ensure_diplomacy(st)
    return next((item for item in data["proposals"] if item["id"] == proposal_id), None)


def open_channel(st: dict, first: str, second: str, label: str) -> dict:
    data = ensure_diplomacy(st)
    participants = [first, second]
    for channel in data["channels"]:
        if channel["participants"] == participants or channel["participants"] == list(reversed(participants)):
            if channel.get("status") != "closed":
                return channel
    channel = {
        "id": "ch-" + uuid.uuid4().hex[:10],
        "participants": participants,
        "label": label,
        "status": "open",
        "visibility": "authorized",
        "messages": [],
        "draft": {
            "our_term": "在非正式磋商中提供对等安排",
            "their_term": "在正式提案中给予对应支持",
            "status": "pending",
        },
        "created_at": time.time(),
    }
    data["channels"].append(channel)
    data["signals"].append({
        "type": "channel",
        "text": label + "沟通邀请已建立",
        "round": st.get("round", 0),
        "participants": participants,
    })
    return channel


def add_channel_message(st: dict, channel: dict, sender: str, text: str) -> dict:
    message = {
        "id": "pm-" + uuid.uuid4().hex[:8],
        "sender": sender,
        "text": text.strip(),
        "round": st.get("round", 0),
        "time": time.time(),
    }
    channel["messages"].append(message)
    channel["messages"] = channel["messages"][-30:]
    return message


def open_backchannel(st: dict, first: str, second: str, ours: str, theirs: str,
                     round_no: int, label_a: str = "", label_b: str = "") -> dict:
    """两个 NPC 之间的暗线接触：虚构记录，只在全知/参与方视角可见。"""
    data = ensure_diplomacy(st)
    channel = {
        "id": "ch-" + uuid.uuid4().hex[:10],
        "participants": [first, second],
        "label": (label_a or first) + " × " + (label_b or second),
        "status": "open",
        "visibility": [first, second],
        "fictional": True,
        "initiator": "npc",
        "messages": [],
        "draft": {"our_term": ours, "their_term": theirs, "status": "accepted"},
        "created_round": int(round_no),
        "created_at": time.time(),
    }
    data["channels"].append(channel)
    data["dark_lines"].append({
        "id": "dark-" + uuid.uuid4().hex[:8],
        "channel_id": channel["id"],
        "participants": [first, second],
        "title": "闭门接触",
        "text": ours + " ⇄ " + theirs,
        "round": int(round_no),
        "fictional": True,
    })
    data["signals"].append({
        "type": "channel",
        "text": channel["label"] + " 出现闭门接触",
        "round": int(round_no),
        "participants": [first, second],
    })
    # 闭门谈过一轮，双方互信略升（幅度小，不替代公开结算）
    relations = data["relations"]
    for source, target in ((first, second), (second, first)):
        row = relations.setdefault(source, {}).setdefault(target, _relation())
        row["trust"] = max(0, min(100, float(row.get("trust", 50)) + BACKCHANNEL_TRUST_GAIN))
        row["hostility"] = max(0, min(100, float(row.get("hostility", 20)) - 2))
        row["confidence"] = min(1.0, float(row.get("confidence", 0.25)) + 0.1)
        row.setdefault("evidence", []).append({
            "round": int(round_no),
            "text": "闭门接触后互信上升",
            "trust_delta": BACKCHANNEL_TRUST_GAIN,
        })
        row["evidence"] = row["evidence"][-6:]
    return channel


def follow_through(st: dict, round_no: int) -> list[dict]:
    """闭门接触两轮后见分晓：要么公开呼应，要么悄悄冷处理。

    这是"表里不一"的来源：谈得拢就在会场互相抬轿子，谈不拢就各自装作没发生过，
    暗线记录保留但标为失效。
    """
    data = ensure_diplomacy(st)
    out = []
    relations = data.get("relations") or {}
    stances = data.get("issue_stances") or {}
    for channel in data.get("channels") or []:
        if not channel.get("fictional") or channel.get("resolved"):
            continue
        created = int(channel.get("created_round") or 0)
        if round_no - created < 2:
            continue
        first, second = (channel.get("participants") or [])[:2]
        if not first or not second:
            continue
        trust = (float(((relations.get(first) or {}).get(second) or {}).get("trust", 50))
                 + float(((relations.get(second) or {}).get(first) or {}).get("trust", 50))) / 2
        channel["resolved"] = round_no
        if trust >= FOLLOW_THROUGH_TRUST:
            channel["draft"]["status"] = "publicized"
            data.setdefault("public_followups", []).append({
                "id": "pf-" + uuid.uuid4().hex[:8],
                "round": int(round_no),
                "participants": [first, second],
                "text": channel.get("label", "") + " 在会场公开呼应，形成议题协同",
            })
            for key in (first, second):
                row = stances.get(key)
                if isinstance(row, dict) and row.get("stance") in ("swing", "support"):
                    row["stance"] = "support"
                    row["support_score"] = max(int(row.get("support_score", 50)), 62)
                    row["confidence"] = min(1.0, float(row.get("confidence", 0.25)) + 0.1)
            for source, target in ((first, second), (second, first)):
                row = relations.setdefault(source, {}).setdefault(target, _relation())
                row["trust"] = max(0, min(100, float(row.get("trust", 50)) + 2))
                row["confidence"] = min(1.0, float(row.get("confidence", 0.25)) + 0.05)
            out.append({"channel": channel.get("id"), "result": "publicized",
                        "round": int(round_no)})
        else:
            channel["draft"]["status"] = "declined"
            data.setdefault("public_followups", []).append({
                "id": "pf-" + uuid.uuid4().hex[:8],
                "round": int(round_no),
                "participants": [first, second],
                "text": channel.get("label", "") + " 的闭门接触没有下文，双方在会场各说各话",
                "failed": True,
            })
            out.append({"channel": channel.get("id"), "result": "faded",
                        "round": int(round_no)})
    return out


def ensure_intel(st: dict) -> list[dict]:
    """情报账本：谁在什么时候看穿了谁，只有持有人知道。"""
    return st.setdefault("intel_ledger", [])


def add_intel(st: dict, *, holder: str, target: str, round_no: int, claim: str,
              real: str, credibility: float, note: str = "") -> dict:
    ledger = ensure_intel(st)
    seq = len(ledger) + 1
    entry = {
        "id": "int-%d" % seq,
        "holder": holder,
        "target": target,
        "round": int(round_no),
        "claim": claim,
        "real": real,
        "credibility": round(float(credibility), 2),
        "status": "held",
        "sold_to": [],
        "note": note or (claim + " 的说法与底牌不符"),
    }
    ledger.append(entry)
    return entry


def intel_for(st: dict, holder: str) -> list[dict]:
    return [entry for entry in ensure_intel(st) if entry.get("holder") == holder]


def intel_act(st: dict, entry: dict, action: str, buyer: str | None = None,
              party_label=None) -> dict:
    """对一条情报采取行动：留着 / 匿名施压 / 私下出售 / 公开揭穿。"""
    label = party_label or (lambda key: key)
    action = str(action or "hold").strip().lower()
    holder = entry.get("holder")
    target = entry.get("target")
    if action == "hold":
        entry["status"] = "held"
        return {"ok": True, "message": "情报留在手里，伺机而动", "entry": entry}

    if action == "hint":
        entry["status"] = "hinted"
        pressed = st.setdefault("pressed", {})
        pressed[target] = int(pressed.get(target) or 0) + 1
        return {"ok": True,
                "message": "已经放风：%s 会感到有人在盯他，但不知道是谁" % label(target),
                "entry": entry}

    if action == "sell":
        buyer = str(buyer or "").strip()
        if not buyer or buyer in (holder, target):
            return {"ok": False, "error": "出售对象无效"}
        entry["status"] = "sold"
        entry.setdefault("sold_to", []).append(buyer)
        copy = dict(entry)
        copy.update({"id": entry["id"] + "-" + buyer, "holder": buyer,
                     "status": "sold", "from": holder})
        ensure_intel(st).append(copy)
        relations = st.setdefault("diplomacy", {}).setdefault("relations", {})
        row = relations.setdefault(buyer, {}).setdefault(holder, _relation())
        row["trust"] = max(0, min(100, float(row.get("trust", 50)) + 3))
        row.setdefault("evidence", []).append({
            "round": entry.get("round"),
            "text": "接受了%s提供的情报" % label(holder),
            "trust_delta": 3,
        })
        return {"ok": True,
                "message": "情报已私下交给%s，对方在议题上欠你一次" % label(buyer),
                "entry": entry}

    if action == "expose":
        entry["status"] = "public"
        relations = st.setdefault("diplomacy", {}).setdefault("relations", {})
        for viewer in (st.get("party_indexes") or {}):
            if viewer == target:
                continue
            row = relations.setdefault(viewer, {}).setdefault(target, _relation())
            row["trust"] = max(0, min(100, float(row.get("trust", 50)) - 5))
            row.setdefault("evidence", []).append({
                "round": entry.get("round"),
                "text": "%s当众揭穿了%s的虚张声势" % (label(holder), label(target)),
                "trust_delta": -5,
            })
            row["evidence"] = row["evidence"][-6:]
        return {"ok": True, "message": "已经当众揭穿：%s 的公信力受损" % label(target),
                "entry": entry}

    return {"ok": False, "error": "未知情报动作：" + action}


def accept_channel_draft(st: dict, channel: dict) -> dict:
    channel["draft"]["status"] = "accepted"
    channel["draft"]["accepted_round"] = st.get("round", 0)
    data = ensure_diplomacy(st)
    line = {
        "id": "dark-" + uuid.uuid4().hex[:8],
        "channel_id": channel["id"],
        "participants": list(channel["participants"]),
        "title": "非正式意向已达成",
        "text": channel["label"] + "形成待公开确认意向",
        "round": st.get("round", 0),
        "fictional": True,
    }
    data["dark_lines"].append(line)
    return channel["draft"]


def create_proposal(st: dict, channel: dict | None, title: str, created_by: str,
                    stage: str = "principle") -> dict:
    data = ensure_diplomacy(st)
    if channel:
        draft = channel.get("draft") or {}
        if draft.get("status") != "accepted":
            raise ValueError("非正式意向尚未接受，不能转为公开提案")
        terms = {
            "our_term": draft.get("our_term", ""),
            "their_term": draft.get("their_term", ""),
        }
        participants = list(channel["participants"])
        channel_id = channel["id"]
    else:
        terms = {"our_term": "提出公开协调方案", "their_term": "各方评估并表决"}
        participants = [created_by]
        channel_id = None
    proposal = {
        "id": "prop-" + uuid.uuid4().hex[:10],
        "channel_id": channel_id,
        "title": title.strip() or "公开协调提案",
        "terms": terms,
        "participants": participants,
        "created_by": created_by,
        "stage": stage if stage in STAGES[:-1] else "principle",
        "status": "discussion",
        "votes": {},
        "created_round": st.get("round", 0),
        "confirmed": False,
    }
    data["proposals"].append(proposal)
    st.setdefault("messages", []).append({
        "role": "system",
        "text": "公开提案：" + proposal["title"] + " · 当前阶段 " + proposal["stage"],
    })
    return proposal


class DiplomacySettlement:
    @staticmethod
    def _clamp(value):
        return max(0, min(100, round(float(value), 1)))

    @staticmethod
    def _change_party(st: dict, key: str, interest=0, trust=0):
        current = st.setdefault("party_indexes", {}).setdefault(key, {
            "interest": 50, "image": 50, "trust": 50,
        })
        current["interest"] = DiplomacySettlement._clamp(current.get("interest", 50) + interest)
        current["trust"] = DiplomacySettlement._clamp(current.get("trust", 50) + trust)
        return current

    def confirm_proposal(self, st: dict, proposal: dict) -> None:
        if proposal.get("confirmed"):
            return
        before = {key: dict(value) for key, value in st.get("party_indexes", {}).items()}
        for key in proposal.get("participants") or []:
            self._change_party(st, key, interest=2, trust=1)
            if key == st.get("you_key"):
                st["player_indexes"] = dict(st["party_indexes"][key])
            if key == st.get("speaker_key"):
                st["agent_indexes"] = dict(st["party_indexes"][key])
            for other in proposal.get("participants") or []:
                if other == key:
                    continue
                relation = ensure_diplomacy(st)["relations"][key][other]
                relation["trust"] = self._clamp(relation["trust"] + 3)
                relation["hostility"] = self._clamp(relation["hostility"] - 2)
                relation["confidence"] = min(1, relation["confidence"] + 0.1)
        proposal["confirmed"] = True
        proposal["status"] = "confirmed"
        deltas = st.setdefault("party_delta", {})
        for key in proposal.get("participants") or []:
            current = st["party_indexes"][key]
            previous = before.get(key, {"interest": 50, "trust": 50})
            deltas[key] = {
                "interest": round(current["interest"] - previous.get("interest", 50), 1),
                "image": 0,
                "trust": round(current["trust"] - previous.get("trust", 50), 1),
            }
        st.setdefault("messages", []).append({
            "role": "system",
            "text": "公开确认生效：" + proposal["title"] + " · 已结算利益与双边信任",
        })

    def record_public_turn(self, st: dict) -> None:
        data = ensure_diplomacy(st)
        round_no = int(st.get("round") or 0)
        if round_no <= data["last_analysis_round"]:
            return
        speaker = st.get("speaker_key")
        agent_messages = [m for m in st.get("messages", []) if m.get("role") == "agent"]
        if not speaker or not agent_messages:
            return
        message = agent_messages[-1]
        text = str(message.get("text") or "")
        stance = data["issue_stances"].setdefault(speaker, {
            "stance": "swing", "support_score": 50, "confidence": 0.25,
            "evidence": [], "updated_round": 0,
        })
        old_stance = stance["stance"]
        positive = sum(text.count(word) for word in ("支持", "合作", "接受", "共识", "赞成", "愿意", "建设性"))
        negative = sum(text.count(word) for word in ("反对", "不接受", "拒绝", "不能", "红线", "保留"))

        obj = st.get("last_obj") or {}
        model_stance = obj.get("stance") if isinstance(obj.get("stance"), dict) else None
        position = str((model_stance or {}).get("position") or "").strip()
        if position in ("support", "swing", "oppose"):
            # 模型给出的立场优先；分数向立场锚点靠拢，保留历史连续性
            anchor = {"support": 72, "swing": 50, "oppose": 28}[position]
            stance["support_score"] = int(round(
                0.5 * float(stance.get("support_score", 50)) + 0.5 * anchor))
            stance["stance"] = position
            stance["confidence"] = min(1.0, float(stance.get("confidence", 0.25)) + 0.15)
            reason = str(model_stance.get("reason") or "").strip()
            conditions = model_stance.get("conditions") or []
        else:
            # 模型没给立场时的兜底：按发言里的正负词计数，力度明显弱于模型判断
            score = stance["support_score"] + min(6, positive * 2) - min(6, negative * 2)
            stance["support_score"] = max(0, min(100, score))
            stance["stance"] = "support" if score >= 65 else ("oppose" if score <= 35 else "swing")
            stance["confidence"] = min(1.0, float(stance.get("confidence", 0.25)) + 0.05)
            reason, conditions = "", []
        stance["updated_round"] = round_no
        stance["evidence"].append({
            "round": round_no,
            "type": "public_speech",
            "text": (reason or text)[:160],
            "source": "model" if position in ("support", "swing", "oppose") else "keyword",
        })
        if conditions:
            stance["conditions"] = list(conditions)[:2]
        stance["evidence"] = stance["evidence"][-8:]
        data["motives"][speaker] = {
            "summary": (st.get("last") or {}).get("summary") or "根据公开发言调整策略",
            "mood": (st.get("last") or {}).get("mood") or "",
            "round": round_no,
        }
        if old_stance != stance["stance"]:
            data["signals"].append({
                "type": "stance",
                "text": speaker + " 的公开议题立场变为 " + stance["stance"],
                "round": round_no,
                "participants": [speaker],
            })

        # 关系变化：优先用模型对本轮互动对象的判断（relations[发言方][对象]）
        assessment = obj.get("relation_assessment") if isinstance(obj.get("relation_assessment"), dict) else {}
        addressed = [key for key in (obj.get("addressed_to") or []) if key != speaker]
        moved = False
        speaker_row = data["relations"].setdefault(speaker, {})
        for target, item in assessment.items():
            if target == speaker or target not in speaker_row:
                continue
            delta = int((item or {}).get("trust_delta", 0) or 0)
            if not delta:
                continue
            relation = speaker_row[target]
            relation["trust"] = self._clamp(relation["trust"] + delta)
            relation["hostility"] = self._clamp(relation["hostility"] - delta)
            relation["confidence"] = min(1.0, float(relation.get("confidence", 0.25)) + 0.1)
            relation["evidence"].append({
                "round": round_no,
                "text": str((item or {}).get("reason") or text)[:120],
                "trust_delta": delta,
            })
            relation["evidence"] = relation["evidence"][-6:]
            moved = True

        # 被点名的对象，对发言方也会有一点反应（幅度减半），没有模型判断时才有意义
        for target in addressed:
            reaction = speaker_row.get(target) or {}
            if target not in data["relations"] or speaker not in data["relations"][target]:
                continue
            if moved and target in assessment:
                continue
            delta = 1 if positive > negative else (-1 if negative > positive else 0)
            if not delta:
                continue
            relation = data["relations"][target][speaker]
            relation["trust"] = self._clamp(relation["trust"] + delta)
            relation["hostility"] = self._clamp(relation["hostility"] - delta)
            relation["confidence"] = min(1.0, float(relation.get("confidence", 0.25)) + 0.05)
            relation["evidence"].append({"round": round_no, "text": text[:120], "trust_delta": delta})
            relation["evidence"] = relation["evidence"][-6:]

        # 模型什么都没给时的旧兜底：把变化记到「上一个发言方」身上
        if not assessment and not addressed:
            previous_speakers = [m.get("key") for m in agent_messages[:-1] if m.get("key") != speaker]
            target = previous_speakers[-1] if previous_speakers else st.get("you_key")
            if target and target != speaker and target in data["relations"]:
                relation = data["relations"][target].get(speaker)
                if relation is not None:
                    delta = 1 if positive > negative else (-1 if negative > positive else 0)
                    relation["trust"] = self._clamp(relation["trust"] + delta)
                    relation["hostility"] = self._clamp(relation["hostility"] - delta)
                    relation["confidence"] = min(1.0, relation["confidence"] + 0.06)
                    relation["evidence"].append({
                        "round": round_no,
                        "text": text[:120],
                        "trust_delta": delta,
                    })
                    relation["evidence"] = relation["evidence"][-6:]
        data["last_analysis_round"] = round_no

    @staticmethod
    def register_vote(proposal: dict, voter: str, vote: str, reason: str = "") -> None:
        if vote not in ("support", "oppose", "abstain"):
            raise ValueError("无效表决")
        proposal["votes"][voter] = {"vote": vote, "reason": reason}
        proposal["status"] = "voting"

    @staticmethod
    def finish_vote(st: dict, proposal: dict) -> dict:
        participants = _participants(st)
        votes = [proposal["votes"].get(key, {}).get("vote", "abstain") for key in participants]
        support = votes.count("support")
        oppose = votes.count("oppose")
        passed = support > len(participants) / 2
        proposal["status"] = "passed" if passed else "rejected"
        proposal["vote_summary"] = {
            "support": support,
            "oppose": oppose,
            "abstain": votes.count("abstain"),
            "total": len(participants),
        }
        if passed:
            index = STAGES.index(proposal["stage"])
            if index < len(STAGES) - 2:
                proposal["stage"] = STAGES[index + 1]
                proposal["status"] = "discussion"
                proposal["votes"] = {}
            else:
                proposal["stage"] = "completed"
        return proposal["vote_summary"]


def _intelligence_for(st: dict, viewer: str, target: str) -> dict:
    data = ensure_diplomacy(st)
    actual = (st.get("party_indexes") or {}).get(target) or {}
    center = int(actual.get("interest", 50))
    evidence = list(data["issue_stances"].get(target, {}).get("evidence") or [])
    confidence = min(0.95, 0.25 + len(evidence) * 0.1)
    radius = max(3, int(14 - confidence * 10))
    return {
        "viewer": viewer,
        "target": target,
        "interest_range": [max(0, center - radius), min(100, center + radius)],
        "confidence": round(confidence, 2),
        "evidence": evidence[-4:],
        "unknown": ["未公开底线", "未确认交换条件"],
    }


def public_diplomacy(st: dict, *, perspective: str, party: str | None) -> dict:
    data = ensure_diplomacy(st)
    observing = st.get("mode") == "observe"
    omniscient = observing and perspective == "omniscient"
    viewer = party if observing and perspective == "party" and party else st.get("you_key")
    if not viewer:
        viewer = _participants(st)[0]

    result = {
        "issue_id": data["issue_id"],
        "issue_stances": copy.deepcopy(data["issue_stances"]),
        "relations": {},
        "channels": [],
        "proposals": copy.deepcopy(data["proposals"]),
        "dark_lines": [],
        "signals": [],
        "motives": {},
        "intelligence": {},
        "perspective": "omniscient" if omniscient else ("party" if observing else "player"),
        "viewer": viewer,
    }
    for source, targets in data["relations"].items():
        for target, relation in targets.items():
            if omniscient or source == viewer or target == viewer:
                result["relations"].setdefault(source, {})[target] = copy.deepcopy(relation)
    for channel in data["channels"]:
        if omniscient or viewer in channel["participants"]:
            result["channels"].append(copy.deepcopy(channel))
    for line in data["dark_lines"]:
        if omniscient or viewer in line["participants"]:
            result["dark_lines"].append(copy.deepcopy(line))
    for signal in data["signals"][-12:]:
        if omniscient or signal.get("type") == "stance" or viewer in (signal.get("participants") or []):
            result["signals"].append(copy.deepcopy(signal))
    if omniscient:
        result["motives"] = copy.deepcopy(data["motives"])
    elif viewer in data["motives"]:
        result["motives"] = {viewer: copy.deepcopy(data["motives"][viewer])}
    for target in _participants(st):
        if target != viewer:
            result["intelligence"][target] = _intelligence_for(st, viewer, target)
    return result

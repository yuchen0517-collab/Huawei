#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import copy
import json

from neg_cli import ACTION_LABELS


def _action_parts(action: object) -> tuple[str, str]:
    if not isinstance(action, dict):
        return "未知行动", "—"
    label = ACTION_LABELS.get(action.get("action_type"))
    offer_patch = action.get("offer_patch")
    if label is None or not isinstance(offer_patch, dict):
        return "未知行动", "—"
    clauses = []
    for clause, value in offer_patch.items():
        option = value.get("option") if isinstance(value, dict) else None
        if isinstance(option, bool) or not isinstance(option, (str, int, float)) or not str(option).strip():
            option = "—"
        clauses.append(f"{clause}→{option}")
    return label, "；".join(clauses) if clauses else "—"


def _format_public_record(message: dict) -> str:
    sender = str(message.get("sender") or message.get("key") or "未知代表")
    text = str(message.get("text") or "").strip()
    if not text:
        return ""
    label, clauses = _action_parts(message.get("action"))
    return f'{sender}[{label}]：{clauses}｜发言："{text}"'


class CountryAgent:
    def __init__(self, key: str, label: str):
        self.key = key
        self.label = label
        self.private_memory: list[dict] = []
        self.turns = 0

    def _context(self, public_messages: list[dict], turn_input: str) -> str:
        transcript = []
        for message in public_messages[-36:]:
            if message.get("role") not in ("player", "agent"):
                continue
            record = _format_public_record(message)
            if record:
                transcript.append(record)

        sections = [
            "你是" + self.label + "的独立国家 Agent。以下会场记录对各方公开；"
            "你必须区分不同发言方，不要把其他国家的立场当成自己的立场。",
            "【公共会场记录】\n" + ("\n".join(transcript) if transcript else "暂无公开发言。"),
        ]
        if self.private_memory:
            memory = []
            for item in self.private_memory[-6:]:
                label, clauses = _action_parts(item.get("action"))
                memory.append(
                    "第" + str(item.get("round")) + "轮：本方[" + label + "]："
                    + clauses + "｜本方发言：" + str(item.get("public_message") or "")[:220]
                )
            sections.append("【仅你可见的私有记忆】\n" + "\n".join(memory))
        sections.append("【本轮输入】\n" + turn_input)
        return "\n\n".join(sections)

    def act(self, *, system_prompt: str, public_messages: list[dict], turn_input: str,
            call_model=None, offline_responses: list[dict] | None = None) -> dict:
        user_content = self._context(public_messages, turn_input)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        if call_model is None:
            samples = offline_responses or []
            if not samples:
                raise ValueError("离线模式没有可用的国家 Agent 回复")
            obj = json.loads(json.dumps(samples[self.turns % len(samples)]))
            raw, finish = "", "offline"
        else:
            obj, raw, finish = call_model(messages, system_prompt)
        return {
            "obj": obj,
            "raw": raw,
            "finish": finish,
            "messages": messages,
            "user_content": user_content,
        }

    def remember(self, round_no: int, obj: dict) -> None:
        if not isinstance(obj, dict) or not isinstance(obj.get("action"), dict):
            raise ValueError("记忆条目必须包含完整 action 对象")
        public_message = obj.get("public_message")
        if not isinstance(public_message, str) or not public_message.strip():
            raise ValueError("记忆条目必须包含非空 public_message")
        self.turns += 1
        self.private_memory.append({
            "round": round_no,
            "action": copy.deepcopy(obj["action"]),
            "public_message": public_message,
            "mood": str(obj.get("mood") or ""),
        })
        self.private_memory = self.private_memory[-12:]

    def public_info(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "turns": self.turns,
            "memory_count": len(self.private_memory),
        }

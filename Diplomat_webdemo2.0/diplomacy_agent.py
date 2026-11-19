#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json

from multi_agent import CountryAgent


class DiplomacyAgent(CountryAgent):
    def __init__(self, key: str, label: str):
        super().__init__(key, label)
        self.channel_memory: dict[str, list[dict]] = {}

    def act_private(self, *, system_prompt: str, channel: dict, public_messages: list[dict],
                    text: str, topic: str, call_model=None) -> dict:
        history = [
            {"sender": message.get("sender"), "text": message.get("text")}
            for message in channel.get("messages", [])[-12:]
        ]
        public_summary = [
            str(message.get("sender") or "") + "：" + str(message.get("text") or "")
            for message in public_messages[-10:]
            if message.get("role") in ("player", "agent")
        ]
        payload = {
            "议题": topic,
            "沟通规则": "非正式意向必须公开确认后才生效；不得声称已经产生秘密约束。",
            "公开会场摘要": public_summary,
            "本渠道历史": history,
            "当前草案": channel.get("draft") or {},
            "对方本轮私下发言": text,
            "本方渠道记忆": self.channel_memory.get(channel["id"], [])[-4:],
        }
        instructions = (
            system_prompt
            + "\n\n【非正式沟通】你只能使用当前渠道和公开会场中的信息。"
            "回应对方并给出可讨论的交换条件。只输出 JSON："
            '{"response":"私下回应","our_term":"你方愿提供的条件",'
            '"their_term":"你希望对方提供的条件","accept":false,'
            '"private_note":"一句内部策略摘要"}'
        )
        messages = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        if call_model is None:
            obj = {
                "response": "我方愿意继续核对交换条件，但任何意向都须进入公开文本并完成确认后才能生效。",
                "our_term": "在对等范围内提供可核查的配套安排",
                "their_term": "在正式提案中明确支持对应条款",
                "accept": False,
                "private_note": "先确认对价，再考虑公开支持",
            }
            raw, finish = "", "offline"
        else:
            obj, raw, finish = call_model(messages, instructions)
        if not isinstance(obj, dict):
            raise ValueError("私下沟通模型没有返回合法 JSON：" + str(finish))
        response = str(obj.get("response") or "").strip()
        if not response:
            raise ValueError("私下沟通没有生成有效回应")
        obj["response"] = response[:500]
        memory = {
            "round": channel.get("draft", {}).get("accepted_round") or len(history) + 1,
            "own_speech": obj["response"],
            "note": str(obj.get("private_note") or "")[:160],
        }
        self.channel_memory.setdefault(channel["id"], []).append(memory)
        self.channel_memory[channel["id"]] = self.channel_memory[channel["id"]][-12:]
        return {"obj": obj, "raw": raw, "finish": finish}

    def assess_proposal(self, *, system_prompt: str, proposal: dict, stance: dict,
                        topic: str, call_model=None) -> dict:
        payload = {
            "议题": topic,
            "提案": proposal,
            "本方当前公开立场": stance,
            "要求": "根据本方利益与红线表决，只输出 JSON："
                    '{"vote":"support|oppose|abstain","reason":"30字内理由"}',
        }
        instructions = system_prompt + "\n\n你正在独立评估一项公开提案，不得代替其他国家作出决定。"
        messages = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        if call_model is None:
            score = float(stance.get("support_score", 50))
            vote = "support" if score >= 60 else ("oppose" if score <= 35 else "abstain")
            return {
                "vote": vote,
                "reason": "根据本方当前公开立场与可接受条件作出判断",
            }
        obj, _raw, _finish = call_model(messages, instructions)
        if not isinstance(obj, dict):
            raise ValueError("表决模型没有返回合法 JSON")
        vote = str(obj.get("vote") or "abstain")
        if vote not in ("support", "oppose", "abstain"):
            vote = "abstain"
        return {"vote": vote, "reason": str(obj.get("reason") or "")[:120]}

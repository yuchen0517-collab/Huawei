#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import threading
import time


INDEX_FIELDS = ("interest", "image", "trust")
DELTA_FIELDS = ("interest_delta", "image_delta", "trust_delta")


class SettlementEngine:
    def __init__(self, model_engine):
        self.model_engine = model_engine

    @staticmethod
    def _clamp(value, low=0.0, high=100.0):
        return max(low, min(high, float(value)))

    @staticmethod
    def _copy_indexes(indexes: dict) -> dict:
        return {field: indexes.get(field, 50) for field in INDEX_FIELDS}

    @staticmethod
    def _snapshot_parties(st: dict) -> dict:
        return {
            key: dict(value)
            for key, value in (st.get("party_indexes") or {}).items()
            if isinstance(value, dict)
        }

    @staticmethod
    def _add_party_deltas(st: dict, before: dict) -> None:
        deltas = st.setdefault("party_delta", {})
        for key, current in (st.get("party_indexes") or {}).items():
            previous = before.get(key) or {field: 50 for field in INDEX_FIELDS}
            row = deltas.setdefault(key, {field: 0 for field in INDEX_FIELDS})
            for field in INDEX_FIELDS:
                row[field] = round(
                    float(row.get(field, 0)) + float(current.get(field, 50)) - float(previous.get(field, 50)),
                    1,
                )

    def apply_turn(self, st: dict, *, speaker_key: str, player_key: str,
                   speaker_indexes: dict, player_indexes: dict,
                   game_result: dict | None = None, auto: bool = False) -> None:
        parties = st.setdefault("party_indexes", {})
        before = self._snapshot_parties(st)
        st["party_delta"] = {}
        parties.setdefault(speaker_key, self._copy_indexes(speaker_indexes))

        if auto:
            current = parties[speaker_key]
            parties[speaker_key] = {
                field: round(self._clamp(
                    current.get(field, 50) + 0.72 * (
                        float(speaker_indexes.get(field, 50)) - float(current.get(field, 50))
                    ), 10, 92), 1)
                for field in INDEX_FIELDS
            }
            for key, indexes in parties.items():
                if key == speaker_key:
                    continue
                for field in INDEX_FIELDS:
                    indexes[field] = round(self._clamp(
                        float(indexes.get(field, 50)) + 0.12 * (50 - float(indexes.get(field, 50))),
                        10, 92,
                    ), 1)
            st["agent_indexes"] = self._copy_indexes(parties[speaker_key])
        else:
            if game_result:
                speaker_indexes["interest"] = game_result["agent_interest"]
                player_indexes["interest"] = game_result["player_interest"]
            st["agent_indexes"] = self._copy_indexes(speaker_indexes)
            st["player_indexes"] = self._copy_indexes(player_indexes)
            parties[speaker_key] = self._copy_indexes(speaker_indexes)
            if player_key:
                parties[player_key] = self._copy_indexes(player_indexes)
            if game_result:
                record = game_result["record"]
                st.setdefault("game_log", []).append(record)
                st["last_game"] = record
                totals = st.setdefault("payoff_total", {"player": 0, "agent": 0})
                totals["player"] += record["payoff"]["player"]
                totals["agent"] += record["payoff"]["agent"]

        self._add_party_deltas(st, before)

    def apply_event(self, st: dict, event: dict, impacts: list[dict] | None = None) -> list[dict]:
        parties = st.setdefault("party_indexes", {})
        before = self._snapshot_parties(st)

        if st.get("mode") == "observe":
            for impact in impacts or []:
                deltas = impact.get("deltas") or {}
                for key in impact.get("keys") or []:
                    current = parties.setdefault(key, {field: 50.0 for field in INDEX_FIELDS})
                    for field in INDEX_FIELDS:
                        delta = deltas.get(field, 0)
                        if delta:
                            current[field] = self._clamp(float(current.get(field, 50)) + delta)
            speaker = st.get("speaker_key")
            if speaker in parties:
                st["agent_indexes"] = self._copy_indexes(parties[speaker])
        else:
            for state_key, effect_key, party_key in (
                ("player_indexes", "player", st.get("you_key")),
                ("agent_indexes", "agent", st.get("speaker_key")),
            ):
                effects = (event.get("effects") or {}).get(effect_key) or {}
                current = st.setdefault(state_key, {field: 50 for field in INDEX_FIELDS})
                for field, delta_field in zip(INDEX_FIELDS, DELTA_FIELDS):
                    current[field] = self._clamp(
                        float(current.get(field, 50)) + int(effects.get(delta_field, 0) or 0)
                    )
                if party_key:
                    parties[party_key] = self._copy_indexes(current)

        self._add_party_deltas(st, before)
        return impacts or []

    @staticmethod
    def apply_task_results(tasks: list[dict], completed_ids) -> list[int]:
        changed = []
        for raw_id in completed_ids or []:
            try:
                index = int(raw_id)
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(tasks) and not tasks[index].get("done"):
                tasks[index]["done"] = True
                changed.append(index)
        return changed

    def judge_tasks_async(self, st: dict, user_text: str, obj: dict, ctx: dict,
                          *, prompt: str, enabled: bool) -> None:
        if not enabled or st.get("mode") == "observe":
            return
        tasks = st.get("tasks") or []
        pending = [index for index, task in enumerate(tasks) if not task.get("done")]
        if not pending:
            return
        payload = {
            "议题": st.get("topic") or "",
            "我方": ctx.get("player_label") or "",
            "对手": ctx.get("agent_label") or "",
            "本轮我方发言": user_text,
            "对手回应摘要": (obj.get("response") or "")[:300],
            "隐藏任务": [
                {"序号": index, "任务": tasks[index].get("text", ""),
                 "优先级": tasks[index].get("priority", "")}
                for index in pending
            ],
        }

        def run() -> None:
            try:
                raw, _finish = self.model_engine.call_deepseek(
                    [{"role": "system", "content": prompt},
                     {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                    json_mode=True,
                    temperature=0.2,
                )
                result = self.model_engine.extract_json(raw)
                changed = self.apply_task_results(tasks, result.get("done") or [])
                if changed:
                    st["touched"] = time.time()
                    print("  [任务] 本轮判定完成：" + "、".join(
                        task.get("text", "") for task in tasks if task.get("done")
                    ))
            except (SystemExit, Exception):
                pass

        threading.Thread(target=run, daemon=True).start()

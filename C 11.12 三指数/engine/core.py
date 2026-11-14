"""RulesEngine 门面：唯一的行动提交入口与状态导出入口。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import List, Optional, Tuple

from .indices import (
    apply_effects,
    initial_indices,
    replay_indices,
)
from .state import NegotiationState, Offer
from .terminal import (
    TERMINAL_LABELS,
    TERMINAL_TYPES,
    build_terminal,
    coverage,
    determine_terminal_type,
    evaluate,
)
from .validator import (
    OFFER_ACTIONS,
    apply_patch,
    clause_names,
    effective_plan,
    latest_offer,
    party_ids,
    redline_violations,
    validate_action,
)


def load_scenario(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


class RulesEngine:
    def __init__(self, scenario: dict, session_id: str = "demo-session"):
        self.scenario = scenario
        self.session_id = session_id

        parties = scenario.get("parties", [])
        private = {}
        if isinstance(parties, list):
            for party in parties:
                private[party["id"]] = deepcopy(party.get("private") or {})
        else:
            private = {party: {} for party in parties}

        self.state = NegotiationState(
            session_id=session_id,
            scenario_id=scenario.get("scenario_id", "unknown"),
            round=1,
            phase="opening",
            current_version=0,
            offers=[],
            agreement=None,
            open_issues=list(clause_names(scenario)),
            action_points=int(scenario.get("action_points_per_round", 3)),
            public_events=[],
            private_state_by_party=private,
            status="active",
            terminal=None,
            indices=initial_indices(scenario),
            behavior_log=[],
            seen_action_ids=[],
            rounds_without_offer=0,
            final_offer_declared_by={party: None for party in party_ids(scenario)},
        )

    # ------------------------------------------------------------------
    # 行动提交
    # ------------------------------------------------------------------
    def submit_action(
        self, action: dict
    ) -> Tuple[bool, Optional[str], str, list]:
        ok, code, message = validate_action(action, self.state, self.scenario)
        if not ok:
            return False, code, message, []

        action_type = action["action_type"]
        actor = action["actor"]
        patch = action["offer_patch"]
        base_plan = effective_plan(self.state, self.scenario)

        if action_type == "accept":
            new_plan = self._agreement_plan(actor)
        else:
            new_plan = apply_patch(base_plan, patch)

        events: List[dict] = []

        is_offer = action_type in OFFER_ACTIONS
        version = self.state.current_version + (1 if is_offer else 0)

        self.state.public_events.append(
            {
                "event_id": self.state.next_event_id(),
                "type": "action",
                "round": int(self.state.round),
                "action_id": action["action_id"],
                "actor": actor,
                "action_type": action_type,
                "card_id": action["card_id"],
                "offer_patch": deepcopy(patch),
                "conditions": deepcopy(action["conditions"]),
                "expected_effect": action["expected_effect"],
                "public_message": action["public_message"],
                "version": version,
            }
        )
        events.append(self.state.public_events[-1])

        if is_offer:
            previous = latest_offer(self.state, actor)
            clauses = deepcopy(previous.clauses) if previous else {}
            for name, entry in patch.items():
                clauses[name] = {
                    "option": entry["option"],
                    "note": entry.get("note", ""),
                }
            self.state.offers.append(
                Offer(
                    action_id=action["action_id"],
                    actor=actor,
                    version=version,
                    clauses=clauses,
                    created_round=int(self.state.round),
                    kind=action_type,
                    conditions=deepcopy(action["conditions"]),
                )
            )
            self.state.current_version = version

        if action_type == "final_offer":
            self.state.final_offer_declared_by[actor] = version
            event = {
                "event_id": self.state.next_event_id(),
                "type": "final_offer_declared",
                "round": int(self.state.round),
                "party": actor,
                "version": version,
            }
            self.state.public_events.append(event)
            events.append(event)

        effect_events, _entry = apply_effects(
            self.state,
            self.scenario,
            action,
            base_plan,
            new_plan,
        )
        events.extend(effect_events)

        self.state.action_points -= 1
        self.state.seen_action_ids.append(action["action_id"])

        if is_offer:
            self._refresh_open_issues()
            self.state.rounds_without_offer = 0

        if action_type in ("offer", "counter_offer", "conditional_exchange"):
            self.state.phase = "bargaining"
        elif action_type == "final_offer":
            self.state.phase = "closing"

        if action_type == "accept":
            self._seal_agreement(actor, action["action_id"], action["conditions"])
            covered, missing = coverage(self.state.agreement.clauses, self.scenario)
            if not missing:
                terminal_type = "FULL_AGREEMENT"
            else:
                rules = self.scenario.get("terminal_rules", {}) or {}
                # 场景禁止部分协议时不得判 PARTIAL_AGREEMENT；与
                # determine_terminal_type 保持一致改判 DEADLOCK，
                # agreement 对象保留在 state 中供审计回看。
                terminal_type = (
                    "PARTIAL_AGREEMENT"
                    if rules.get("partial_agreement_allowed", True) is not False
                    else "DEADLOCK"
                )
            terminal_event = self._record_terminal(terminal_type)
            if terminal_event:
                events.append(terminal_event)
        elif action_type == "walk_away":
            terminal_event = self._record_terminal("WITHDRAWAL")
            if terminal_event:
                events.append(terminal_event)

        return True, None, "ok", events

    # ------------------------------------------------------------------
    # 回合推进与结束
    # ------------------------------------------------------------------
    def next_round(self) -> dict:
        if self.state.status == "ended":
            return {
                "round": self.state.round,
                "phase": self.state.phase,
                "rounds_without_offer": self.state.rounds_without_offer,
                "terminal": deepcopy(self.state.terminal),
            }

        had_offer = any(
            offer.created_round == self.state.round for offer in self.state.offers
        )
        if had_offer:
            self.state.rounds_without_offer = 0
        else:
            self.state.rounds_without_offer += 1

        self.state.round += 1
        self.state.action_points = int(
            self.scenario.get("action_points_per_round", 3)
        )
        declared = any(
            value is not None
            for value in self.state.final_offer_declared_by.values()
        )
        if declared:
            self.state.phase = "closing"
        elif self.state.offers:
            self.state.phase = "bargaining"
        else:
            self.state.phase = "opening"

        self.state.public_events.append(
            {
                "event_id": self.state.next_event_id(),
                "type": "round_advanced",
                "round": int(self.state.round),
                "rounds_without_offer": self.state.rounds_without_offer,
            }
        )

        terminal_type = None
        if int(self.state.rounds_without_offer) >= int(
            self.scenario.get("deadlock_rounds", 2)
        ):
            terminal_type = "DEADLOCK"
        elif int(self.state.round) > int(self.scenario.get("max_rounds", 12)):
            terminal_type = "ROUNDS_EXHAUSTED"

        if terminal_type:
            self._record_terminal(terminal_type)

        return {
            "round": self.state.round,
            "phase": self.state.phase,
            "rounds_without_offer": self.state.rounds_without_offer,
            "terminal": deepcopy(self.state.terminal),
        }

    def finish(self, terminal_type: Optional[str] = None) -> dict:
        if self.state.status == "ended" and self.state.terminal:
            return deepcopy(self.state.terminal)

        if terminal_type is None:
            resolved = determine_terminal_type(self.state, self.scenario)
            if resolved is None:
                if self.state.offers:
                    self._seal_partial_agreement()
                    resolved = determine_terminal_type(self.state, self.scenario)
                else:
                    resolved = "DEADLOCK"
        else:
            resolved = terminal_type
            if resolved in ("FULL_AGREEMENT", "PARTIAL_AGREEMENT"):
                if self.state.agreement is None and self.state.offers:
                    self._seal_partial_agreement()

        self._record_terminal(resolved)
        return deepcopy(self.state.terminal)

    # ------------------------------------------------------------------
    # 查询与导出
    # ------------------------------------------------------------------
    def public_state(self, viewer: str = "") -> dict:
        return self.state.to_public_dict(viewer)

    def evaluate(self, viewer: str = "") -> dict:
        return evaluate(self.state, self.scenario, viewer)

    def replay(self) -> dict:
        start = initial_indices(self.scenario)
        replayed = replay_indices(self.state.public_events, start)
        return {
            "consistent": replayed == self.state.indices,
            "replayed": replayed,
            "current": deepcopy(self.state.indices),
        }

    def dump(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.state.to_archive_dict(), handle, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # 内部状态推进
    # ------------------------------------------------------------------
    def _refresh_open_issues(self) -> None:
        parties = party_ids(self.scenario)
        latest = {party: latest_offer(self.state, party) for party in parties}
        open_issues = []
        for name in clause_names(self.scenario):
            stated = [
                offer.clauses[name]["option"]
                for offer in latest.values()
                if offer and name in offer.clauses
            ]
            if not stated:
                open_issues.append(name)  # 双方都未表态
            elif len(stated) == len(parties) and any(
                option != stated[0] for option in stated[1:]
            ):
                open_issues.append(name)  # 双方都已表态但取值冲突
            # 只有一方表态：视为对方暂未反对，不列为未决
        self.state.open_issues = open_issues

    def _other_party(self, actor: str) -> Optional[str]:
        others = [party for party in party_ids(self.scenario) if party != actor]
        return others[0] if others else None

    def _agreement_plan(self, actor: str) -> dict:
        plan = effective_plan(self.state, self.scenario)
        mine = latest_offer(self.state, actor)
        counterpart = self._other_party(actor)
        theirs = latest_offer(self.state, counterpart) if counterpart else None

        if mine:
            for name, entry in mine.clauses.items():
                plan[name] = deepcopy(entry)
        if theirs:
            for name, entry in theirs.clauses.items():
                plan[name] = deepcopy(entry)
        return plan

    def _seal_agreement(self, actor: str, action_id: str, conditions: list) -> None:
        plan = self._agreement_plan(actor)
        merged_conditions: List[str] = []
        for text in list(conditions):
            if text not in merged_conditions:
                merged_conditions.append(text)

        counterpart = self._other_party(actor)
        for party in (counterpart, actor):
            offer = latest_offer(self.state, party) if party else None
            if not offer:
                continue
            for text in offer.conditions:
                if text not in merged_conditions:
                    merged_conditions.append(text)

        self.state.agreement = Offer(
            action_id=action_id,
            actor=actor,
            version=self.state.current_version,
            clauses=deepcopy(plan),
            created_round=int(self.state.round),
            kind="agreement",
            conditions=merged_conditions,
        )
        self.state.open_issues = []

    def _seal_partial_agreement(self) -> None:
        plan = effective_plan(self.state, self.scenario)
        covered = set()
        conditions: List[str] = []
        for party in party_ids(self.scenario):
            offer = latest_offer(self.state, party)
            if not offer:
                continue
            covered.update(offer.clauses.keys())
            for text in offer.conditions:
                if text not in conditions:
                    conditions.append(text)

        clauses = {name: deepcopy(plan[name]) for name in covered if name in plan}
        if not clauses:
            return

        self.state.agreement = Offer(
            action_id="finish-agreement",
            actor="",
            version=self.state.current_version,
            clauses=clauses,
            created_round=int(self.state.round),
            kind="agreement",
            conditions=conditions,
        )
        self.state.open_issues = [
            name for name in clause_names(self.scenario) if name not in clauses
        ]

    def _record_terminal(self, terminal_type: str) -> Optional[dict]:
        self.state.status = "ended"
        self.state.phase = "ended"
        terminal = build_terminal(self.state, self.scenario, terminal_type)
        self.state.terminal = terminal
        event = {
            "event_id": self.state.next_event_id(),
            "type": "terminal",
            "round": int(self.state.round),
            "terminal_type": terminal_type,
        }
        self.state.public_events.append(event)
        return event
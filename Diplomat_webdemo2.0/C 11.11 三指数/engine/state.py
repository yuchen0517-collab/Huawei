"""对局状态：全局唯一事实来源。

增量说明：新增 indices 与 behavior_log 两个字段，其余字段名保持不变。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

INDEX_NAMES = ("interest", "image", "trust")
DEFAULT_INDICES = {"interest": 50, "image": 50, "trust": 50}


@dataclass
class NegotiationState:
    session_id: str
    scenario: dict = field(default_factory=dict)
    round: int = 1
    phase: str = "opening"
    current_version: int = 0
    offers: dict = field(default_factory=dict)
    agreement: dict | None = None
    open_issues: list = field(default_factory=list)
    action_points: list = field(default_factory=list)
    public_events: list = field(default_factory=list)
    private_state_by_party: dict = field(default_factory=dict)
    status: str = "active"
    indices: dict[str, dict[str, int]] = field(default_factory=dict)
    behavior_log: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        rules = self.scenario.get("index_rules", {}) if self.scenario else {}

        if not self.offers and self.scenario.get("clauses"):
            self.offers = {
                clause["id"]: clause.get("default", clause["lo"])
                for clause in self.scenario["clauses"]
            }

        if not self.indices:
            initial = rules.get("initial", {})
            self.indices = deepcopy(initial)
        else:
            self.indices = deepcopy(self.indices)

        for party in self.scenario.get("parties", {}):
            if party not in self.indices:
                self.indices[party] = dict(DEFAULT_INDICES)
            else:
                for name in INDEX_NAMES:
                    self.indices[party].setdefault(name, DEFAULT_INDICES[name])

    def index_scale(self) -> tuple[int, int]:
        scale = (self.scenario.get("index_rules", {}) or {}).get("scale", [0, 100])
        return int(scale[0]), int(scale[1])

    def _ensure_party(self, party: str) -> dict[str, int]:
        if party not in self.indices:
            initial = (self.scenario.get("index_rules", {}) or {}).get("initial", {})
            self.indices[party] = dict(initial.get(party, DEFAULT_INDICES))
        for name in INDEX_NAMES:
            self.indices[party].setdefault(name, DEFAULT_INDICES[name])
        return self.indices[party]

    def apply_indices(
        self, deltas, reason: str, round_no: int, meta: dict | None = None
    ) -> list[dict]:
        """结算一批指数变化。

        deltas 形如 {"CN": {"image": -3}, "US": {"interest": 2}}。
        每个 (party, index) 是一条 delta，对应 public_events 里的一条事件。
        越界一律 clamp，并在事件中留下 clamped=True。
        meta 用于把发言标签（actor / action_type / magnitude）一并写进事件。
        """
        if not deltas:
            return []

        low, high = self.index_scale()
        events: list[dict] = []

        for party, changes in deltas.items():
            if not isinstance(changes, dict):
                continue
            party_indices = self._ensure_party(party)
            for index in INDEX_NAMES:
                if index not in changes:
                    continue
                delta = int(changes[index])
                before = int(party_indices[index])
                raw_after = before + delta
                after = max(low, min(high, raw_after))
                party_indices[index] = after

                event = {
                    "event_id": f"evt-{len(self.public_events) + 1:04d}",
                    "type": "index_change",
                    "round": int(round_no),
                    "party": party,
                    "index": index,
                    "delta": delta,
                    "applied_delta": after - before,
                    "before": before,
                    "after": after,
                    "clamped": after != raw_after,
                    "reason": reason,
                }
                if meta:
                    event.update(meta)
                self.public_events.append(event)
                events.append(event)

        return events

    def to_public_dict(self, viewer: str | None = None) -> dict[str, Any]:
        """公开视图：indices 是公开信息，不涉及私有底牌。"""
        data: dict[str, Any] = {
            "session_id": self.session_id,
            "round": self.round,
            "phase": self.phase,
            "current_version": self.current_version,
            "offers": deepcopy(self.offers),
            "agreement": deepcopy(self.agreement),
            "open_issues": deepcopy(self.open_issues),
            "action_points": deepcopy(self.action_points),
            "public_events": deepcopy(self.public_events),
            "indices": deepcopy(self.indices),
            "status": self.status,
        }
        if viewer is not None:
            data["private_state"] = deepcopy(
                self.private_state_by_party.get(viewer)
            )
        return data

    def to_archive_dict(self) -> dict[str, Any]:
        """存档视图：包含 behavior_log，用于回放与审计。"""
        return {
            "session_id": self.session_id,
            "round": self.round,
            "phase": self.phase,
            "current_version": self.current_version,
            "offers": deepcopy(self.offers),
            "agreement": deepcopy(self.agreement),
            "open_issues": deepcopy(self.open_issues),
            "action_points": deepcopy(self.action_points),
            "public_events": deepcopy(self.public_events),
            "private_state_by_party": deepcopy(self.private_state_by_party),
            "status": self.status,
            "indices": deepcopy(self.indices),
            "behavior_log": deepcopy(self.behavior_log),
        }
"""对局状态：全局唯一事实来源。

设计约束：
- indices 只能通过 NegotiationState.apply_index_changes() 修改；
- 每次指数变化写一条 index_change 事件，clamp 必须留痕；
- 非法行动在进入本模块前就被拒绝，不存在“先改再回滚”。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

INDEX_NAMES = ("interest", "image", "trust")
INDEX_MIN = 0
INDEX_MAX = 100


@dataclass
class Offer:
    """一版报价。clauses 存该版本明确表态的条款全量，形如 {议题名: {option, note}}。"""

    action_id: str
    actor: str
    version: int
    clauses: Dict[str, dict]
    created_round: int
    kind: str
    conditions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "actor": self.actor,
            "version": self.version,
            "clauses": deepcopy(self.clauses),
            "created_round": self.created_round,
            "kind": self.kind,
            "conditions": deepcopy(self.conditions),
        }


@dataclass
class NegotiationState:
    session_id: str
    scenario_id: str
    round: int = 1
    phase: str = "opening"
    current_version: int = 0
    offers: List[Offer] = field(default_factory=list)
    agreement: Optional[Offer] = None
    open_issues: List[str] = field(default_factory=list)
    action_points: int = 3
    public_events: List[dict] = field(default_factory=list)
    private_state_by_party: Dict[str, dict] = field(default_factory=dict)
    status: str = "active"
    terminal: Optional[dict] = None
    indices: Dict[str, Dict[str, int]] = field(default_factory=dict)
    behavior_log: List[dict] = field(default_factory=list)
    seen_action_ids: List[str] = field(default_factory=list)
    rounds_without_offer: int = 0
    final_offer_declared_by: Dict[str, Optional[int]] = field(default_factory=dict)

    def init_indices(self, values: Dict[str, Dict[str, int]]) -> None:
        """仅在构造时写入初始指数；运行期一律走 apply_index_changes。"""
        self.indices = deepcopy(values)

    def apply_index_changes(
        self,
        changes: List[Tuple[str, str, int]],
        reason: str,
        source: str,
        round_no: Optional[int] = None,
    ) -> List[dict]:
        """指数唯一写入口。

        changes 为 [(party, index_name, requested_delta), ...]。
        返回写入 public_events 的事件列表。clamp 时同时记录
        requested_delta 与实际 delta，复盘时能解释“为什么只涨了 2 分”。
        """
        events: List[dict] = []
        for party, index, requested_delta in changes:
            if party not in self.indices:
                raise KeyError(f"未知参与方：{party}")
            if index not in INDEX_NAMES:
                raise ValueError(f"未知指数：{index}")

            requested = int(requested_delta)
            before = int(self.indices[party].get(index, INDEX_MIN))
            raw_after = before + requested
            after = max(INDEX_MIN, min(INDEX_MAX, raw_after))
            self.indices[party][index] = after

            event = {
                "event_id": f"evt-{len(self.public_events) + 1:04d}",
                "type": "index_change",
                "round": int(self.round if round_no is None else round_no),
                "party": party,
                "index": index,
                "before": before,
                "after": after,
                "delta": after - before,
                "requested_delta": requested,
                "clamped": after != raw_after,
                "reason": reason,
                "source": source,
            }
            self.public_events.append(event)
            events.append(event)
        return events

    def next_event_id(self) -> str:
        return f"evt-{len(self.public_events) + 1:04d}"

    def to_public_dict(self, viewer: str = "") -> dict:
        private = {}
        if viewer and viewer in self.private_state_by_party:
            private = {viewer: deepcopy(self.private_state_by_party[viewer])}

        return {
            "session_id": self.session_id,
            "scenario_id": self.scenario_id,
            "round": self.round,
            "phase": self.phase,
            "current_version": self.current_version,
            "offers": [offer.to_dict() for offer in self.offers],
            "agreement": self.agreement.to_dict() if self.agreement else None,
            "open_issues": deepcopy(self.open_issues),
            "action_points": self.action_points,
            "public_events": deepcopy(self.public_events),
            "private_state_by_party": private,
            "status": self.status,
            "terminal": deepcopy(self.terminal),
            "indices": deepcopy(self.indices),
            "behavior_log": deepcopy(self.behavior_log),
            "rounds_without_offer": self.rounds_without_offer,
            "final_offer_declared_by": deepcopy(self.final_offer_declared_by),
        }

    def to_archive_dict(self) -> dict:
        data = self.to_public_dict("")
        data["private_state_by_party"] = deepcopy(self.private_state_by_party)
        data["seen_action_ids"] = deepcopy(self.seen_action_ids)
        return data
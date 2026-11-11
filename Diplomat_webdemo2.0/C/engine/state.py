# -*- coding: utf-8 -*-
"""谈判状态模型 —— 对应《四人分工与执行手册》2.2-B  NegotiationState

三条铁律（手册 2.1 / 2.3）：
1. 只有本模块能改 round / current_version / action_points / status；
2. 任何 Agent 输出都必须先转成 Offer，再走 commit_offer()，不得直接写字段；
3. UI 只读 to_public_dict(viewer) 的结果，不在浏览器里自己推算第二份状态。
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import copy


@dataclass
class Offer:
    """一次正式报价（一个版本）。"""
    action_id: str
    actor: str
    version: int
    clauses: Dict[str, Any]
    created_round: int
    kind: str = "offer"          # offer / counter_offer / final_offer
    conditions: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NegotiationState:
    session_id: str
    round: int = 1
    phase: str = "opening"                       # opening / bargaining / closing / ended
    current_version: int = 0
    offers: List[Offer] = field(default_factory=list)
    agreement: Optional[Offer] = None
    open_issues: List[str] = field(default_factory=list)
    action_points: int = 3
    public_events: List[dict] = field(default_factory=list)
    private_state_by_party: Dict[str, dict] = field(default_factory=dict)
    status: str = "active"                       # active / ended
    terminal: Optional[dict] = None
    rounds_without_offer: int = 0
    seen_action_ids: List[str] = field(default_factory=list)
    indices: Dict[str, Dict[str, float]] = field(default_factory=dict)   # {party: {interest, image, trust}}

    # ---------- 读 ----------

    def latest_offer(self, actor: Optional[str] = None) -> Optional[Offer]:
        for o in reversed(self.offers):
            if actor is None or o.actor == actor:
                return o
        return None

    def offer_by_version(self, version: int) -> Optional[Offer]:
        for o in self.offers:
            if o.version == version:
                return o
        return None

    def diff(self, from_version: int, to_version: int) -> Dict[str, dict]:
        """条款差距：返回 {条款: {from, to}}，只列有变化的。"""
        a, b = self.offer_by_version(from_version), self.offer_by_version(to_version)
        if not a or not b:
            return {}
        out = {}
        for k in set(a.clauses) | set(b.clauses):
            if a.clauses.get(k) != b.clauses.get(k):
                out[k] = {"from": a.clauses.get(k), "to": b.clauses.get(k)}
        return out

    def to_public_dict(self, viewer: str) -> dict:
        """给 UI 的状态快照。私有底牌只给本人，绝不外泄（手册 2.3）。"""
        d = {
            "session_id": self.session_id,
            "round": self.round,
            "phase": self.phase,
            "current_version": self.current_version,
            "latest_offer": self.latest_offer().to_dict() if self.latest_offer() else None,
            "my_latest_offer": self.latest_offer(viewer).to_dict() if self.latest_offer(viewer) else None,
            "agreement": self.agreement.to_dict() if self.agreement else None,
            "open_issues": list(self.open_issues),
            "action_points": self.action_points,
            "public_events": copy.deepcopy(self.public_events),
            "status": self.status,
            "terminal": copy.deepcopy(self.terminal),
            "indices": copy.deepcopy(self.indices),
            "private_state": copy.deepcopy(self.private_state_by_party.get(viewer, {})),
        }
        return d

    def init_indices(self, index_rules: dict) -> None:
        """按场景 index_rules.initial 初始化三指数（公开信息，UI 可读）。"""
        self.indices = copy.deepcopy(index_rules.get("initial", {}) or {})

    # ---------- 写（唯一入口）----------

    def commit_offer(self, action_id: str, actor: str, clauses: Dict[str, Any],
                     kind: str = "offer", conditions: Optional[List[dict]] = None) -> Offer:
        """提交一个新版本。调用前必须先过 validator。"""
        self.current_version += 1
        offer = Offer(
            action_id=action_id, actor=actor, version=self.current_version,
            clauses=dict(clauses), created_round=self.round,
            kind=kind, conditions=list(conditions or []),
        )
        self.offers.append(offer)
        self.seen_action_ids.append(action_id)
        self.rounds_without_offer = 0
        if kind == "final_offer":
            self.phase = "closing"
        return offer

    def accept(self, action_id: str, actor: str) -> Optional[Offer]:
        """接受对方最新版本。未决条款非空时不得调用（validator 已拦）。"""
        other = [o for o in self.offers if o.actor != actor]
        if not other:
            return None
        self.agreement = other[-1]
        self.seen_action_ids.append(action_id)
        return self.agreement

    def advance_round(self, action_points: int = 3) -> None:
        """进入下一轮。本轮没有新报价则累计僵局计数。"""
        if self.latest_offer() is None or self.latest_offer().created_round < self.round:
            self.rounds_without_offer += 1
        self.round += 1
        self.action_points = action_points
        if self.phase == "opening":
            self.phase = "bargaining"

    def close(self, terminal: dict) -> None:
        self.status = "ended"
        self.phase = "ended"
        self.terminal = terminal

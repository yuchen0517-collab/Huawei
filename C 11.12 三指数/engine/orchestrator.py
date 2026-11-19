"""谈判工作流编排：起手式 → 场景确认 → 对战回合 → 终局 → 复盘。

设计约束：
- 只读消费 `RulesEngine` 与 `TurnScheduler`，不复制 indices / offers；
- 行动写入一律经过 `RulesEngine.submit_action()`，不直接改 state；
- 状态机只推进流程，不参与规则结算；
- 复盘只走 `RulesEngine.debrief_state(requester=...)`，不自行拼装全量视图。
"""

from __future__ import annotations

from copy import deepcopy
from typing import List, Optional

from agent.audit import audit_agreement

from .scheduler import TurnScheduler

OPENING = "opening"
CONFIRMED = "confirmed"
BARGAINING = "bargaining"
TERMINAL = "terminal"
DEBRIEF = "debrief"

STATES = (OPENING, CONFIRMED, BARGAINING, TERMINAL, DEBRIEF)

ALLOWED_TRANSITIONS = {
    OPENING: (CONFIRMED,),
    CONFIRMED: (BARGAINING,),
    BARGAINING: (TERMINAL,),
    TERMINAL: (DEBRIEF,),
    DEBRIEF: (),
}


class WorkflowError(Exception):
    """工作流编排的基础异常。"""


class IllegalWorkflowTransition(WorkflowError):
    """非法状态迁移。"""


class WorkflowActionError(WorkflowError):
    """预设动作被引擎拒绝，整局无法继续。"""


class NegotiationOrchestrator:
    """把引擎的规则能力串成一条可验证的工作流。

    实例只保存流程轨迹（状态、迁移、动作日志），不保存指数、报价或协议副本；
    所有业务状态仍以 `engine.state` 为唯一事实来源。
    """

    def __init__(self, engine, scheduler: Optional[TurnScheduler] = None):
        self.engine = engine
        self.scheduler = scheduler or TurnScheduler(engine.scenario)
        self._state = OPENING
        self._transitions: List[dict] = []
        self._actions: List[dict] = []
        self._debrief: Optional[dict] = None

    @property
    def state(self) -> str:
        return self._state

    @property
    def transitions(self) -> List[dict]:
        return deepcopy(self._transitions)

    @property
    def actions(self) -> List[dict]:
        return deepcopy(self._actions)

    def _require(self, expected: str, operation: str) -> None:
        if self._state != expected:
            raise IllegalWorkflowTransition(
                f"{operation} 要求状态 {expected!r}，当前 {self._state!r}。"
            )

    def _transition(self, target: str, reason: str = "") -> None:
        allowed = ALLOWED_TRANSITIONS.get(self._state, ())
        if target not in allowed:
            raise IllegalWorkflowTransition(
                f"非法迁移：{self._state} -> {target}；允许：{list(allowed)}。"
            )
        self._transitions.append(
            {
                "from": self._state,
                "to": target,
                "round": int(self.engine.state.round),
                "reason": reason,
            }
        )
        self._state = target

    # ------------------------------------------------------------------
    # 起手式与场景确认
    # ------------------------------------------------------------------
    def confirm(self) -> dict:
        """场景确认：只读校验场景可运行，然后 opening -> confirmed。"""
        self._require(OPENING, "场景确认")
        scenario = self.engine.scenario
        parties = scenario.get("parties") or []
        clauses = scenario.get("clauses") or []
        if not parties or not clauses:
            raise WorkflowError("场景确认失败：parties / clauses 不能为空。")
        self._transition(CONFIRMED, "场景确认")
        return {
            "scenario_id": scenario.get("scenario_id"),
            "parties": [
                party["id"] if isinstance(party, dict) else party for party in parties
            ],
            "clauses": [
                clause.get("name") if isinstance(clause, dict) else clause
                for clause in clauses
            ],
        }

    def begin(self) -> dict:
        """confirmed -> bargaining，返回只读调度视图。"""
        self._require(CONFIRMED, "进入对战回合")
        self._transition(BARGAINING, "进入对战回合")
        return {
            "state": self._state,
            "round": int(self.engine.state.round),
            "order": self.scheduler.speaking_order(self.engine.state.round),
            "scheduler": self.scheduler.describe(),
        }

    # ------------------------------------------------------------------
    # 对战回合
    # ------------------------------------------------------------------
    def submit_action(self, action: dict):
        """经引擎提交行动；失败时只记录轨迹，不推进状态机。"""
        self._require(BARGAINING, "提交行动")
        ok, code, message, events = self.engine.submit_action(action)
        self._actions.append(
            {
                "round": int(self.engine.state.round),
                "action_id": action.get("action_id"),
                "actor": action.get("actor"),
                "action_type": action.get("action_type"),
                "ok": bool(ok),
                "code": code,
            }
        )
        if ok and self.engine.state.status == "ended":
            self._transition(TERMINAL, "行动触发终局")
        return ok, code, message, events

    def next_round(self) -> dict:
        """经引擎推进回合；若推进后终局则 bargaining -> terminal。"""
        self._require(BARGAINING, "推进回合")
        info = self.engine.next_round()
        if self.engine.state.status == "ended":
            self._transition(TERMINAL, "轮次推进触发终局")
        return info

    def finish(self) -> dict:
        """bargaining -> terminal，终局判定交给引擎。"""
        self._require(BARGAINING, "终局判定")
        terminal = self.engine.finish()
        self._transition(TERMINAL, "终局判定")
        return terminal

    # ------------------------------------------------------------------
    # 复盘
    # ------------------------------------------------------------------
    def debrief(self, requester: str) -> dict:
        """terminal -> debrief。

        先走 `engine.debrief_state(requester=...)` 的闸门：未终局或未显式
        授权时由引擎抛 `IllegalDebriefAccess`，编排层不复制这套判断。
        """
        data = self.engine.debrief_state(requester=requester)
        self._transition(DEBRIEF, "复盘")
        self._debrief = {
            "visibility": data.get("visibility"),
            "requester": data.get("requester"),
        }
        return data

    # ------------------------------------------------------------------
    # 整局驱动与轨迹
    # ------------------------------------------------------------------
    def run(self, rounds, requester: str = "workflow-runner") -> dict:
        """按轮次脚本跑完整局，返回 trace。

        `rounds` 形如 `[[action, ...], [action, ...]]`；每轮动作提交完后
        推进回合，最后一轮不推进。任一动作被拒绝即抛 `WorkflowActionError`。
        """
        self.confirm()
        self.begin()
        total = len(rounds)
        for index, actions in enumerate(rounds):
            for action in actions:
                ok, code, message, _ = self.submit_action(action)
                if not ok:
                    raise WorkflowActionError(
                        f"动作 {action.get('action_id')!r} 被拒绝：{code} {message}"
                    )
                if self._state != BARGAINING:
                    break
            if self._state == BARGAINING and index < total - 1:
                self.next_round()
        if self._state == BARGAINING:
            self.finish()
        if self._state == TERMINAL:
            self.debrief(requester)
        return self.build_trace()

    def build_trace(self) -> dict:
        """只读汇总：动作序列、迁移轨迹、终局、审计。不复制引擎状态。"""
        terminal = self.engine.state.terminal or {}
        audit = audit_agreement(self.engine.state, self.engine.scenario)

        rounds = []
        for round_no in sorted({item["round"] for item in self._actions}):
            rounds.append(
                {
                    "round": round_no,
                    "order": self.scheduler.speaking_order(round_no),
                    "actions": [
                        deepcopy(item)
                        for item in self._actions
                        if item["round"] == round_no
                    ],
                }
            )

        return {
            "scenario_id": self.engine.scenario.get("scenario_id"),
            "session_id": self.engine.state.session_id,
            "scheduler": self.scheduler.describe(),
            "actions": deepcopy(self._actions),
            "rounds": rounds,
            "transitions": deepcopy(self._transitions),
            "terminal": {
                "type": terminal.get("type"),
                "label": terminal.get("label"),
                "round": terminal.get("round"),
                "coverage": terminal.get("coverage"),
            },
            "audit": audit,
            "debrief": deepcopy(self._debrief),
        }
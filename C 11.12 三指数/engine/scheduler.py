"""多智能体发言调度：确定性实现。

设计约束：
- 纯标准库、无副作用、不修改 `NegotiationState`；
- 发言顺序只由 `round_no` 与 `scenario["parties"]` 的声明顺序推导，
  禁止随机、禁止依赖时间 / UUID / 网络 / LLM；
- 多边（1v5）时按 `round_no` 轮转起始位，保证每方在每个周期内
  都能轮到一次“首位发言”；
- `describe()` 只输出调度规则，不含任何 private 字段，可安全下发 UI。

本模块是成员C 的编排收口，成员A 的 `multi_agent.py` 只读调用即可，
不需要改动其内部状态。
"""

from __future__ import annotations

from typing import Dict, List, Union


class TurnScheduler:
    """回合发言顺序与行动点预算的只读计算器。"""

    def __init__(self, scenario: dict):
        self.scenario = scenario
        parties = scenario.get("parties", []) or []
        if isinstance(parties, dict):
            ids = list(parties.keys())
        else:
            ids = [
                party["id"] for party in parties if isinstance(party, dict) and party.get("id")
            ]
        # actor 统一小写（项目硬约束），这里同步归一，避免大小写差异导致
        # 调度顺序与引擎 actor 口径不一致。
        self.parties: List[str] = [str(party_id).lower() for party_id in ids]
        self.max_rounds: int = int(scenario.get("max_rounds", 12))
        raw_budget = scenario.get("action_points_per_round", 3)
        if isinstance(raw_budget, dict):
            # 预算表的键同样按 actor 小写归一，避免 "P3" / "p3" 查不到。
            self._budget: Union[int, Dict[str, int]] = {
                str(party).lower(): int(points)
                for party, points in raw_budget.items()
            }
        else:
            self._budget = int(raw_budget)

    def speaking_order(self, round_no: int) -> List[str]:
        """本回合发言顺序。

        纯确定性：第 1 回合从 parties 声明顺序的第一位开始，之后每回合
        起始位后移一位，尾部回绕到头部。两方时严格交替；
        五方（1v5）时 5 个回合构成一个完整轮转周期。
        """
        if not self.parties:
            return []
        start = (int(round_no) - 1) % len(self.parties)
        return self.parties[start:] + self.parties[:start]

    def action_budget(self, party: str, round_no: int) -> int:
        """本回合该方可用的行动点数。

        数据源严格取自 `scenario["action_points_per_round"]`：
        - 整数：所有参与方、所有回合同额；
        - 映射：按键小写查表，缺失或未知参与方返回 0（fail-closed）。

        `round_no` 保留在签名中供未来“按回合递增预算”的场景扩展；
        当前实现所有回合同额，故不参与计算。
        """
        del round_no  # 当前所有回合同额；保留参数位以便后续扩展
        budget = self._budget
        if isinstance(budget, dict):
            return int(budget.get(str(party).lower(), 0))
        return int(budget)

    def is_last_round(self, round_no: int) -> bool:
        """是否已到最后一回合（含超出 max_rounds 的情形）。"""
        return int(round_no) >= self.max_rounds

    def describe(self) -> dict:
        """供 UI / 复盘展示的调度规则摘要，不含任何 private 字段。"""
        if isinstance(self._budget, dict):
            budget_view: Union[int, Dict[str, int]] = {
                party: int(self._budget.get(party, 0)) for party in self.parties
            }
        else:
            budget_view = int(self._budget)
        return {
            "parties": list(self.parties),
            "party_count": len(self.parties),
            "max_rounds": self.max_rounds,
            "action_points_per_round": budget_view,
            "rotation": "round 1 从 parties 声明顺序首位开始，每回合起始位后移一位",
            "last_round": self.max_rounds,
        }
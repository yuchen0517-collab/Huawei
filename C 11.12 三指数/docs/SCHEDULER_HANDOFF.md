# TurnScheduler 接入交接（给成员A 的 multi_agent.py）

> 结论先说：**顺序归 `TurnScheduler`，结算归 `RulesEngine`，编排层只决定何时推进 / 终局 / 复盘。**
> 本文只给接入方式，不改 `multi_agent.py` 现有实现。

## 1. 接入位置

`multi_agent.py` 当前只有 `CountryAgent`（构造、`act`、`remember`、`public_info`），
没有回合驱动循环。建议在 **`CountryAgent` 类定义之后、文件末尾**新增一个只读辅助函数，
由 A 侧回合驱动（`neg_cli.py` 里调用 `agent.act(...)` 的那层）调用；不要把调度逻辑塞进
`CountryAgent` 内部，也不要让 Agent 自己决定下一个发言方。

可直接粘贴（8 行）：

```python
from engine.scheduler import TurnScheduler

def scheduled_order(scenario: dict, round_no: int) -> list[str]:
    """本回合发言顺序；纯只读，不修改任何状态。"""
    return TurnScheduler(scenario).speaking_order(round_no)
```

接入点对应 A 的回合循环：

```python
for round_no in range(1, scheduler.max_rounds + 1):
    for party in scheduled_order(scenario, round_no):
        agent = agents_by_party[party]
        budget = scheduler.action_budget(party, round_no)   # 只读，不扣点
        result = agent.act(...)                            # A 原有调用不变
        engine.submit_action(result["action"])             # 仍走唯一写入口
    engine.next_round()
```

## 2. 接入前后行为对比

| 维度 | 接入前 | 接入后 |
|---|---|---|
| 谁决定下一个发言方 | A 按 `agents` 列表 / 队列的固定顺序 | `TurnScheduler.speaking_order(round_no)`：第 1 回合按 `parties` 声明顺序，之后每回合起始位后移一位并回绕 |
| 两方场景 | 固定先手，容易整局同一方先说 | 严格交替：奇数轮 `cn` 先、偶数轮 `us` 先 |
| 五方（1v5） | 固定首位，轮转偏差累积 | 5 个回合构成完整轮转周期，每方都能轮到一次首位 |
| 行动点怎么扣 | 引擎每轮重置全局 `action_points`，每次 `submit_action` 扣 1 | **不变**。扣点仍在引擎内完成；`scheduler.action_budget()` 只返回场景声明的本回合预算，是只读参考值，不负责扣点、也不按方单独记账 |
| 状态来源 | A 自己维护 `round` / 队列 | 只读 `engine.state.round` 与 `scenario["parties"]`，无第二份状态 |

注意：`engine.state.action_points` 是**每轮全局预算**（`action_points_per_round`），
不是“每方各自预算”。若产品要求按方分账，需要另立规则并同步 D 的产品口径，
不能靠 `scheduler.action_budget()` 自行扣减。

## 3. 失败模式

| 失败模式 | 表现 | 建议处理 |
|---|---|---|
| scheduler 返回空 | `parties` 缺失或为空，`speaking_order()` 返回 `[]` | 不进入回合循环；直接 `engine.finish()`，由引擎判 `DEADLOCK`，并把“场景缺 parties”作为场景装配错误上报 |
| 轮次超限 | `scheduler.is_last_round(round_no)` 为真，或 `round_no > max_rounds` | 停止提交新行动，调用 `engine.finish()`；引擎按 `round > max_rounds` 判 `ROUNDS_EXHAUSTED`，不要自己伪造终局类型 |
| 某方未响应 | 该方 `act()` 超时 / 返回空 / 返回非法行动 | **不要代打、不要伪造 `actor`**。跳过该方，进入下一方；连续无报价由引擎的 `rounds_without_offer` 累计，达到 `deadlock_rounds` 后由 `next_round` 判 `DEADLOCK`。若单次 `submit_action` 返回失败码，保留错误码给 UI，继续下一位 |

补充：`submit_action` 失败发生在状态写入之前，A 侧不需要回滚；但同一 `action_id`
不要重试第二次（会被 `DUPLICATE_ACTION` 拒绝）。

## 4. 职责边界（一句话）

**编排层不接管发言顺序**：它只负责 `opening → confirmed → bargaining → terminal → debrief`
的流程推进与终局 / 复盘时序；谁先说由 `TurnScheduler` 决定，方案是否合法、指数怎么变由
`RulesEngine` 决定，三者不互相复制状态。

参考实现：`engine/orchestrator.py`（状态机与 trace）、`run_workflow.py`（端到端入口）、
`tests/test_orchestrator.py`（6 条回归，含“编排态与直接引擎态逐字段一致”的强证明）。
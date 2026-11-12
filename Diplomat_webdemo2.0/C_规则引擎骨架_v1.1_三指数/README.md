# 成员 C · 规则引擎骨架（可直接跑）

对应《DIPLOMAT 四人分工与执行手册》第五章 + 2.2-B + 12.2。  
不依赖任何第三方库，Python 3.9+ 直接跑。

## 1. 怎么验证（30 秒）

```bash
cd C_规则引擎骨架
python3 -m unittest discover -s tests -v
```

当前 12 条用例全绿：5 类终局 + 4 类非法行动 + 红线审计 + 底牌隔离。

## 2. 目录

```
engine/state.py       NegotiationState 状态模型（唯一写入口）
engine/validator.py   行动合法性校验 + 统一错误码
engine/terminal.py    五类终局判定 + 三层评价
scenarios/            示例场景（海洋法会议，数值为教学假设）
docs/                 状态示例、报价版本伪代码
tests/test_rules.py   规则回归用例
```

## 3. 三条设计立场（写进 PR 说明里）

1. **模型不许改事实。** 所有 Agent 输出先转成 `action` dict，过 `validate_action()`，再由 `commit_offer()` 落库。模型直接写 `state.round` 的路径必须删掉。
2. **非法行动不改状态。** 校验失败只返回 `error_code`，状态一字不动。D 拿错误码显示人话，不用自己编文案。
3. **结果与评价分离。** `terminal_type` 回答"怎么结束的"，`agreement_quality` 回答"这份协议好不好"。达成协议不等于成功，退出也不等于失败——退出时用 BATNA 对比来判是否理性。

## 4. 接进 v0 的四步

**第 1 步：定位写入点。** 在仓库里全局搜 `round +=`、`current_version`、`action_points`、`state[`，列出所有直接改状态的地方。这张清单就是你要收口的范围。

**第 2 步：替换写入口。** 把 `diplomacy.py` / `multi_agent.py` 里直接赋值的地方，改成调用 `commit_offer()` / `accept()` / `advance_round()` / `close()`。

**第 3 步：把 `settlement.py` 的终局逻辑迁到 `terminal.py`。** 它现在大概率是"结束就结算"，你要拆成：先判 `terminal_type`，再算 `agreement_quality`，最后留 `learning_performance` 给 D 的教练 Agent。

**第 4 步：字段对齐。** 本骨架用的是手册 2.2-B 的字段名。如果 v0 里叫别的（比如 `version` 而不是 `current_version`），先跟 A 确认以哪套为准，别两边各写一套。

## 5. 还需要你补的两件事

- **协议审计 Agent**（`agent/audit/`）：检查条款遗漏、语义冲突、模糊履约条件、双方版本一致性。骨架里已给出"遗漏条款"和"红线冲突"两项，另外两项要按真实条款文本写规则。
- **真实场景参数**：`scenarios/demo_scenario.json` 里的 ideal / redline / batna 是教学假设值，等 B 出主场景 JSON 后替换，别自己拍。

## 6. 给 A 和 D 的接口

```python
from engine.validator import validate_action, ERRORS
from engine.state import NegotiationState
from engine.terminal import check_terminal, evaluate

ok, code, msg = validate_action(state, action, scenario)
if not ok:
    return {"ok": False, "error_code": code, "message": msg}   # D 直接用

snapshot = state.to_public_dict(viewer="CN")                    # 只给本人私有状态
terminal = check_terminal(state, scenario, last_action)
```

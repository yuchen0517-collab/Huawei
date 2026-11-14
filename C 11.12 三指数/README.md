# 外交谈判模拟器 · 规则引擎 + 协议审计 + 场景适配（v2）

本模块是系统中**唯一可以修改谈判状态**的部分。模型可以自由生成发言，
但不能自由生成数值；所有结算可复现、可审计，非法行动不改变状态。

## 1. 跑起来

```bash
python -m unittest discover -s tests -t .
python demo.py
```

第一条命令运行 129 条单元测试；第二条跑完一局完整谈判，打印每步状态与
`AGREEMENT_HAS_OPEN_ISSUES`、`FINAL_OFFER_LOCKED` 的真实拦截，并把真实
结果写入 `docs/state.example.json` 与 `docs/evaluation.example.json`。

## 2. 目录说明

```
engine/
  __init__.py   只暴露 RulesEngine / load_scenario / TERMINAL_TYPES / TERMINAL_LABELS
  state.py      NegotiationState、Offer、指数唯一写入口
  validator.py  JSON Schema 校验、18 类错误码、final_offer 规则、硬/软红线判定
  indices.py    score / closeness / utility / interest / 查表 / clamp / replay
  terminal.py   五类终局 + 六字段评价（batna_comparison 支持 viewer 裁剪）
  core.py       RulesEngine 门面（phase 状态机）
adapter/
  __init__.py
  scenario_adapter.py  成员B 契约 → 引擎场景；全项目唯一的 B→C 转换实现
load_scenario_bridge.py  成员A 场景入口的兼容桥（is_b_scenario / convert_b_scenario /
                         load_scenario / make_scenario），convert 直接委托适配层
agents.json               ai_governance 场景的 C 侧精简数据源（字段名与 A 侧一致）
agent/
  audit/
    auditor.py  协议审计五项检查（只出意见，不改协议）
scenarios/
  demo_scenario.json         AI 治理双边场景：3 条款（2 枚举 + 1 数值）
  from_b_chip_controls.json  成员B 契约样例：芯片出口管制（3 议题，带 BOM）
tests/
  test_schema.py       14 条 schema 校验
  test_final_offer.py  13 条 final_offer 拦截
  test_rules.py        23 条行动/终局（含取值冲突、phase 转移回归）
  test_indices.py      19 条三指数
  test_audit.py        10 条协议审计
  test_adapter.py      29 条场景契约适配（映射/效用/红线/端到端/信息隔离）
  test_bridge.py       21 条桥接（双实现统一/入口回落/BOM/隔离/占位分数防回归）
docs/
  index_rules.md        三指数口径
  action_schema.md      行动结构逐字段说明
  final_offer.md        最后报价拦截规则
  offer_version.md      版本、accept 检查、红线方向
  scenario_adapter.md   场景契约适配：字段映射、红线、warning、与 A 的关系
  state.example.json / evaluation.example.json（由 demo.py 真实生成）
demo.py
INTEGRATION_NOTES.md    2026-11-14 适配层归位与引擎能力合并的决策记录
```

## 3. 怎么接

### 成员A（编排层 / 多 Agent 调度）

三种场景来源，统一走同一个入口：

```python
from load_scenario_bridge import load_scenario, make_scenario

engine = RulesEngine(load_scenario(scenario_path), session_id=session_id)
# scenario_path 为 None 时回落 make_scenario()（agents.json → ai_governance）
# scenario_path 指向 B 契约文件时自动识别并委托 adapter.adapt_scenario
```

若 A 侧仍保留自己的 `load_scenario.py`，把它改成 3 行转发即可，`api.py` 一行不用动：

```python
import sys
from pathlib import Path

_engine = Path(__file__).resolve().parent / "C 11.12 三指数"
if str(_engine) not in sys.path:
    sys.path.insert(0, str(_engine))

from load_scenario_bridge import ENGINE_ROOT, load_scenario, make_scenario  # noqa: F401,E402
```

```python
ok, code, message, events = engine.submit_action(action)
if not ok:
    # code 是 18 类错误码之一；message 可直接展示给前端
    ...
view = engine.public_state(viewer="cn")        # 按观察者过滤私有底牌
evaluation = engine.evaluate(viewer="cn")      # 对外展示必须传 viewer
```

- `action` 必须逐字符合 `docs/action_schema.md` 的 JSON Schema。
- `events` 是本次新增的事件列表，可增量推给前端。
- `engine.next_round()` 推进回合；`engine.finish()` 手动结束。
- `engine.evaluate()` 不传 `viewer` 只用于复盘 / 审计 / demo；给玩家看的评价必须传己方 party_id。

### 成员B（场景契约）

B 只出题材与立场（`urn:diplomat:schema:scenario:1.0`），不承担结算参数：

```python
from adapter import load_and_adapt, validate_b_contract

errors = validate_b_contract(b_dict)            # 不抛异常，逐条带 $.字段路径
scenario, warnings = load_and_adapt("b_scenario.json")
# warnings 全是 {"code", "field", "message"} 结构；可原样下发给 B 做补数据清单
```

契约中缺失的 `index_rules`、`initial`、`deadlock_rounds`、
`action_points_per_round` 由适配层补默认值并输出结构化 warning。
字段映射、红线方向与已知限制见 `docs/scenario_adapter.md`。

### 成员D（学习评价 / 观战页）

```python
evaluation = engine.evaluate()
# terminal_type / agreement_quality / batna_comparison /
# redline_check / learning_performance(None) / evidence_links
```

`learning_performance` 恒为 `None`，归成员D 填充。
`evidence_links` 是 `public_events` 的下标列表，观战页可据此回点。

### 协议审计

```python
from agent.audit import audit_agreement

result = audit_agreement(engine.state, engine.scenario)
# {"ok": bool, "issues": [...], "summary": {"blocking": n, "warning": n}}
```

审计只读，不提供任何“帮我改成合法版本”的接口。

## 4. 硬约束

| 约束 | 落实方式 |
|---|---|
| 只用标准库 | 无第三方依赖；schema 校验手写，不引入 `jsonschema` |
| 禁用随机/时间/UUID/网络/LLM | 结算路径零调用；`replay` 只重放事件 |
| 模型只出离散标签 | 无 `effect_labels` 时按固定表 + patch 幅度推导 |
| 非法行动不改状态 | 全部校验与计算先完成，再统一写入 |
| 指数唯一写入口 | `NegotiationState.apply_index_changes()` |
| clamp 留痕 | 事件含 `before/after/delta/requested_delta/clamped/source` |
| 可回放 | `replay_indices()` 纯函数，`RulesEngine.replay()` 对账 |
| actor 统一小写 | 场景、测试、demo 全部使用 `cn` / `us` |
| 条款键唯一 | 以 `clauses[].name` 为键，适配层重复即抛 `ScenarioContractError` |
| 私有底牌隔离 | `public_state(viewer)` 只返回该方 `private`；`batna_comparison` 支持 viewer 裁剪 |

## 5. 错误码

规范正文写“16 个”，但表格实际列出 17 个字符串；加上适配层新增的
`WALK_AWAY_FORBIDDEN`，本实现共 18 个：

| 错误码 | 触发条件 |
|---|---|
| `SCHEMA_VIOLATION` | 缺字段、多字段、类型错（message 写明字段） |
| `UNKNOWN_ACTION_TYPE` | 不在 9 个 action_type 枚举内 |
| `PATCH_NOT_ALLOWED` | 非报价类行动带非空 `offer_patch` |
| `PHASE_CLOSED` | 谈判已结束仍提交行动 |
| `DUPLICATE_ACTION` | `action_id` 已生效过 |
| `VERSION_CONFLICT` | 状态版本内部不一致（schema 暂无 base_version） |
| `AGREEMENT_HAS_OPEN_ISSUES` | 还有未决条款就 accept |
| `NO_COUNTERPART_OFFER` | 对方还没报价就 accept |
| `ACTION_POINTS_INSUFFICIENT` | 行动点用完 |
| `UNKNOWN_CLAUSE` | 引用不存在的条款 |
| `UNKNOWN_OPTION` | 枚举条款取值不在 options 内 |
| `TERM_LOCKED` | 条款已锁定 |
| `VALUE_OUT_OF_RANGE` | 数值条款超出 range |
| `REDLINE_VIOLATION` | 方案触碰硬红线 |
| `FINAL_OFFER_ALREADY_DECLARED` | 再次声明最后报价 |
| `FINAL_OFFER_LOCKED` | 声明后仍想改条款 |
| `FINAL_OFFER_EMPTY` | 最后报价没带条款 |
| `WALK_AWAY_FORBIDDEN` | 场景 `terminal_rules.allow_walk_away=false` 时尝试退出 |

校验顺序固定：
`schema → action_type → phase → 幂等 → 版本 → final_offer 三条规则 →
accept 未决检查 → walk_away 开关 → 行动点 → 条款/取值/范围 → 红线`。

## 6. 场景级开关（`terminal_rules`）

| 字段 | 缺省 | 作用 |
|---|---|---|
| `allow_walk_away` | `true` | `false` 时 `walk_away` 返回 `WALK_AWAY_FORBIDDEN`，状态零推进 |
| `accept_requires_no_open_issues` | `true` | `false` 时跳过 `AGREEMENT_HAS_OPEN_ISSUES` 拦截 |
| `partial_agreement_allowed` | `true` | `false` 时部分协议判 `DEADLOCK`（不判 `PARTIAL_AGREEMENT`） |

未声明 `terminal_rules` 的场景（如 `demo_scenario.json`）三个开关全部按缺省值，
行为与 v2 完全一致。

## 7. 调参入口

| 想改什么 | 改哪里 | 需要改代码？ |
|---|---|---|
| 条款范围、初始值、理想点、红线、权重 | `scenarios/*.json` 的 `clauses` | 否 |
| 枚举选项及双方得分 | `clauses[].options[].score` | 否 |
| 指数初值、敏感度、行为查表 | `index_rules` | 否 |
| 轮次上限、僵局轮数、每轮行动点 | `max_rounds` / `deadlock_rounds` / `action_points_per_round` | 否 |
| 场景终局开关 | `terminal_rules` | 否 |
| 各方 BATNA | `parties[].batna` | 否 |
| 私有底牌 | `parties[].private` | 否 |
| ai_governance 的双方偏好分 | `load_scenario_bridge.py` 的 `_ENUM_CLAUSES` / `_NUMERIC_CLAUSES` | 是 |
| 模糊词表、可核验动词表 | `agent/audit/auditor.py` 常量 | 是 |
| 路径2 幅度阈值 0.15 / 0.45 | `engine/indices.py` | 是 |

## 8. 待 A 确认

1. **`effect_labels` 字段**：A 已于 2026-11-13 在 `action_schema.json` 加为可选字段
   （不进 required）并全链路透传，此项已闭环。
2. **`conditions` 是纯文本**：审计只能做模糊词与可核查性检查，做不了结构化
   语义冲突检测。若后续要检查“条件与条款矛盾”，`conditions` 需改成
   `{clause, op, value, text}` 的结构化数组。
3. **缺少 `base_version` / `target_version`**：schema 的 `additionalProperties:
   false` 不允许客户端携带版本基准，`VERSION_CONFLICT` 目前只能做状态内部
   一致性检查。若要在协议层严格拒绝“基于旧版本报价”，需要新增可选版本字段
   （或允许引擎接受 `accept` 的 `target_version`）。
4. **`load_scenario.py` 改为转发 `load_scenario_bridge`**：我方已提供同名同签名入口，
   A 侧只需替换 import；细节见 `INTEGRATION_NOTES.md` 与 `docs/scenario_adapter.md` 第 8 节。

## 9. 还没做的下一步

- 协议审计接入编排层：`accept` 前自动跑一次审计，blocking 时提示但不代改。
- 多方（>2）扩展：`party_ids` 与“对方”选择当前按双边硬编码。
- 事件流持久化与跨进程回放：目前 `dump()` 只导出状态，事件流已在
  `public_events` 中，可直接作为回放输入。
- 观战页的 `final_offer_declared_by` 徽标与 `public_message` 渲染。
- 隐藏任务卡信息隔离的对抗测试（套话 / 长对话漂移 / 接口字段泄露三类攻击）。
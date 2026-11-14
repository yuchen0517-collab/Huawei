# 场景契约适配层（B → C）

## 1. 定位

成员B 的场景编译 Agent 输出 `urn:diplomat:schema:scenario:1.0`，成员C 的规则引擎
只认自己的 `scenarios/demo_scenario.json` 格式。本适配层是两者之间**单向只读**的
翻译层：

- 不改 B 的契约字段名，不改 B 的 JSON Schema；
- 不改引擎核心逻辑，只补了三个向后兼容的可选开关；
- 适配过程零随机、零时间、零网络、零 LLM，同一输入永远得到同一输出。

```
B 场景 JSON ──(utf-8-sig 读取)──> validate_b_contract
                                        │
                          ┌─────────────┴─────────────┐
                          │                           │
                   错误列表非空                    warnings
                          │                           │
                 ScenarioContractError        结构化 dict（code/field/message）
                          │                           │
                          └────> adapt_scenario ──────┘
                                        │
                                  C 场景 dict
                                        │
                                  RulesEngine
```

## 2. 用法

### 示例 1：从文件加载并启动引擎

```python
from adapter import load_and_adapt
from engine import RulesEngine

scenario, warnings = load_and_adapt("scenarios/from_b_chip_controls.json")
# warnings 是 [{"code": "...", "field": "...", "message": "..."}, ...]
engine = RulesEngine(scenario, session_id="session-001")
print(engine.state.phase, engine.state.indices)
```

### 示例 2：只校验契约，不适配

```python
from adapter import validate_b_contract

errors = validate_b_contract(b_scenario_dict)   # 不抛异常
if errors:
    print("\n".join(errors))                    # 每条都带 $.字段路径
```

### 示例 3：内存对象直接适配

```python
from adapter import adapt_scenario, ScenarioContractError

try:
    scenario = adapt_scenario(b_scenario_dict)
except ScenarioContractError as exc:
    # 消息形如：$.terminal_rules: 缺少必填字段。；$.issues[0].type: 期望 numeric/enumerated 之一
    raise
```

## 3. 字段映射表（以引擎实际实现为准）

| # | B 侧 | C 侧 | 规则 |
|---|---|---|---|
| 1 | `parties[].party_id` | `parties[].id` | 直传并强制小写 |
| 2 | `parties[].name` | `parties[].name` | 直传 |
| 3 | `parties[].role_label` | `parties[].role` | 直传 |
| 4 | `parties[].public_position` | `parties[].public_position` | 直传，引擎忽略但保留 |
| 5 | `private_state_by_party[p].batna.utility` | `parties[].batna` | 取数值；缺失置 `null` 并 warning |
| 6 | `batna.description` / `batna.basis` | `parties[].private.batna_note` | 以 `；` 连接 |
| 7 | `hidden_task` | `parties[].private.bottom_line` | 只经 `public_state(viewer)` 分片可见 |
| 8 | `priority_ranking` | `parties[].private.priority_ranking` | 只经 `public_state(viewer)` 分片可见 |
| 9 | `issues[]` | `clauses[]` | 逐条翻译 |
| 10 | `issues[].issue_id` | `clauses[].issue_id` | 直传备查 |
| 11 | `issues[].name` | `clauses[].name` | 直传；引擎以 `name` 为键，重复即报错 |
| 12 | `issues[].type` | `clauses[].type` | `enumerated → enum`，`numeric → numeric` |
| 13 | `issues[].unit` | `clauses[].unit` | 直传，引擎忽略但保留 |
| 14 | `issues[].range{min,max,step}` | `clauses[].range[min,max]` + `clauses[].step` | 引擎 `range` 是二元数组，`step` 单独保留 |
| 15 | `issues[].options[].option_id` | `clauses[].options[].id` | 直传 |
| 16 | `options[].label` / `order` | `options[].label` / `order` | 直传 |
| 17 | `goals[].weight` | `clauses[].weights[p]` | 按 `issue_id` 回填；按参与方分别归一化 |
| 18 | `goals[].target + direction` | `options[].score[p]` 或 `positions[p].ideal` | 见第 4 节 |
| 19 | `redlines[]` | `redlines[p]` / `positions[p].redline` | 见第 5 节 |
| 20 | `assumptions[].text` | `assumptions[]` | 转为字符串数组，保留 `[assumption_id]` 前缀 |
| 21 | `max_rounds` | `max_rounds` | 直传 |
| 22 | `terminal_rules.allow_walk_away` | `terminal_rules.allow_walk_away` | `false` 时引擎返回 `WALK_AWAY_FORBIDDEN` |
| 23 | `terminal_rules.accept_requires_no_open_issue` | `terminal_rules.accept_requires_no_open_issues` | 注意单复数差异 |
| 24 | `terminal_rules.partial_agreement_allowed` | `terminal_rules.partial_agreement_allowed` | `false` 时部分协议判 `DEADLOCK` |
| 25 | `scenario_type` | `scenario_type` | `assumption → hypothesis` 并 warning |
| 26 | `public_facts` | `public_facts` | 直传保留，引擎不用 |
| 27 | — | `deadlock_rounds` | 默认 `2` |
| 28 | — | `action_points_per_round` | 默认 `3` |
| 29 | — | `clauses[].initial` | 枚举取 `order` 最小项，数值取 `range.min`，并 warning |
| 30 | —（可选 `index_rules`，上游组装层可补） | `index_rules` | 输入自带则原样保留；否则注入 `demo_scenario.json` 同口径默认表并 warning |
| 31 | — | `allow_accept_with_open_issues` | 由第 23 条取反得到 |

> 说明：任务书里写的是 `clauses[].targets[p].ideal`，但引擎 `validator.py` /
> `indices.py` 实际读取的是 `clauses[].positions[p].ideal` 与
> `clauses[].positions[p].redline`。适配层按**代码实际契约**输出，文档以此为准。

## 4. 效用分推导

### 数值条款

- `higher_better`：`ideal = target`，分数仍由引擎 `closeness()` 按
  `1 - |value - ideal| / (max - min)` 计算，理想点 1.0。
- `lower_better`：`ideal = target`，引擎同一公式自然表现为“越接近 target 越高分”。

适配层只负责把 `target` 写入 `positions[p].ideal`，不在场景里预存所有取值的分数。

### 枚举条款（ranked）

按 `order` 位次计算，`target` 为 1.0，步长 `1 / (n - 1)`，最低 0.0：

| options（order） | target | 分数 |
|---|---|---|
| wto(1) / bilateral(2) / unilateral(3) | wto | 1.0 / 0.5 / 0.0 |
| wto(1) / bilateral(2) / unilateral(3) | bilateral | 0.5 / 1.0 / 0.5 |

每方各自用自己的 `target` 计算，互不共用分数；`parties` 数组顺序不影响结果。

## 5. 红线映射

| B 侧 | 条款类型 | C 侧输出 |
|---|---|---|
| `op: "in", value: [允许集合]` | 枚举 | `redlines[p] = 不在允许集合里的 option_id` |
| `op: "not_in", value: [...]` | 枚举 | `redlines[p] = value` 中存在的 option_id |
| `op: "min", value: X` | 数值 | `positions[p].redline = X`，`redline_direction = below_is_violation` |
| `op: "max", value: X` | 数值 | `positions[p].redline = X`，`redline_direction = above_is_violation` |
| `hard: false` | 枚举 | 写入 `clauses[].soft_redlines[p]` |
| `hard: false` | 数值 | `positions[p].soft = true` |

无红线时**不写 `redline` 键**（不填 ideal 占位），引擎按“缺键即无红线”处理。

软红线不阻断行动：`validate_action` 只用硬红线拒绝；软红线通过
`engine.validator.soft_redline_violations(plan, scenario)` 返回 warning 清单。

`redline_direction` 是可选字段。不传时 `is_redline_violation()` 仍走 v2 原有的
“由 `ideal` 与 `redline` 大小关系隐式判方向”逻辑，79 条旧测试与 demo 行为不变。

## 6. warning 代码

| code | 触发条件 |
|---|---|
| `SCENARIO_TYPE_NORMALIZED` | `scenario_type=assumption` 归一化为 `hypothesis` |
| `INITIAL_DERIVED` | 每条条款的初始值由适配层推导 |
| `DEFAULT_INDEX_RULES` | B 契约无 `index_rules`，注入默认查表 |
| `INDEX_RULES_PRESERVED` | 输入场景已自带 `index_rules`，适配层原样保留 |
| `WEIGHT_NORMALIZED` | 某方权重和在 [0.99, 1.01] 之外，已按比例归一化 |
| `GOAL_MISSING` | 某方对某议题没有 goal，效用分按 0 |
| `BATNA_MISSING` | `batna.utility` 缺失或非数值 |
| `HIDDEN_TASK_MISSING` | `hidden_task` 缺失，`bottom_line` 置空 |
| `PRIORITY_RANKING_MISSING` | `priority_ranking` 缺失，置空数组 |
| `MULTIPLE_NUMERIC_REDLINES` | 同一方对同一数值议题给了多条红线，引擎单槽位只留一条 |

## 7. 已知限制（需与 B 对齐）

1. **B 契约没有 `index_rules`**：上游组装层（成员A）现在会借用
   `scenarios/demo_scenario.json` 的整张结算表并随场景传入，适配层检测到该字段后
   **原样保留**；只有输入完全没带时才注入默认表并 warning。
   **结算表的唯一源头是 `demo_scenario.json`**，改表时必须通知 A 同步；
   `tests/test_adapter.py::test_default_index_rules_matches_demo_scenario` 会守卫
   默认常量与 demo 表一致。
2. **B 契约没有 `initial`**：当前初始方案由 `order` 最小值 / `range.min` 推导，
   可能让初始 Interest 偏离剧情设定。建议 B 增加 `initial_option` / `initial_value`。
3. **B 契约没有 `deadlock_rounds` 与 `action_points_per_round`**：固定为 2 与 3，
   无法按场景调节节奏。
4. **数值红线单槽位**：现有引擎每个数值条款每方只有一个 `redline`。若 B 同方同时给出
   `min` 与 `max` 两条硬红线（区间约束），适配层只保留第一条并记 warning。
5. **`step` 不参与校验**：引擎只校验 `range[0] <= value <= range[1]`，不检查取值是否是
   `step` 的整数倍。B 若依赖步长离散化，需要引擎侧另行补校验。
6. **枚举 `direction` 只能是 `ranked`**：B 若给枚举议题写 `higher_better`，适配层直接报
   契约错误，不猜测语义。
7. **`negotiability` 未消费**：它是编译器回填的只读审计字段，适配层忽略，不进入 C 场景。
8. **多参与方**：引擎的 `accept` 只找“第一个对方”，当前按双边设计；三方及以上会退化。
9. **`partial_agreement_allowed=false`** 的实现方式：`accept` 时由 validator 拒绝未全覆盖的
   协议；`finish()` 自动封存部分协议后由 `determine_terminal_type` 判为 `DEADLOCK`
   （协议对象仍留在 state 中供审计回看）。

## 8. 与成员A `load_scenario.py` 的关系

本目录归位后（2026-11-14，从 `Diplomat_webdemo2.0/C 11.11 三指数/` 移到
`C 11.12 三指数/`），**全项目只有一套 B→C 场景转换实现**，即本文件。

成员A 侧原先自行实现了一套 `convert_b_scenario()`（含
`_convert_numeric` / `_convert_enumerated` / `_weights` / `_goal` / `_hard_redline`），
与本适配层功能重复，且存在以下实质性缺陷（均已由本适配层正确实现）：

| 缺陷 | A 侧旧实现 | 本适配层 |
|---|---|---|
| 枚举效用分不看 `goals[].target` | 按 `parties[0]/parties[1]` 数组顺序硬编码 | 每方以自己 `target` 为 1.0、按 `order` 位次线性衰减 |
| 无红线时 `redline = ideal` | 红线恒不触发 | 不写 `redline` 键 |
| 丢弃 `op: min/max` | 靠 ideal/redline 大小猜方向 | 输出 `redline_direction` 显式方向 |
| 丢弃 `op: not_in` | 只认 `in` | `in` / `not_in` 都映射 |
| `hard` 缺省视为非红线 | 漏掉未显式声明 `hard` 的红线 | `hard` 缺省按硬红线处理 |
| 权重不归一化 | 权重和不为 1 时 Interest 失真 | 按参与方归一化并 warning |
| `terminal_rules` 只映射一个字段 | 丢 `allow_walk_away` / `partial_agreement_allowed` | 三个字段全部映射 |
| `initial` 取极端值且不告警 | 开局 Interest 偏低且无提示 | 推导并输出 `INITIAL_DERIVED` warning |
| `assumptions` 丢 `assumption_id` | 只留 `text` | 保留 `[A1] ` 前缀 |

### A 侧接入方式（唯一改动点）

```python
# 旧：from load_scenario import ENGINE_ROOT, load_scenario, make_scenario
from load_scenario_bridge import ENGINE_ROOT, load_scenario, make_scenario
```

`load_scenario_bridge.py` 提供与 A 原模块**同名同签名**的四个入口：

| 入口 | 行为 |
|---|---|
| `is_b_scenario(data)` | 判断是否为 B 契约格式 |
| `convert_b_scenario(data)` | 直接委托 `adapter.adapt_scenario`，不再自行映射字段 |
| `load_scenario(path=None)` | `path=None` 回落 `make_scenario()`；否则读文件（utf-8-sig）并自动识别 B/C |
| `make_scenario(agents_path=None)` | 保留 A 的 `agents.json → ai_governance` 组装逻辑 |

`ENGINE_ROOT` 也一并导出，`api.py` 依赖它做 `sys.path` 注入，无需改动。
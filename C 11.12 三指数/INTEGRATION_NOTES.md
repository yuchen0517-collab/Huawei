# 集成说明 · 2026-11-14 适配层归位

## 1. 为什么要做这次归位

2026-11-13 完成的场景契约适配层写在了 `Diplomat_webdemo2.0/C 11.11 三指数/`，
但成员A 的 `api.py` 真正接入的是 `Huawei/C 11.12 三指数/`
（`load_scenario.py` 里硬编码 `ENGINE_DIR_NAME = "C 11.12 三指数"`），
导致 108 条测试全绿却**一行运行时都没被调用**。

同时 A 侧自行维护了一套 `convert_b_scenario()`，功能与适配层重复且存在实质性缺陷，
形成“两套 B→C 语义、一套在跑”的分叉。

本次目标：**全项目只有一套 B→C 场景转换实现**，且不把 11.12 的新引擎能力回退成 11.11。

## 2. 关键决策

| 决策 | 内容 | 理由 |
|---|---|---|
| 单向移植，不整目录覆盖 | 只把 `adapter/`、适配层测试、B 样例场景、适配文档复制进 11.12 | 11.12 的 `core.py`（phase 状态机）、`terminal.py`、`demo.py` 更新；整目录覆盖等于回退 |
| `validator.py` 以 11.12 为基底增量合并 | 只合并 `WALK_AWAY_FORBIDDEN`、`REDLINE_DIRECTIONS`、`_numeric_redline_hit`、软红线三函数、`terminal_rules` 行为 | 11.11 的 validator 缺 11.12 后来修的 `accept` 规则读取方式与 `FINAL_OFFER_*` 文案 |
| `terminal.py` 用 11.11 的功能超集 | 11.11 相对 11.12 只多 `partial_agreement_allowed` 与 `viewer` 裁剪，无反向缺失 | 属于能力增量，不构成回退；同时保住 BATNA 视角裁剪（演示前必须堵的泄露） |
| `core.py` 只改 `accept` 终局判定 + `evaluate` 透传 viewer | `accept` 分支原先硬编码 `PARTIAL_AGREEMENT`，绕过 `determine_terminal_type` | `partial_agreement_allowed=false` 时该硬编码会违反场景语义 |
| `walk_away` 拦截放在 `validator` | `submit_action` 第一步就是 `validate_action`，失败直接返回 | 保证“状态零推进”，避免 core 与 validator 双实现分叉 |
| A 的 `convert_b_scenario` 废除 | `load_scenario_bridge.convert_b_scenario` 直接 `return adapt_scenario(data)` | 一套语义；A 侧仅需换 import |
| `agents.json` 只搬 C 侧必需字段 | `_scenario.player` + `us`，字段名与 A 侧完全一致 | 完整对手注册表由 A 在仓库根维护；C 侧只消费场景组装需要的字段 |

## 3. 移植清单

| 源（C 11.11 三指数） | 目标（C 11.12 三指数） | 处理 |
|---|---|---|
| `adapter/__init__.py` | `adapter/__init__.py` | 原样 |
| `adapter/scenario_adapter.py` | `adapter/scenario_adapter.py` | 原样（唯一转换实现） |
| `tests/test_adapter.py` | `tests/test_adapter.py` | 原样，29 条继续全绿 |
| `scenarios/from_b_chip_controls.json` | `scenarios/from_b_chip_controls.json` | 原样 |
| `docs/scenario_adapter.md` | `docs/scenario_adapter.md` | 原样 + 新增第 8 节（与 A 的关系） |
| — | `load_scenario_bridge.py` | 新建 |
| — | `tests/test_bridge.py` | 新建，21 条 |
| — | `agents.json` | 新建，A 侧字段的精简副本 |
| `engine/validator.py` | `engine/validator.py` | 增量合并（见第 4 节） |
| `engine/terminal.py` | `engine/terminal.py` | 能力增量（见第 4 节） |
| `engine/core.py` | `engine/core.py` | 2 处增量（见第 4 节） |

`engine/indices.py`、`engine/state.py` 两版逐字节相同，未改动。

## 4. 引擎改动的向后兼容说明

### 4.1 `engine/validator.py`

| 改动 | 为什么 | 向后兼容 |
|---|---|---|
| `ERRORS` 新增 `WALK_AWAY_FORBIDDEN` | 场景可禁止退出谈判 | 新增键，旧场景不触发 |
| 新增 `REDLINE_DIRECTIONS` 常量 | 适配层可选输出显式方向，集中定义合法值 | 纯新增 |
| 新增 `_numeric_redline_hit()` | 把数值红线判定抽出来，供硬/软两条路径复用 | 逻辑与 v2 原实现完全一致，仅多了显式方向优先分支 |
| `is_redline_violation()`：`soft` 短路 + 走 `_numeric_redline_hit` | 软红线不阻断行动 | 无 `soft` 字段时行为不变；有 `redline_direction` 时按显式方向 |
| 新增 `is_soft_redline_violation()` / `soft_redline_violations()` | 软红线只出 warning | 纯新增，调用方只展示 |
| `accept` 段改为 `requires_full` 组合判断 | 场景禁止部分协议时，accept 必须覆盖全部条款 | 三开关全缺省时等价于原来的 `accept_requires_no_open_issues` 判断 |
| 新增 `walk_away` 拦截 | 契约语义落地 | 缺省 `allow_walk_away=True`，旧场景零变化 |

`FINAL_OFFER_ALREADY_DECLARED` / `FINAL_OFFER_LOCKED` 的 message 文案**保留 11.12 原文**，
未采用 11.11 的加长版，避免 79 条既有断言漂移。

### 4.2 `engine/terminal.py`

| 改动 | 为什么 | 向后兼容 |
|---|---|---|
| `batna_comparison(..., viewer="")` | 非 viewer 方 `batna/net_gain/better_than_batna` 置 null，防反推底牌 | 默认空 viewer = 内部全量，旧调用不变 |
| `evaluate(..., viewer="")` | 同上 | 同上 |
| `determine_terminal_type`：`partial_agreement_allowed=false` 时部分协议判 `DEADLOCK` | 场景禁止部分协议 | 缺省 true，旧场景不变 |

### 4.3 `engine/core.py`

| 改动 | 为什么 | 向后兼容 |
|---|---|---|
| `accept` 终局：先算 `missing`，再按 `partial_agreement_allowed` 决定 `PARTIAL_AGREEMENT` / `DEADLOCK` | 原实现硬编码 `PARTIAL_AGREEMENT`，绕过场景开关 | 缺省 true 时与原来完全一致 |
| `evaluate(viewer="")` 透传 | 与 `terminal.evaluate` 对齐 | 默认参数 |

`accept` 的 `DEADLOCK` 分支是**防御性口径**：`validator` 已先行拦截
（`requires_full` + `open_issues` 非空时返回 `AGREEMENT_HAS_OPEN_ISSUES`），
该分支只在状态被外部篡改时兜底，正常流程不可达；行为与
`determine_terminal_type` 保持一致。

`phase` 状态机、`evaluate()` 结构、`batna_comparison()` 字段、`replay()` 均未删除或改写。

## 5. A 侧 `convert_b_scenario()` 的缺陷逐条结论

> 说明：任务书在 bug 3 与 bug 6 之间有两段文字（bug 4 / bug 5 的标题）在传输中丢失，
> bug 4 / bug 5 按紧邻残留文本“`…0.01 时归一化并记结构化 warning`”与 A 代码实际行为还原判定。

| # | 结论 | 依据 | 现状 |
|---|---|---|---|
| 1 | 成立 | `_convert_enumerated` 用 `parties[0]/parties[1]` 硬编码，`_goal()` 取到的 target 在枚举分支从未使用；`dispute_forum` 上 us 对 `unilateral` 得 1.0，与 target=`bilateral` 相反 | 已由适配层修复：每方以自己 target 为 1.0 线性衰减 |
| 2 | 成立 | `"redline": redline_value if redline_value is not None else ideal`，`ideal == redline` 时引擎恒返回 False | 已修复：无红线不写 `redline` 键 |
| 3 | 成立 | `_convert_numeric` 只取 `redline.get("value")`，`op` 未读入 C 场景 | 已修复：输出 `redline_direction` |
| 4 | 成立（按残留文本还原为“权重未归一化”） | `_weights()` 直接 `round(weight, 4)`，权重和偏离 1 时 Interest 口径失真且无告警 | 已修复：`_apply_weights` 归一化 + `WEIGHT_NORMALIZED` |
| 5 | 成立（按残留文本还原为“归一化阈值与告警缺失”） | A 侧无 0.01 阈值判断、无结构化 warning | 已修复：`abs(total-1.0) > 0.01` 触发告警 |
| 6 | 成立 | `terminal_rules` 只映射 `accept_requires_no_open_issue` | 已修复：三字段全映射，引擎三开关全支持 |
| 7 | 成立 | 数值 `initial = minimum`、枚举 `initial = options[0]`，且无 warning | 已修复：数值取双方 ideal 中点并按硬红线夹逼，枚举取 order 最小项；两者均记 `INITIAL_DERIVED`；显式 `initial` 优先（见 5.1） |
| 8 | 成立 | `[assumption["text"] for ...]` 丢弃 `assumption_id` / `affects` | 已修复：`assumptions` 保留 `[A1] ` 前缀；新增旁路键 `assumptions_detail` 原样保留结构化假设（含 `affects`） |

### 5.1 bug 7 已裁决：采用「中点 + 硬红线夹逼」

2026-11-14 裁决：数值条款 `initial` 由 `range.min` 改为
**双方 `ideal` 中点，再夹逼到双方硬红线可行区间**。

理由（已实测）：`range.min` 让开局方案在两个数值条款上都落在 cn 的硬红线违规区间
（`受管制先进制程门槛` initial=7 < cn redline 14；`逐案许可有效期` initial=6 < cn redline 12），
等于从一个“对方绝不接受”的非法基点起算。中点方案对双方 ideal 对称，且夹逼后落在可行域内
（条款一 `[14,21]` → 21；条款二 `[12,24]` → 18）。

实现：`adapter.scenario_adapter._derived_initial()` / `_resolve_numeric_initial()`。

- `IDEALS_INCOMPLETE`（ideal 不足两方）→ 回退 `range.min` + warning；
- `REDLINE_RANGE_EMPTY`（双方硬红线可行域为空）→ 取中点 + warning，交给审计暴露；
- 夹逼成功 → 只记 `INITIAL_DERIVED`。

断言同步：本轮唯一授权改动的断言是
`tests/test_adapter.py::test_initial_utility_matches_engine`，期望值由
`cn=0.39 / us=0.6717` 改为 `cn=0.7967 / us=0.6717`（实跑 0.796667 / 0.671667）。
us 不变是夹具的偶然：us 的 ideal 到 `range.min` 的距离恰好等于到中点夹逼值的距离。

前向兼容：B 若在 `issues[]` 中提供显式 `initial`，适配层**优先采用**并跳过推导与
`INITIAL_DERIVED` warning；类型或范围非法（数值项不在 `[min,max]`、枚举项不是
`option_id`）直接抛 `ScenarioContractError`。

### 5.2 A 侧另外三处缺陷（任务书未列，但已确认）

| 缺陷 | 后果 | 适配层现状 |
|---|---|---|
| 枚举红线只处理 `op == "in"`，把 `not_in` 的 value 当允许集 | `not_in` 语义完全反向 | `_enum_redlines` 两种 op 分开处理 |
| `_hard_redline` 要求 `hard` 为真值 | B 未显式写 `hard` 时红线被整体漏掉 | `item.get("hard", True) is not False` |
| `parties[]` 缺 `public_position` / `priority_ranking` / `batna_note` | 前端展示与审计线索缺失 | 适配层全部映射 |

## 6. 已知遗留问题

1. **`affects` 由旁路键承载**：`assumptions` 仍是字符串数组（引擎只读它），
   `assumptions_detail` 原样保留 `assumption_id / text / reason / affects`。
   审计/复盘工具改读旁路键即可；若要把 `affects` 接进引擎，需要引擎侧新增只读消费点。
2. **数值 `initial` 已改为中点 + 夹逼**：见 5.1。`IDEALS_INCOMPLETE` /
   `REDLINE_RANGE_EMPTY` 两个降级分支需要审计关注。
3. **`step` 不参与校验**：B 若依赖步长离散化，需要引擎补校验。
4. **数值红线单槽位**：同方 `min`+`max` 区间约束只保留第一条。
5. **多参与方**：`accept` 只找“第一个对方”，三方以上会退化。
6. **`agents.json` 是精简副本**：只含 `make_scenario()` 需要字段；A 侧若扩展
   `make_scenario()` 读取新字段，需要同步本文件或改为读取 A 的完整注册表。
7. **A 的 `api.py` 尚未改 import**：本次只提供桥接层，A 侧改动未落地（不应由 C 单方面改 A 分支）。

## 7. `Diplomat_webdemo2.0/C 11.11 三指数/` 的处置建议

**建议保留为历史快照，先不删除。** 具体做法：

1. 在该目录加 `DEPRECATED.md`，说明：
   - 运行时唯一入口已迁至 `Huawei/C 11.12 三指数/`；
   - 本目录仅作 2026-11-13 的适配层快照，供比对；
   - 不要在此目录继续开发。
2. 删除前先与 A/B/D 确认没有脚本或文档仍在引用该路径。
3. 若后续确认无引用，再整体删除并同步 `.gitignore`。

本次**未修改该目录任何文件**（符合“不碰历史快照”的约束）。

## 8. 需要与 A / B 对齐的事项

### 与 A

1. 把 `load_scenario.py` 改为转发 `load_scenario_bridge`（README 3.1 给了 3 行 shim）。
2. `make_scenario()` 的占位分数已替换为常量设计表；若 A 侧有独立维护的 `agents.json` 立场数据，
   需要与 `_ENUM_CLAUSES` / `_NUMERIC_CLAUSES` 对齐或直接提供结构化输入。
3. `engine.evaluate()` 新增 `viewer` 参数；对外展示评价必须传己方 party_id。

### 与 B

1. 补 `issues[].initial`（数值开局值 / 枚举初始选项），替代适配层推导。
2. 补 `index_rules`（行为标签 → 三指数查表）的正式来源，目前整表借用 `demo_scenario.json`。
3. 补 `deadlock_rounds`、`action_points_per_round`（当前固定 2 / 3）。
4. 明确 `terminal_rules` 三字段的冻结语义与值域：
   `allow_walk_away` / `accept_requires_no_open_issue`（注意单数） / `partial_agreement_allowed`。
5. 若需要“假设—条款”可追溯，请把 `assumptions[].affects` 保留在契约中并说明用途。
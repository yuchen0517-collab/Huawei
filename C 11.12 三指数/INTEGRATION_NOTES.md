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
## 9. 11-16 交付日状态

### 9.1 集成层完成度自评

| 能力 | 状态 | 依据 |
|---|---|---|
| B→C 场景适配层（唯一转换实现） | **完成** | `adapter/scenario_adapter.py` 910 行；`convert_b_scenario` 直接委托 `adapt_scenario`，A 的旧转换器已废除（`tests/test_bridge.py::ConvertDelegationTest` 断言输出相等） |
| 引擎收口（状态/结算/终局/审计/replay） | **完成** | `engine/{state,core,validator,terminal,indices}.py`；`demo.py` 四项指标全通 |
| 隐藏底牌隔离对抗测试 | **完成** | `tests/test_isolation_adversarial.py` 843 行 / 24 条，三类诱导零泄露 |
| 多智能体发言调度 | **完成** | `engine/scheduler.py` 93 行 + `tests/test_scheduler.py` 186 行 / 12 条 |
| A 侧复盘链路接通 | **完成（由 A 完成，C 不重复接）** | A 的 `1f508b4` 在 `api.py` 接通 debrief/evaluate；C 分支该目录与 A 逐字节一致（见 `docs/RECONCILE_A_C_1116.md`） |

### 9.2 本次交付日改动清单

| 改动 | 位置 | 说明 |
|---|---|---|
| K4：`action_points_per_round` 5→3 | `load_scenario_bridge.py::make_scenario_with_warnings` | 引擎默认 / `demo_scenario.json` / B 场景适配默认 / A 书面口径均为 3，原 5 为历史遗留 |
| K4 回归测试 | `tests/test_bridge.py::MakeScenarioRegressionTest::test_action_points_per_round_is_three` | 断言 `make_scenario()["action_points_per_round"] == 3` |
| 单复数双读端到端证明测试 | `tests/test_bridge.py::BSingularTerminalRuleTest::test_b_scenario_singular_terminal_rule_enforced` | 用真实夹具 `scenarios/from_b_chip_controls.json` 走完整加载链，证明「有未决条款 accept 被拒 + 状态零推进 + 清空后 accept 成功」 |
| A/C 目录差异核对报告 | `docs/RECONCILE_A_C_1116.md` | 只读比对；两分支 `C 11.12 三指数/` tree 哈希相同（`25d9802`），39 文件零差异 |

### 9.3 已知边界与待办（答辩用，如实列出）

1. **`speaker_score`（四维发言评分）未实现。** 归属已由 A 接口答复第三轮 Q3 + D 的
   state-contract 评审 §5 划给 C 的“口径与落库”，但 A、D 均明确**本轮不出接口、
   终局面板按 null 态渲染**，故本轮不实现，列为交付后 backlog。
2. **`est_confidence`（对方态势可信度）未产出。** D 已裁决改为定性分级
   `high/mid/low/unknown` 由 D 前端推导；C 侧只预留字段、默认不填。
3. **K4（action_points 3 vs 5）仍待 D 签字。** 本仓库已统一取 3；若 D 改判 5，
   需同步修改 `scenarios/demo_scenario.json`、B 场景适配默认值，并通知 A 修订
   对 C/D 的书面口径。**不要把“C 已改为 3”当成 D 已同意。**
4. **B 契约仍缺四个字段**：`index_rules`、`issues[].initial`、`deadlock_rounds`、
   `action_points_per_round`。现由适配层推导或借用 `demo_scenario.json` 的表，
   需 B 补正式来源（B 出题材、C 转场景 JSON 的分工不变）。
5. **`from_b_chip_controls.json` 的单数键 `accept_requires_no_open_issue` 不改。**
   它是 B 冻结契约（`scenario.schema.json` 的 `terminal_rules.required` 写单数且
   `additionalProperties: false`）；引擎读复数、由适配层双读翻译，已在 9.2 加证明测试。
## 10. 11-17 对接 B 契约 1.1

成员B `e229462`「11.15针对c的修改」把场景契约从 1.0 升到 1.1（加法式，1.0 场景仍合法）。
本轮按 B 的原文补齐适配缺口，并修掉一个**会静默归零**的严重问题。

### 10.1 本轮改动清单

| # | 文件 / 函数 | 改动 | 理由 |
|---|---|---|---|
| 1 | `adapter/scenario_adapter.py::_normalize_index_rules` | 新增：B 1.1 的 13 标签平铺表 → `image_actions` / `trust_actions` 两张表 | B 表与引擎表**结构层级不同**；适配层原样保留会让 image/trust 静默归零 |
| 2 | 同上 | `initial` 全局值展开到每个参与方；`scale` 补 `[0,100]`；`sensitivity` 缺失时省略并 warning | 引擎要求按参与方分层；不编造敏感度 |
| 3 | 同上 | `interest_delta` 忽略 + `INTEREST_DELTA_UNSUPPORTED` warning | 引擎无 interest 行为通道，见 `docs/INDEX_RULES_V1_GAP.md` |
| 4 | `engine/indices.py::IndexRulesShapeError` | 新增异常（可外部 import） | 形状不可识别时显式失败，禁止静默返回 0 |
| 5 | `engine/indices.py::behaviour_delta` | 非空表但既无 `image_actions` 也无 `trust_actions` 时抛错；可选 `warnings` 参数记录缺档位 | 防静默失效；空表保持 delta=0 兼容老场景 |
| 6 | `engine/indices.py::initial_indices` | 同时兼容「全局 initial」与「按方分层 initial」 | 上游绕过适配层时不再静默回落 50 |
| 7 | `adapter/scenario_adapter.py::_adapt` | `runtime.action_points_per_round` 显式读取（1~5）；缺省 3 + warning | B 明确「禁止在适配层写死」 |
| 8 | 同上 | `terminal_rules.deadlock_rounds` 显式读取（2~10 且 ≤ max_rounds）；缺省 2 + warning | 路径与字段位置按 B 1.1 |
| 9 | 同上 | `terminal_rules` 三布尔改为**必填**，取消 `.get(..., True)` 兜底 | B 1.1 冻结语义：缺失或非布尔即契约错误 |
| 10 | `adapter/scenario_adapter.py::validate_b_contract` | 新增 numeric `initial` 的 `(value-min) % step` 整数倍校验 | B 1.1 明确要求 |
| 11 | 同上 | 新增 `initial_ref` 解析校验（`public_facts[].fact_id` / `assumptions[].assumption_id`） | B 1.1 明确要求「填写时必须能解析到」 |
| 12 | 同上 | 适配结果在 clause 上保留 `initial_ref` + `INITIAL_REF_RESOLVED` warning | 供审计追溯「有据的现状」 |
| 13 | `engine/core.py::finish` | 显式传入 `PARTIAL_AGREEMENT` 且场景禁止部分协议时改判 `DEADLOCK` | 关闭 `finish(terminal_type=...)` 绕过口，与另外两处判定同口径 |
| 14 | `load_scenario_bridge.py::make_scenario_with_warnings` | 从 `agents._scenario.runtime` / `terminal_rules` 读运行参数，缺省回默认并加来源注释 | 与 B 1.1 的显式读取口径对齐 |
| 15 | `tests/fixtures/index_rules_v1.json` | **新增**（从 `origin/feat/scenario-b` 复制 B 原表） | 测试不得跨分支读取，别人 checkout 后必须可独立跑 |
| 16 | `tests/fixtures/b_scenario_dst.json` | **新增**（B 的真实场景，从 `origin/feat/scenario-b` 复制） | 端到端回归需要 B 真实场景 |
| 17 | `tests/test_index_rules_v1.py` | **新增** 20 条 | 任务 1 的全部验收点 |
| 18 | `tests/test_contract_v1_1.py` | **新增** 18 条 | runtime / deadlock / 三布尔 / initial_ref |

测试夹具没有因「三布尔必填」而需要补齐：`scenarios/from_b_chip_controls.json` 与
`tests/fixtures/b_scenario_dst.json` 的三布尔都齐全且都是 JSON 布尔。

### 10.2 `index_rules` 形状映射表

| B 1.1 原生形状 | 引擎形状 | 规则 |
|---|---|---|
| `initial: {"image": 50, "trust": 50}` | `initial: {"p1": {"image": 50, "trust": 50}, "p2": {...}}` | 全局值展开到每个 `parties[].id`；已分层则原样保留 |
| `{"<label>": {"slight": {...}, "moderate": {...}, "major": {...}}}` | `image_actions["<label>"][magnitude]` | 取 `image_delta` |
| 同上 | `trust_actions["<label>"][magnitude]` | 取 `trust_delta` |
| 同上 | —（丢弃） | `interest_delta` 忽略 + `INTEREST_DELTA_UNSUPPORTED` |
| 无 `scale` | `scale: [0, 100]` | 补引擎默认量纲 |
| 无 `sensitivity` | 省略该键 | 引擎按 1.0 等权；`SENSITIVITY_ABSENT` warning |
| 缺某标签 | 该标签三档补 0 | `INDEX_RULE_LABEL_MISSING` warning |
| 13 标签外的键 | 忽略 | `INDEX_RULE_LABEL_UNKNOWN` warning |
| 已含 `image_actions` / `trust_actions` | 原样深拷贝 | `INDEX_RULES_ALREADY_NATIVE` warning |

13 个标签与三档幅度两边完全一致：
`constructive_proposal / cite_rules / hardline_stance / broken_promise /
personal_attack / redline_provoke / procedural / diplomatic_reframe /
protect_ally / keep_promise / betray_ally / vague_stance / conditional_concession`，
`slight / moderate / major`。因此转换是无损的结构搬移。

### 10.3 `IndexRulesShapeError` 的设计理由

`_table_delta()` 原来的语义是「查不到表就返回 0」。这在「场景没有结算表」时是正确的，
但在「场景带了表、但表形状没被识别」时是**静默降级**：image / trust 永远停在初值，
全部测试照样绿。B 1.1 原生表正好会触发这条路径。

现在的规则：

- `index_rules` 为空 `{}` 或缺失 → 不抛，`delta=0`（兼容 demo / 老场景）；
- 表非空、但既无 `image_actions` 也无 `trust_actions` → 抛
  `IndexRulesShapeError`，消息列出实际顶层键，并提示「是否使用了未经适配层转换的 B 1.1 原生表」；
- 适配层 `_normalize_index_rules` 遇到同样不可识别的形状 → `ScenarioContractError`。

实测（`tests/fixtures` 真实 B 表）：适配后 `personal_attack/major` 的
`behaviour_delta` 为 `{"image": -9, "trust": -6}`，初值 50 → 41 / 44；
修复前同一条链路为 `{"image": 0, "trust": 0}`。

### 10.4 `partial_agreement` 双触发口核对结论

结论：**部分满足 → 已做最小增量修复**。

| 核对项 | 结论 | 证据 |
|---|---|---|
| `partial_agreement_allowed=false` 时不存在 PARTIAL_AGREEMENT | 基本满足；`finish(terminal_type="PARTIAL_AGREEMENT")` 曾可绕过 | `engine/terminal.py:128-131`、`engine/core.py:181-197`；本轮在 `core.py::finish` 关闭显式绕过口 |
| 优先级高于 `accept_requires_no_open_issue` | 满足：存在未决条款且 partial=false 时 accept 被 validator 拒 | `engine/validator.py:401-412`（`requires_full = not partial_allowed or ...`） |
| 与 `accept_requires_no_open_issue=true` 同时为 true 不矛盾 | 满足：引擎有两个独立触发口——accept 口与 `finish()` 自动封存口 | `engine/core.py:274-288`（`_seal_partial_agreement`）+ `determine_terminal_type` |
| timeout / deadlock 不受三开关影响 | 满足：`ROUNDS_EXHAUSTED` / `DEADLOCK` 分支不读三布尔 | `engine/terminal.py:137-146`、`engine/core.py:252-261` |

新增测试固化：`tests/test_contract_v1_1.py::TerminalBooleansTest`（4 条）。

### 10.5 仍待对齐事项（按紧急度）

1. **`interest_delta` 无落点**（最高优先级，需 B + 队长裁决）：见 `docs/INDEX_RULES_V1_GAP.md`。
   C 侧当前忽略并 warning；推荐方案 (a)：B 移除或标注为 informational。
2. **`initial_ref` 的承载字段**：C 侧暂存在 `clauses[].initial_ref`（引擎忽略）。
   需与 B / 审计确认：是否要在 `docs/state.example.json` 或审计报告的字段里正式暴露。
3. **`sensitivity` 缺失**：B 1.1 未提供参与方敏感度，C 按 1.0 等权处理。
   若 B 后续补该字段，适配层已支持直接透传（见 `_normalize_index_rules` 第 6 步）。
4. **`deadlock_rounds` 的「状态变化」口径**：B 描述为「连续多少轮无状态变化」，
   C 引擎按 `rounds_without_offer`（无新报价）计数，语义略窄。需与 B 确认是否要把
   「无新事件 / 无新暗线」也纳入计数；本轮未改引擎计数口径。
5. **`runtime` 目前只有 `action_points_per_round`**：B schema 的
   `additionalProperties: false` 已冻结；后续若加字段需 B 先升级契约。

### 10.6 验证基线（2026-11-17 实跑）

| 检查项 | 结果 |
|---|---|
| `python -m pytest tests/ -q` | `218 passed, 145 subtests passed` |
| `python -m unittest discover -s tests -t .` | `Ran 218 tests ... OK` |
| `python demo.py` 终局 | `FULL_AGREEMENT` |
| `demo.py` coverage | `1.0` |
| `demo.py` 审计 | `{"ok": true, "issues": [], "summary": {"blocking": 0, "warning": 0}}` |
| `demo.py` replay | `True` |
# 跨成员口径对齐 · 2026-11-19

> 依据：当前 `integrate/1120` 工作树与代码事实。每条均给出 C 侧默认口径，未获答复时先按默认执行，不留空白。

## Q1 `api.py` 对外评价是否走 `evaluate_for(engine, viewer)`？

- **【问题】** 对外给玩家展示评价时，是否统一调用 `load_scenario_bridge.evaluate_for(engine, viewer)`，而不是无参 `engine.evaluate()`？
- **【当前 C 侧口径】** 全仓库当前**不存在** `api.py` 与 `test_e2e.py`（顶层与子目录检索均无），A 那套 HTTP/端到端文件已被 revert，无法从代码确认其调用方式。C 侧唯一对外出口是 `C 11.12 三指数/load_scenario_bridge.py::evaluate_for(engine, viewer)`；它已同时裁剪 `batna_comparison` 与 `redline_check`（2026-11-19 修复，commit `b42ed76`），非 viewer 方一律 `None`。
- **【影响】** 若 A 侧或任何 HTTP 层直接无参调用 `engine.evaluate()`，会把双方 BATNA 与红线布尔原样下发，可由 `net_gain` / `redline_check` 反推对方底牌。
- **【需要谁签】** 成员A。
- **签署状态**：未签，C 侧按默认口径执行。
- **未答复时的默认口径**：C 侧只保证 `evaluate_for` 正确；任何外部调用方一律视为“未接入”，不为其无参调用背书，也不在 C 侧新增第二个评价出口。

## Q2 身份收口归属

- **【问题】** 客户端提交行动时，`actor` 由谁强制覆盖，是否统一走会话身份？
- **【当前 C 侧口径】** `load_scenario_bridge.py::submit_for(engine, viewer, action)` 已实现强制收口：`viewer` 为空抛 `ValueError`，action 自带的 `actor` 一律被覆盖为 `viewer` 后再进 `engine.submit_action()`。`load_scenario_bridge.py::debrief_for(engine, requester)` 同样要求显式 requester。
- **【影响】** 若上层再叠加一次 actor 覆盖且顺序/大小写不一致，可能出现双重覆盖或身份漂移；若不覆盖，则客户端可冒充他方结算。
- **【需要谁签】** 成员A。
- **签署状态**：未签，C 侧按默认口径执行。
- **未答复时的默认口径**：C 侧以 `submit_for` 为唯一身份收口；不信任任何入口传入的 `actor`，也不在引擎内新增会话概念。

## Q3 K4：`action_points_per_round` 取 3 还是 5？

- **【问题】** 每轮行动点最终取 3 还是 5？
- **【当前 C 侧口径】** 仓库统一取 **3**：`engine/core.py` / `engine/state.py` 默认、`scenarios/demo_scenario.json`、适配层 B 场景默认、`load_scenario_bridge.make_scenario()` 均为 3；`tests/test_bridge.py` 有 3 的回归断言。当前 241 条基线按 3 计。
- **【影响】** 若 D 改判 5，需同步改 `demo_scenario.json`、B 场景默认与 A 的书面口径；否则前端展示与引擎扣点不一致。
- **【需要谁签】** 成员D。
- **签署状态**：未签，C 侧按默认口径执行。
- **未答复时的默认口径**：**按 3 执行**，所有回归与演示均以 3 为准；不预留 5 的分支。

## Q4 B 契约 1.1 四字段是否齐？

- **【问题】** `index_rules` / `issues[].initial` / `deadlock_rounds` / `action_points_per_round` 是否已在 B 契约 1.1 中冻结齐全？
- **【当前 C 侧口径】** B 的 `e229462` 已把四字段补进 1.1（加法式，1.0 仍合法）。C 适配层现状：`index_rules` 由 `_normalize_index_rules` 把 B 的 13 标签平铺表转成 `image_actions` / `trust_actions`（不转换会静默归零，已修）；`issues[].initial` 显式优先、缺失时推导中点+红线夹逼；`deadlock_rounds` 从 `runtime.terminal_rules` 读取；`action_points_per_round` 从 `runtime` 读取，缺省 3 并记 warning。
- **【影响】** 若 B 后续再改字段名/层级，适配层需同步升级；若 B 认为已冻结，C 侧不再为缺字段做临时推导。
- **【需要谁签】** 成员B。
- **签署状态**：未签，C 侧按默认口径执行。
- **未答复时的默认口径**：按当前 1.1 字段解析；缺失字段走“缺省值 + 结构化 warning”，不静默归零。

## Q5 `interest_delta`

- **【问题】** B 契约 1.1 的 `interest_delta` 是否保留？由谁提供结算通道？
- **【当前 C 侧口径】** 适配层当前**忽略** `interest_delta`，只记 `INTEREST_DELTA_UNSUPPORTED` warning；引擎 `interest` 仅由条款效用重算（`engine/indices.py::interest_value`），没有按行为标签增减 interest 的通道。三方以上也没有转移支付 / 侧支付通道。
- **【影响】** B 若依赖 `interest_delta` 表达“发言本身影响利益”，当前不会生效；多边交易也无法表达议题间补偿。
- **【需要谁签】** 成员B。
- **签署状态**：未签，C 侧按默认口径执行。
- **未答复时的默认口径**：**忽略 `interest_delta`**，`interest` 只随条款方案变化；不新增第三条结算路径，不把标签写进 interest。

---

## 发给成员A

> A，C 侧对外评价出口已收口为 `load_scenario_bridge.evaluate_for(engine, viewer)`，2026-11-19 修复后 `batna_comparison` 与 `redline_check` 都会按 viewer 裁剪，非 viewer 方为 `None`（commit `b42ed76`）。请确认 `api.py` 的评价链路统一走这个函数，不要无参调用 `engine.evaluate()`。身份侧 C 侧用 `submit_for(engine, viewer, action)` 强制覆盖 `actor`，请确认你的接入层不会二次覆盖或顺序相反。另：当前仓库树里没有 `api.py` / `test_e2e.py`，我无法验证 HTTP 层端到端，需要你确认这两个文件的最终落点。

## 发给成员B

> B，C 侧按契约 1.1 已读取 `index_rules` / `issues[].initial` / `deadlock_rounds` / `action_points_per_round` 四字段，`index_rules` 已做形状归一（不再静默归零）。请确认这四字段是否已冻结齐全。另一个悬空项是 `interest_delta`：C 侧目前只记 `INTEREST_DELTA_UNSUPPORTED` warning，没有结算通道；请裁决是移除、标为 informational，还是补正式通道。未答复前 C 侧默认忽略该字段。

## 发给成员D

> D，K4 的 `action_points_per_round` C 侧当前统一取 3（引擎默认、demo 场景、B 场景适配、bridge 均为 3，241 条回归按 3 写），请签字确认；若改判 5 请明确，我同步改场景与回归。`speaker_score` / `est_confidence` 本轮只预留字段，值恒为 `null`；四维评分与定性分级由你侧推导，前端请按 `null` 渲染，不要展示默认分。

## 发给队长

> 队长，C 侧成果目前**只在 `integrate/1120`**（合并提交 `1b8a5c6`，本轮修复 `b42ed76`、卫生 `59758ae`/`589d35c`），**develop 尚未合并**，需要你统筹合入。团队级风险：仓库当前**没有 `api.py` / `test_e2e.py`**，A 那套 HTTP 层已被 revert，导致 C 侧无法验证 HTTP 层端到端集成；请确认 A 侧最终文件落点与集成责任。另 `git fetch/push` 仍受网络与凭据阻塞，需要你在可联网环境复核远程 develop 是否还有新提交。
# 第 6 天 · 发给 CodeArts Agent 的提示词（教练 Agent 从 0 到可用）

## 先说一句人话：为什么不能直接开写

日程给 D6 的是「修 UI 状态同步；教练异步接入」。但教练这块和前面几天不一样——
**它不是写个面板就完事，它没有任何数据来源。**

三条已核实的事实，决定了今天的正确顺序：

1. A 的状态投影函数 `Huawei/api.py` 的 `project_snapshot()`（约 133–150 行）只返回 **9 个字段**：
   `session_id / round / phase / my_offer / opponent_offer / open_issues / action_history / status / mode`。
   **没有 `speaker_score`，没有 `action_points`，更没有教练建议字段。**
2. 前端 `src/adapters/httpAdapter.js:112` 在读 `payload.speaker_score`，
   `:100` 在读 `payload.action_points`——真实接口下这两个判断**永远不成立**，
   现在终局四维有数，只是因为跑的是 mock。
3. A 已有 `POST /session/{session_id}/debrief`，但它只 `return {"status": "accepted"}`（status_code=202）。
   **收下了，然后呢？结果落在哪个字段、前端怎么取回，全都没定。**

所以今天的顺序是：**先定契约（Task 1）→ 再用 mock 把前端做到可演示（Task 2）→ 同时把接口需求甩给 A（Task 3）**。
不要跳过 Task 1 直接写代码，否则 Task 2 写完要为 Task 3 的结论重写一遍。

> 手册兜底原则：里程碑未通过时**先砍范围，不要靠最后一天通宵补集成**。
> 今天如果只做完 Task 1 + Task 2 的 P0 项，也算达成 D6；Task 2 的 P1 项可推到 D8「复盘页面」。

---

## 提示词正文（整段复制给 CodeArts Agent）

````text
# 你的角色

你是 Diplomat 项目的前端工程智能体，服务对象是成员 D（UI／教练 Agent／Demo 统筹）。
今天按团队手册是第 6 天，日程给 D 的两项是：**修 UI 状态同步；教练异步接入**。
本轮只做教练 Agent，且必须按 Task 1 → 2 → 3 的顺序做，**每完成一个 Task 就停下来等确认**。

工作目录：`11.11/`（零构建、零依赖、原生 `<script>` 分层版，不是 ES module，不要用 import/export）。

# 教练 Agent 的边界（手册 §2.1 写死，不可越界）

| 教练 Agent 负责 | 教练 Agent 不得负责 |
|---|---|
| 异步分析策略选择 | **阻断每一轮操作** |
| 指出替代行动 | **代替用户做决定** |
| 生成学习反馈 | **改变谈判事实状态**（轮次、版本、行动点、条款、终局一律不许碰） |

这三条「不得」会被翻译成代码里的硬约束，见 Task 2 的 A3、A5、B4。

# 已核实的事实（不要怀疑、不要重新调研，直接按此实现）

1. 前端分层：`store.js`（唯一状态）/ `adapters/`（mock 与 http 同签名）/ `components/`（只读渲染，返回 HTML 字符串）。
   切换点只有 `D.adapters.use('mock' | 'http')`。组件层**禁止**做任何数值计算。
2. `src/adapters/mockAdapter.js` 约 117–120 行，终局卡片的 `keyTurns`（关键转折）与
   `reviewPoints`（复盘要点）是**硬编码静态文案**。这是教练 Agent 的产出物被提前写死在了展示层，
   接真接口后这块必然是空的。
3. `src/components/finale.js` 已经正确实现了 `speaker_score` 展示：只以 `speakerScore` 是否为
   null/空判定首轮不计分（K5=A 裁决），前端只展示与映射评级，不重算加权。**这个模式是对的，照抄。**
4. `docs/state-contract.md` §5 字段总表里 `coachAdvice` **已经登记过一行**：类型 `object | null`、
   主责 B＋C、降级行为「未返回 → 折叠入口『教练建议生成中』，不阻塞下一轮」，
   并标注「ia-design 约束 7；现状未实现」。但它挂在 **P15：A 未答、B 未回**，属于未回签项。
   也就是说：占位已登记，字段结构从未定义。
5. `Huawei/api.py` 的 `project_snapshot()` 只返回 9 个字段，无 `speaker_score`、无 `action_points`、
   无任何教练字段。`POST /session/{session_id}/debrief` 只返回 `{"status":"accepted"}`（202）。
6. `Huawei/openapi.json` 的真实端点是 `POST /session`、`GET|POST /session/{session_id}/state`、
   `/session/{session_id}/action`、`/session/{session_id}/auto_step`、`/session/{session_id}/debrief`。
   而 `httpAdapter.js` 里写的默认路径（`/session/actions`、`/session/state`、`/session/summary` 等）
   **一个都对不上**。**本轮不要动这些路径**，那是「接真实接口」的独立任务，不要和教练混在一起。

---

# Task 1 · 先写契约文档（最高优先级）

产出 `docs/coach-contract.md`。不写代码，只写字段与时序定义。
**这个文件要能直接发给 A 和 B 评审，所以要精确到字段名和类型。**

## 1.1 `coach_advice` 对象结构（后端返回 snake_case）

严格按下面的结构定义，不要自己增删字段：

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `status` | `"pending" \| "ready" \| "failed"` | 是 | 本次生成的状态。`pending` 时 `items` 必须为空数组 |
| `basis_round` | number | `ready` 时必填 | 建议基于哪一轮的状态生成 |
| `basis_version` | number | `ready` 时必填 | 生成时的协议版本号，用于判断建议是否已过期 |
| `generated_at` | string | `ready` 时必填 | ISO 8601 时间戳 |
| `items` | array | 是 | 建议条目，见 1.2。空数组是合法值 |
| `fail_reason` | string \| null | 否 | 仅 `status="failed"` 时有值，面向用户的短句，不是堆栈 |

## 1.2 `items[]` 单条结构

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `id` | string | 是 | 稳定标识，前端用它做展开态记忆，不用数组下标 |
| `kind` | `"stage" \| "alternative"` | 是 | `stage`=阶段建议，`alternative`=替代行动。手册要求的两类，缺一不可 |
| `title` | string | 是 | 不超过 16 字的短标题 |
| `text` | string | 是 | 30–90 字，必须指向本轮**具体**条款或行动；禁止「建议加强沟通」这类空话 |
| `evidence` | array | 是（可为空数组） | 证据链接，见 1.3。手册完成标准明写「建议引用具体行动」，所以此字段是硬性要求 |
| `ap_cost` | number \| null | 是 | 替代行动预计消耗的行动点；`stage` 类固定 `null` |
| `apply_hint` | string \| null | 否 | 若为 `alternative`，给出可操作的入口描述（如「把『复核周期』改为 24 个月」）；**只是提示，前端绝不自动改草稿** |

## 1.3 `evidence[]` 单条结构

| 字段 | 类型 | 含义 |
|---|---|---|
| `kind` | `"action" \| "offer" \| "event"` | 证据类型 |
| `round` | number | 发生在第几轮 |
| `action_id` | string \| null | `kind="action"` 时必填，对齐 A 的 `a` + 6 位数字格式（`make_action_id`） |
| `clause` | string \| null | 涉及的条款名，必须能在 `state.clauses` 里找到同名项 |
| `label` | string | 展示文案，≤ 20 字 |

**证据可溯源是硬要求**：每条 evidence 必须能被前端解析成真实存在对象。
`action_id` 在 `action_history` 里查不到、或 `clause` 在条款表里找不到的，视为**无效证据**。

## 1.4 触发与取回时序（这一节必须让 A 确认，写两个方案让 A 选）

- **触发**：`提交本轮报价` 成功、且新状态渲染完成后，前端 `POST /session/{id}/debrief`（fire-and-forget）。
  提交链路**不得 await 这个请求**，失败也不影响提交结果。
- **取回**，二选一：
  - **方案 A（前端倾向）**：`coach_advice` 作为 `project_snapshot()` 的**可选字段**返回，
    前端在后续 `GET /state` 时顺带取到。优点是不加新端点、不新增轮询。
    代价：A 要接受投影字段从 9 个变 10 个。
  - **方案 B**：新增 `GET /session/{id}/coach`，前端按退避轮询（3s、6s、12s，最多 3 次）。
    代价：多一个端点 + 前端要处理轮询生命周期。
  - 契约里两个方案都要写清楚请求/响应示例，标注「待 A 选定」，**不要只写一个**。
- **过期规则**：`basis_version < state.version` 时，面板显示「基于 v{basis_version} 的建议」并保留原文，
  **不自动消失、不闪动**；终局打开后教练面板冻结，不再刷新。
- **轮次触发节流**：每轮提交只触发一次；同一轮内重复点击「提交本轮总结」（K3=B，不推进轮次）**不得**重复触发。

## 1.5 不泄露硬约束（照 K7 的做法写，这是评审重点）

教练 Agent 只能引用**公开事件**：`action_history`、`open_issues`、双方的 `public_message`、
`my_offer` / `opponent_offer` 的已报价条款。

**禁止**引用或暗示：对方 `private_state_by_party`、对方红线、对方真实 BATNA、`net_gain`、
对方隐藏任务完成态。

前端要做**双重断言**（不是只写文档）：
1. 渲染前逐条校验 `evidence`，任一 evidence 解析失败 → 整条 item 不渲染。
2. `text` 命中禁用词表（见 Task 2 B3）→ 整条 item 不渲染。
   被过滤掉要在控制台打 `console.warn`，但不弹窗、不打扰用户。

## 1.6 与 `speaker_score` 的分工（必须在文档里写死，否则一定被做混）

| | `speaker_score` | `coach_advice` |
|---|---|---|
| 回答什么 | 这一局**打了几分** | 下一轮**可以怎么做** |
| 产出时机 | 终局，由 A 的终局端点返回（K5=A） | 每轮提交后，异步 |
| 结构 | 四维分 + total + 一句话 feedback | items[] + evidence[] |
| 前端职责 | 只做展示与 S/A/B/C/D 评级映射，不重算 | 只做展示与有效性校验，不生成、不改写 |
| 首轮特例 | `null` → 显示「首轮不计分」 | 首轮（对方未发言）也应有 `stage` 类建议，**不受 null 影响** |

## Task 1 完成标准

- `docs/coach-contract.md` 落盘，含 1.1–1.6 全部小节 + 一份**完整 JSON 示例**
  （1 条 `stage` + 1 条 `alternative`，evidence 用 mock 里真实存在的 `round` 和条款名）。
- 文末附「需要 A 回答的 3 个问题」：方案 A/B 选哪个、投影字段能否加、`generated_at` 时区口径。
- 附「需要 B 回答的 2 个问题」：`text` 的生成 Prompt 谁写、`feedback` 与 `items[].text` 的口径会不会重复。
- **不写任何代码。**

---

# Task 2 · 用 mock 把教练前端做到可演示

契约定完立刻做这一步。**不依赖 A，全部用 mockAdapter 驱动**，目标是评委看得懂的「异步、不阻塞、可溯源」。

## P0 · 必做（今天做不完就是 D6 未完成）

### A1 状态层加槽位
`src/store.js` 的 `S` 增加教练状态，字段名与 Task 1 契约对齐（前端内部用 camelCase，
映射仿照 `httpAdapter.js:112` 的 `payload.speaker_score → patch.speakerScore`）：

- `coach`: 当前 `coach_advice` 对象，初始 `null`
- `coachStatus`: `"idle" | "pending" | "ready" | "failed"`
- `coachCollapsed`: boolean，**默认 `true`**（手册要求「默认折叠」）

**红线**：教练状态必须存在独立槽位，**严禁**写入或修改 `round` / `version` / `ap` / `clauses` /
`openIssues` / `ended` 任何一项。这一条要在代码注释里写明「教练不改变谈判事实状态」。

### A2 适配层加方法
`mockAdapter` 与 `httpAdapter` 实现同一签名的 `coach(state)`：

- `mockAdapter.coach`：返回一份符合契约的 mock，覆盖三种情形，由 DEMO 面板选择：
  `ready`（2 条 items）/ `pending`（status=pending，items 空）/ `failed`（status=failed + fail_reason）。
- `httpAdapter.coach`：**不发请求**，直接返回 `{ ok: true, coach: null }` 并加
  `// TODO 待 A 确认方案A/B` 注释。接口没定就诚实返回空，**不要臆造路径**。

### A3 异步不阻塞（这是最容易被做错的一条）
- 触发点在提交成功回调里，**fire-and-forget**：`coach()` 的 Promise 绝不进提交链路的 await。
- 提交失败的分支（`INVALID_ACTION` / `VERSION_CONFLICT` / `TIMEOUT` / `SESSION_BUSY`）**一律不触发教练**。
- 「提交本轮总结」（K3=B）不触发教练。
- 教练请求 pending 期间，用户可以正常改条款、选卡、提交下一轮，**不许有任何禁用、遮罩或 loading 挡路**。
- 超时或异常 → `coachStatus="failed"`，面板显示降级态；**不自动重试超过 1 次**，不形成轮询轰炸。

### A4 教练面板组件
新建 `src/components/coach.js`（保持与现有九个区域组件一致：纯只读渲染、返回 HTML 字符串）。
注册进 `index.html` 的脚本顺序，位置在 `finale.js` **之前**。

渲染三种状态：
| 状态 | 展示 |
|---|---|
| `pending` | 折叠入口标题「教练建议生成中」+ 一个 CSS 呼吸点，**不是骨架、不是转圈遮罩** |
| `ready` | 折叠入口「教练建议 · N 条 · 基于 v{basis_version}」，展开后逐条渲染 |
| `failed` | 「教练建议暂不可用」+ `fail_reason` 原文，旁边一个「重试」小按钮（点了才再发一次） |

面板位置：放在**左栏底部**，作为一个 panel，与「会场纪要与事件」并列。
理由：手册信息密度分级是 中央 > 右栏 > 左栏 > 手牌，教练是复盘素材、不是决策输入，
放左栏符合「不抢焦点」；中央主舞台是全页唯一写入口，不能塞只读面板进去。

**不要**放到终局覆盖层里——那是 `speaker_score` 的地盘，混了评委看不懂。

展开态每条 item 渲染：`kind` 徽标（阶段建议／替代行动）→ `title` → `text` →
`evidence` 列表（`label` + `R{round}` 标记）→ `ap_cost` 非 null 时显示「预计消耗 {n} 行动点」。

### A5 三条硬约束落到代码
1. **默认折叠**：`coachCollapsed` 初始 `true`；首次拿到 `ready` 时**只更新标题上的条数，不自动展开**。
2. **不代替用户决定**：`apply_hint` 只渲染成灰字提示。
   **禁止**实现任何「一键应用建议」的按钮。手牌和条款的改动只能来自用户点击。
3. **不泄露**：实现 1.5 的双重断言。禁用词表放 `src/core/util.js`（复用工具层），至少含：
   `对方红线`、`对方真实`、`对方BATNA`、`真实底线`、`私有`、`net_gain`、`隐藏底牌`。
   命中 → 该条不渲染 + `console.warn("[coach] filtered item:", id, reason)`。

## P1 · 有余力再做（可推到 D8「复盘页面」，不阻断验收）

### B1 证据点击跳转
点 `evidence` 里的 `R{round}` → 切到「对话」视图并滚到该轮消息，或切到报价板并高亮对应条款。
`action_id` 查不到时该条 evidence 不渲染（A5 已覆盖），不要显示「未知来源」。

### B2 把终局硬编码迁到教练产出
删掉 `mockAdapter.js` 约 117–120 行的静态 `keyTurns` / `reviewPoints`，
改为从 `coach.items` 里 `kind="stage"` 的条目派生。
`finale.js` 里加空态：教练未返回时显示「本场未生成复盘要点」，**不得保留现在那两句假文案**。

### B3 「导出复盘记录」去假
现在 `src/app.js:44` 是 `case "exportStory": toast("复盘记录已导出到会话归档（演示态）")`——
点了没真导出。改为导出 `JSON.stringify(DIPLOMAT.snapshot(), null, 2)` 为 `.json` 文件下载
（纯前端 `Blob` + `a.download`，零依赖）。
手册 11.2 要求「演示路径中的所有按钮都有真实作用，不存在点了没有反应的占位控件」。

## Task 2 完成标准（逐条自测，写进 `docs/evidence/t6/` 截图命名）

| # | 验收项 | 通过标准 | 截图 |
|---|---|---|---|
| 1 | 默认折叠 | 刷新后教练面板收起，标题可见条数 | `t6-collapsed.png` |
| 2 | 不阻塞 | DEMO 选 `pending` → 连续改 2 条条款 + 提交成功，全程无禁用无遮罩 | `t6-nonblocking.png` |
| 3 | 失败降级 | DEMO 选 `failed` → 显示原因 + 可点重试；报价板照常可用 | `t6-failed.png` |
| 4 | 不污染状态 | 提交前后 `DIPLOMAT.snapshot()` 里 `round/version/ap` 三项**完全不受教练返回影响** | 两张快照同框 |
| 5 | 不触发时机 | 点「提交本轮总结」后，Network/Console 无教练请求 | `t6-k3-notrigger.png` |
| 6 | 无效证据被过滤 | 手改 mock 让 `action_id="a999999"`（不存在）→ 该条不渲染 + Console 有 warn | `t6-filter.png` |
| 7 | 禁用词被过滤 | 手改 mock 让 `text` 含「对方真实 BATNA」→ 该条不渲染 | `t6-leakfilter.png` |
| 8 | 过期标注 | mock `basis_version=10`、当前 `v12` → 标题显示「基于 v10 的建议」且不消失 | `t6-stale.png` |
| 9 | 双档不破版 | 1440×900 与 1920×1080 下，`DIPLOMAT.measure()` 四项仍全 `true`、无横向滚动 | 两张 Console 截图 |
| 10 | 零回退 | 现有 12 条功能对照（README「功能对照」表）逐条仍通过 | — |

**第 9 条特别重要**：教练面板是新增长度，最可能把 `--h-*` 那套固定高度顶爆。
加完后必须重跑 `docs/acceptance-checklist.md` 第 1 节和第 2 节，不是「看着没滚动」就算过。

---

# Task 3 · 产出给 A 的接口需求（一段可直接转发的文字）

在 `docs/coach-contract.md` 末尾附一节「给 A 的接口需求（可直接转发）」，用第一人称写给 A，
控制在 200 字内，只提请求、不复述方案细节：

必须包含的三句：
1. 你的 `project_snapshot()` 现在返回 9 字段，教练建议没有承载位；请选方案 A（投影加
   `coach_advice` 可选字段）或方案 B（新增 `GET /session/{id}/coach`）。
2. `debrief` 现在返回 202 `{"status":"accepted"}`，我需要知道结果什么时候能取到，
   以及生成失败时怎么告诉我。
3. 顺带确认：`/state` 和 `/action` 的响应里，`speaker_score` 与 `action_points` 到底什么时候补——
   前端已经在读这两个字段（`httpAdapter.js:100`、`:112`），真实接口下它们恒为 undefined，
   终局四维和手牌行动点接真接口后必然是空/0。

**这一节是 D6 最重要的产出物之一**：教练做不完是 D 的问题，但字段没地方放，是必须 A 表态才能推进的事。
不要替 A 决定，只把选择摆清楚。

---

# 今天不要做的事

| 不要做 | 为什么 |
|---|---|
| 改 `httpAdapter` 的默认请求路径去对齐 openapi | 那是「接真实接口」的独立任务，混进来会让这次 diff 不可评审 |
| 实现「一键应用建议」 | 手册 §2.1 明令教练「不得代替用户做决定」 |
| 教练面板自动展开 | 手册完成标准写死「默认折叠，不阻塞下一轮」 |
| 给教练加动画、粒子、转场 | 手册 1.4 明确本轮不做精致动画 |
| 前端本地生成建议文本或打分 | 教练产出由模型侧（B）生成，前端只展示；本地编造等于「把模型内容当事实」 |
| 把教练塞进中央主舞台或终局覆盖层 | 中央是全页唯一写入口；终局是 `speaker_score` 的地盘 |
| 为了「看起来能用」保留 `keyTurns` 那两句硬编码 | 假文案在演示里被追问一句就穿帮，违反手册 11.2 |
| 新增第 7 个错误码 | K2 裁决：6 码外统一 `INVALID_ACTION` 行内红条 + 原文 detail |

# 交付时请一并报告

1. 每个 Task 结束时**停下来等确认**，不要一次做完三个 Task。
2. Task 2 完成后，给出：新增/修改的文件清单（含行数增减）、`coach.js` 的渲染分支数、
   以及验收表 10 条里哪几条已过、哪几条卡在哪。
3. 如果任何一条 P0 做不下去，**直接说明卡点**，不要绕过去用硬编码填上。
4. 保持零依赖、零构建：不引入 npm 包、不引入 `<script type="module">`、不改现有 K/P 注释编号。
````

---

## 给你的三句话备注（不用发给 CodeArts）

1. **今天的真实风险不是代码量，是 P15 还是空的**。`coachAdvice` 在 state-contract §5 只登记了一行占位，
   A 和 B 都没回签。所以 Task 3 那段一定要在今天发出去，否则 D8「复盘页面」你会发现教练面板依然是 mock。
2. **顺手能收的最大收益是 `speaker_score` 和 `action_points`**。这两个字段前端早就在读、真实接口恒缺，
   Task 3 第 3 句是搭教练的便车把这个问题正式提给 A —— 比单开一轮追问省事。
3. **验收第 9 条别跳过**。左栏加面板是这轮唯一会改变整页高度的动作，
   `app.css` 顶部那套 `--h-*` 固定高度一旦被顶爆，双档同屏这个硬验收直接挂，
   而这正是分镜镜头 09 要拍的证据。

# 教练 Agent 字段与时序契约（T6 · 草案 v0.1）

> 用途：定义 `coach_advice` 的字段、类型、触发与取回时序，供 A（会话后端）与 B（场景与模型）评审。
> 状态：**待 A / B 评审，未回签**。评审通过前，前端只按本文件的 mock 形态实现，不假设真实接口已具备。
> 关联：`docs/state-contract.md` §5 的 `coachAdvice` 占位行（P15 未回签）、K7（不泄露）、K5（`speaker_score` 归 A 终局）。
> 命名约定：后端返回 **snake_case**；前端内部转 **camelCase**（映射方式与 `httpAdapter.js:112` 的 `payload.speaker_score → patch.speakerScore` 一致）。

---

## 0. 边界（先写死，后续所有字段都受它约束）

| 教练 Agent 负责 | 教练 Agent 不得负责 |
|---|---|
| 异步分析策略选择 | 阻断每一轮操作 |
| 指出替代行动 | 代替用户做决定 |
| 生成学习反馈 | 改变谈判事实状态（轮次、版本、行动点、条款、终局） |

由此产生三条硬约束，评审时请对照实现检查：

1. **不阻塞**：`coach()` 的 Promise 不进入提交链路的 `await`；pending 期间不禁用任何输入、不加遮罩。
2. **不代替决定**：`apply_hint` 仅渲染为灰字提示，**禁止**任何「一键应用」入口。
3. **不改变事实**：教练数据只写入独立槽位（`coach / coachStatus / coachCollapsed`），**绝不**写 `round / version / ap / clauses / openIssues / ended`。

---

## 1. 字段定义

### 1.1 `coach_advice` 对象结构

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `status` | `"pending" \| "ready" \| "failed"` | 是 | 本次生成的状态。`pending` 时 `items` 必须为空数组 |
| `basis_round` | `number` | `ready` 时必填 | 建议基于哪一轮的状态生成 |
| `basis_version` | `number` | `ready` 时必填 | 生成时的协议版本号，用于判断建议是否已过期 |
| `generated_at` | `string` | `ready` 时必填 | ISO 8601 时间戳 |
| `items` | `array` | 是 | 建议条目，见 1.2。空数组是合法值 |
| `fail_reason` | `string \| null` | 否 | 仅 `status="failed"` 时有值，面向用户的短句，**不是堆栈** |

补充约束：

- `status="pending"`：`basis_round / basis_version / generated_at` 可以缺省；`items` 必须 `[]`；`fail_reason` 必须缺省或 `null`。
- `status="ready"`：`items` 允许 `[]`（模型未产出建议，但生成过程正常），此时前端显示「本轮暂无建议」，**不得**转而显示「生成中」。
- `status="failed"`：`items` 必须 `[]`；`fail_reason` 必填，长度建议 ≤ 30 字。

### 1.2 `items[]` 单条结构

> **A 2026-11-17 回签后，`kind` 以三值 `risk / opportunity / next_move` 为准；下表 `stage / alternative` 为旧口径，待随 §1.6 一起重构。**

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `id` | `string` | 是 | 稳定标识，前端用它做展开态记忆，**不用数组下标** |
| `kind` | `"stage" \| "alternative"` | 是 | `stage` = 阶段建议；`alternative` = 替代行动。两类缺一不可 |
| `title` | `string` | 是 | 不超过 16 字的短标题 |
| `text` | `string` | 是 | 30–90 字，必须指向本轮**具体**条款或行动；禁止「建议加强沟通」这类空话 |
| `evidence` | `array` | 是（可为空数组） | 证据链接，见 1.3。手册完成标准要求「建议引用具体行动」，故此字段为硬性要求 |
| `ap_cost` | `number \| null` | 是 | 替代行动预计消耗的行动点；`stage` 类固定 `null` |
| `apply_hint` | `string \| null` | 否 | 若为 `alternative`，给出可操作入口描述（如「把『复核周期』改为 24 个月」）；**只是提示，前端绝不自动改草稿** |

补充约束：

- `id` 推荐格式 `adv-r{basis_round}-{序号}`，同一 `basis_version` 内唯一；跨版本可重复。
- `kind="stage"` 时 `ap_cost` 必须为 `null`；`kind="alternative"` 时 `ap_cost` 必须是 `0..state.action_points.max` 的整数。
- `text` 中出现的条款名必须与 `state.clauses[].name` 逐字一致。

### 1.3 `evidence[]` 单条结构

| 字段 | 类型 | 含义 |
|---|---|---|
| `kind` | `"action" \| "offer" \| "event"` | 证据类型 |
| `round` | `number` | 发生在第几轮，取值 `1..state.maxRound` |
| `action_id` | `string \| null` | `kind="action"` 时必填，对齐 A 的 `a` + 6 位数字格式（`make_action_id`） |
| `clause` | `string \| null` | 涉及的条款名，必须能在 `state.clauses` 里找到同名项 |
| `label` | `string` | 展示文案，≤ 20 字 |

**证据可溯源是硬要求**：每条 evidence 必须能被前端解析成真实存在对象。

- `kind="action"`：`action_id` 必须命中 `action_history`（或 `state.actions`）中的记录，否则整条 item 无效。
- `clause` 非 `null` 时，必须与 `state.clauses[].name` 有同名项。
- `round` 必须落在 `1..maxRound` 内，且 `round <= basis_round`。

### 1.4 触发与取回时序（**已定：方案 A，A 于 2026-11-17 回签**）

#### 触发（已定，不需要 A 选）

- 时机：`提交本轮报价` 成功、且新状态渲染完成之后。
- 动作：从**提交响应**或 `GET /session/{session_id}/state` 读取 `coach_advice`（A 两处同源，同一 `basis_version` 逐字节一致）。**教练不通过 `debrief` 触发**；`debrief` 只在终局打开时调用一次。
- 约束：
  1. 提交链路**不得 `await`** 该请求；`debrief` 失败不影响提交成功的结果展示与本地状态。
  2. 提交失败分支（`INVALID_ACTION` / `VERSION_CONFLICT` / `TIMEOUT` / `SESSION_BUSY`）**一律不触发**。
  3. 「提交本轮总结」（K3=B）**不触发**教练。
  4. 同一 `basis_version` 只触发一次；同轮重复点击「提交本轮总结」不得重复触发。
  5. pending 期间用户可继续改条款、选卡、提交下一轮，**不允许**任何禁用、遮罩或 loading 挡路。

终局 `debrief` 示例（**教练不走此端点**，仅用于终局复盘）：

```http
POST /session/sess-20261116-01/debrief
Content-Type: application/json

{
  "basis_round": 3,
  "basis_version": 12
}
```

响应示例（现状，已核实）：

```http
HTTP/1.1 202 Accepted
{"status":"accepted"}
```

#### 方案 A（前端倾向）：`coach_advice` 作为投影可选字段

```http
GET /session/sess-20261116-01/state
```

```json
{
  "version": 12,
  "round": 3,
  "action_points": { "current": 3, "max": 5 },
  "open_issues": ["争议仲裁归属", "费用分摊比例"],
  "coach_advice": {
    "status": "ready",
    "basis_round": 3,
    "basis_version": 12,
    "generated_at": "2026-11-16T14:32:08+08:00",
    "items": [],
    "fail_reason": null
  }
}
```

- 优点：不加新端点、不新增轮询；`version` 与建议天然同源。
- **A 2026-11-17 回签**：提交响应也会带回同一份 `coach_advice`，前端可在提交响应或 `GET /state` 二选一读取，两处同一 `basis_version` 逐字节一致。
- 代价：A 要把投影字段从 9 个扩到 10 个，并接受该字段可缺省。
- 缺省语义：`coach_advice` 不存在 → 前端保持「未生成」；存在但 `status="pending"` → 「生成中」。

#### 方案 B：新增 `GET /session/{id}/coach`

```http
GET /session/sess-20261116-01/coach
```

```json
{
  "status": "pending",
  "basis_round": 3,
  "basis_version": 12,
  "generated_at": null,
  "items": [],
  "fail_reason": null
}
```

- 前端退避轮询：`3s → 6s → 12s`，**最多 3 次**；`ready` / `failed` 立即停止；页面切走或终局打开后停止。
- 代价：多一个端点 + 前端要管理轮询生命周期（`coachTimer` 清理、重复触发防护）。

> **本节结论：A 未选定前，`httpAdapter.coach()` 不发请求，返回 `{ ok: true, coach: null }`；前端只走 mock。**

#### 过期规则（两方案通用）

- `basis_version < state.version` → 标题显示「基于 v{basis_version} 的建议」，正文保留，**不自动消失、不闪动**。
- 终局打开（`state.ended === true` 或终局覆盖层打开）后，教练面板冻结，不再刷新、不再请求。

### 1.5 不泄露硬约束（评审重点，照 K7 的做法）

教练 Agent 只能引用**公开事件**：

- `action_history`（双方已生效行动）
- `open_issues`
- 双方的 `public_message`
- `my_offer` / `opponent_offer` 的**已报价条款**

**禁止**引用或暗示：

- 对方 `private_state_by_party`
- 对方红线
- 对方真实 BATNA
- `net_gain`
- 对方隐藏任务完成态

前端必须做**双重断言**（不只是文档约定）：

| 断言 | 规则 | 失败处理 |
|---|---|---|
| 断言 1：证据可溯源 | 逐条校验 `evidence`：`action_id` 在行动账本可查；`clause` 在 `state.clauses` 有同名项；`round` 在 `1..maxRound` 且 `<= basis_round` | 整条 item 不渲染 |
| 断言 2：禁用词 | `title + text` 归一化（去空白、转小写）后命中禁用词表 | 整条 item 不渲染 |

禁用词表（放 `src/core/util.js`，作为工具层单一来源）：

```
对方红线、对方真实、对方BATNA、真实底线、私有、net_gain、隐藏底牌
```

过滤行为：

- 被过滤的 item **静默不渲染**，不弹窗、不打扰用户。
- 控制台打一行：`console.warn("[coach] filtered item:", id, reason)`，`reason ∈ {"evidence", "leak"}`。
- 过滤后若 `items` 全被滤掉，面板显示「本轮暂无建议」，**不回退成「生成中」**。

### 1.6 与 `speaker_score` 的分工（写死，避免混做）

| | `speaker_score` | `coach_advice` |
|---|---|---|
| 回答什么 | 这一局**打了几分** | 下一轮**可以怎么做** |
| 产出时机 | 终局，由 A 的终局端点返回（K5=A） | 每轮提交后，异步 |
| 结构 | 四维分 + `total` + 一句话 `feedback` | `items[]` + `evidence[]` |
| 前端职责 | 只做展示与 S/A/B/C/D 评级映射，**不重算加权** | 只做展示与有效性校验，**不生成、不改写** |
| 首轮特例 | `null` → 显示「本轮未评分」 | 首轮（对方未发言）也应有 `next_move` / `risk` 类建议，**不受 `null` 影响** |
| 展示位置 | 终局覆盖层 | 左栏底部面板（与「会场纪要与事件」并列） |
| 状态字段 | `speakerScore`（已存在） | `coach / coachStatus / coachCollapsed`（新增） |

前端内部命名映射：

| 后端（snake_case） | 前端（camelCase） |
|---|---|
| `coach_advice` | `coach` |
| `status` | `coachStatus` |
| `basis_round` | （留在 `coach.basisRound`） |
| `basis_version` | `coach.basisVersion` |
| `generated_at` | `coach.generatedAt` |
| `items[].ap_cost` | `items[].apCost` |
| `items[].apply_hint` | `items[].applyHint` |
| `items[].action_id` | `items[].actionId`（仅 evidence 内） |

**实现口径（T6 现状）**：前端当前**透传后端 snake_case**（`coach.basis_version` / `items[].ap_cost` / `items[].apply_hint`），组件层直接读取；不额外做 camelCase 映射。原因：A 尚未选定取回方案（A/B），提前重构会让 `sanitize → store → 组件` 三处同时改动，与本轮 diff 混在一起不可评审。A 选定方案后如需统一命名，单独开一次重构。

> 上表是「A 选定取回方案后」的目标口径，不代表 T6 已有实现；以本段现状为准。

**A 2026-11-17 回签（覆盖本节旧口径）**：

- `items[].kind` 只有 `risk / opportunity / next_move` 三值，不再使用 `stage / alternative`；
- `basis_round` 已加；`evidence[]` 已补 `kind / round / label`；`clause` 只在 `clauses[].name` 可查时填；
- `coach_advice` 在提交响应与 `GET /state` 两处同源；
- 前端命名仍透传 snake_case，等 A 定稿后单独开重构（不做 camelCase 映射）。

---

## 2. 完整 JSON 示例

> 示例中的 `kind` 仍是旧值；A 回签后按 `risk / opportunity / next_move` 理解。`evidence` 已按 2026-11-17 回签补齐 `kind / round / label`。

> `round` 与 `clause` 取自 mock 现行数据（`version=12`、`round=3`、条款名与 `mockAdapter.createState()` 一致）。
> `action_id` 仅演示 A 的 `a` + 6 位数字格式；联调时必须能在行动账本中查到，否则该 item 会被前端断言 1 过滤。

```json
{
  "status": "ready",
  "basis_round": 3,
  "basis_version": 12,
  "generated_at": "2026-11-16T14:32:08+08:00",
  "items": [
    {
      "id": "adv-r3-01",
      "kind": "stage",
      "title": "先固定已达成条款",
      "text": "R2 起「监测站点数量」与「数据共享频率」已达成一致，建议先写入附件一固化，再以「联合实验室选址」的 A/B 双址方案换取对方在仲裁条款上的明确表态。",
      "evidence": [
        {
          "kind": "action",
          "round": 2,
          "action_id": "a000137",
          "clause": "监测站点数量",
          "label": "站点数由 5 降至 4"
        },
        {
          "kind": "offer",
          "round": 3,
          "action_id": null,
          "clause": "联合实验室选址",
          "label": "对方报价 B 城"
        }
      ],
      "ap_cost": null,
      "apply_hint": null
    },
    {
      "id": "adv-r3-02",
      "kind": "alternative",
      "title": "用技术援助换折算",
      "text": "若对方坚持费用分摊 60/40，可提出以技术援助折算差额，并把折算表作为附件二，预计用 2 点行动力换取「费用分摊比例」上的口径松动。",
      "evidence": [
        {
          "kind": "action",
          "round": 3,
          "action_id": "a000142",
          "clause": "费用分摊比例",
          "label": "我方提出 40/60 与援助抵差"
        }
      ],
      "ap_cost": 2,
      "apply_hint": "在「费用分摊比例」行把 40 / 60 改为 45 / 55，备注技术援助折算口径"
    }
  ],
  "fail_reason": null
}
```

三种降级形态（同一结构的子集）：

```json
{ "status": "pending", "basis_round": 3, "basis_version": 12, "items": [], "fail_reason": null }
```

```json
{ "status": "failed", "items": [], "fail_reason": "模型暂不可用，请稍后重试" }
```

---

## 3. 需要 A 回答的 3 个问题

1. **取回方案选 A 还是 B？** 方案 A：`project_snapshot()` 投影增加可选字段 `coach_advice`（9 → 10 字段）；方案 B：新增 `GET /session/{id}/coach`，前端退避轮询。两方案示例见 1.4，请只选一个。
2. **投影字段能否加？** 若选方案 A，请确认 `coach_advice` 允许缺省（旧版本无该键）且 `pending` 态也可出现在投影里，不需要额外版本号。
3. **`generated_at` 时区口径？** 请明确返回 UTC（`Z`）还是带偏移（如 `+08:00`）；前端只做展示，不参与过期判定（过期只看 `basis_version`）。

---

## 4. 需要 B 回答的 2 个问题

1. **`text` 的生成 Prompt 由谁写？** 契约只约束长度、条款指向与禁用词，不约束 Prompt 内容。请明确由 B 起草还是 D 起草后交 B 审。
2. **`feedback` 与 `items[].text` 会不会口径重复？** `speaker_score.feedback` 是终局一次性复盘，`items[].text` 是逐轮建议。请确认二者在内容上如何分工，避免终局出现两段近义文字。
---

## 5. 给 A 的接口需求（可直接转发）

> 以下一段可直接复制给 A，不需要附带其他上下文。

A，三件事需要你表态：

1. 你的 `project_snapshot()` 现在返回 9 个字段，教练建议没有承载位。请选方案 A（投影加 `coach_advice` 可选字段）或方案 B（新增 `GET /session/{id}/coach`）。
2. `debrief` 现在返回 202 `{"status":"accepted"}`。我需要知道结果什么时候能取到，以及生成失败时你怎么告诉我。
3. 顺带确认：`/state` 和 `/action` 的响应里，`speaker_score` 与 `action_points` 什么时候补？前端已经在读这两个字段（`httpAdapter.js:100`、`:112`），真实接口下它们恒为 `undefined`，终局四维和手牌行动点接真接口后必然是空/0。

—— D
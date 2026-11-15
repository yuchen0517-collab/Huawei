# Diplomat 状态字段契约（T1 · 评审版 v1）

> 用途：冻结 `index.html` 里散落的 `S` 状态与错误处理，作为 A（会话后端）／B（场景与模型）／C（规则与审计）／D（前端）四方对齐的唯一字段口径。
> 上游依据：`docs/ia-design.md`（信息架构定稿）、`index.html`（第 1 天原型，`S` 定义见 `index.html:731-769`）、`action_schema.json`（行动 JSON Schema）。
> 评审截止：**第 3 天（按 D1=2026-11-11 计，即 2026-11-13）**，需 A、C 在本文第 9 节逐条回签（回签栏见第 10 节）。
> **A 已于 2026-11-13 回签**（结论见第 10 节），相关改动已在 `api.py` 落地且测试通过；待 C 回签后本文升级为 v2 冻结版。
> 本文件只做契约描述，不含实现改动；实现改造在 T2 执行。

---

## 0. 阅读前提（四条已冻结，不再讨论）

1. **字段名以 `index.html` 现状为准，不改名**。现状没有字段的（右栏五块、议题条、左栏四块），本文标为「建议字段名」，**待 A 确认后才成立**，不得当成已定字段直接照抄。
2. **错误响应统一为 `{"error", "detail"}` 形状**；唯一例外：`VERSION_CONFLICT`（409）额外携带 `current_state`（全量状态投影，见 6.3）。**错误码不是 6 码全集**（A 回签修订）：真实全集 = 引擎 17 码 + API 层码（`INVALID_REQUEST`／`INVALID_JSON`／`SESSION_NOT_FOUND` 等），以 `Huawei/API错误码清单.md` 为准。前端只对本文 6 码做专门 UI；其余码一律走行内红条并原文渲染 `detail`（全部为中文人类可读文案），**禁止 else 分支静默**。另：`TIMEOUT` 由前端计时产生（阈值 150 秒，见 P5 回签）；`ROUND_LOCKED` 后端暂不下发，保留码位。
3. **前端不得本地维护业务真值**。`version`／`round`／`ap`／条款 `status` 的唯一真值在服务端；前端本地可写的只有「本次会话的临时交互态」（草稿、选中卡、提交流程标记）。
4. **`version` 一律存整数，展示统一加 `v` 前缀**。顶栏 `#mVer`、报价板 `#bdVer`、协议抽屉 `#drVer`、终局 `#fv` 四处必须渲染同一个 `S.version`（`index.html:806-809`），禁止任何一处持有副本。

---

## 1. 字段总表 A：会话与回合核心

产出方代码：**A** 会话后端／**B** 场景与模型／**C** 规则与审计／**D** 前端本地。

| 字段名 | 类型 | 取值范围 / 枚举 | 产出方 | 前端可写 | 为空 / 默认时的 UI 表现 | 现状依据 |
|---|---|---|---|---|---|---|
| `version` | number（整数） | ≥1；会话内单调递增；当前演示值 `12` | A | **否**，只接受服务端响应回写 | 不可为空。缺失即视为 `VERSION_CONFLICT` 或加载失败，不进 `ready` | `index.html:732`；渲染 `806-809` |
| `serverVersion` | number（整数）\| null | ≥1；仅 `VERSION_CONFLICT` 时非空 | A | **否** | `null` → 冲突条 `#conflictBar` 不渲染；非空 → 显示「本地 v{version}，服务端 v{serverVersion}」+ 草稿处数 | `index.html:739`；`876-880` |
| `round` | number（整数） | `1..maxRound`，当前 `3` | A | **否**，`结束本轮`须走接口 | 不可为空；顶栏渲染 `R{round} / {maxRound}` | `index.html:733`；`805` |
| `maxRound` | number（整数） | 固定 `6`（旧版 15 轮已废弃） | A（会话配置） | 否 | 缺失则 `R{round} / —`，视为配置错误 | `index.html:733`；`805` |
| `ap` | number（整数） | `0..apMax`，当前 `3` | A | **否** | 为 `0` → 手牌全部卡牌 `disabled`，`结束本轮`仍可用 | `index.html:734`；`900`、`907-912` |
| `apMax` | number（整数） | 固定 `5`（旧版 2 点已废弃） | A（会话配置） | 否 | 缺失则行动点不渲染，视为配置错误 | `index.html:734` |
| `phase` | string（枚举） | 现状实现只用 `loading`／`ready`；目标枚举取 ia-design §3 #7 与 §4 状态机并集：`loading`／`ready`／`dirty`／`submitting`／`error`／`conflict`／`degraded`／`locked`／`finale` | D（由 A 的状态 + 本地流程派生） | **是**（仅流程态，不含业务真值） | `loading` → 报价板 5 行骨架行（`839`），手牌禁用；`ready` → 正常渲染 | `index.html:735`；`837-842`、`1184-1193` |
| `modelDown` | boolean | `false`／`true` | B（模型可用性）经 A 以 `MODEL_UNAVAILABLE` 送达 | 是（仅置位标记） | `false` → 左栏解说正常、情报视图正常；`true` → 左栏改降级空态、情报视图改空态，**报价板与预演不变** | `index.html:736`；`1035-1043` |
| `roundLocked` | boolean | `false`／`true` | A（`ROUND_LOCKED`） | 是（仅置位标记） | `false` → 正常；`true` → 顶栏连接灯转红「本轮锁定」、手牌与 `结束本轮` 全禁用、条款 `select` 禁用、接受按钮禁用 | `index.html:737`；`812-813`、`856`、`900`、`913`、`962` |
| `conflict` | boolean | `false`／`true` | D（由 `VERSION_CONFLICT` 派生） | **是**（派生标记，非真值） | `false` → 冲突条隐藏；`true` → 冲突条显示、提交按钮 `disabled`（`890`），必须点「拉取最新并合并」 | `index.html:738`；`875-880`、`890`、`1074-1079` |
| `inlineError` | object \| null | `{error, detail}`，`error` 仅取 6 码 | D（由提交错误响应回填） | 是（仅展示缓存） | `null` → 报价板顶部红条 `#inlineErr` 隐藏；非空 → 顶栏下方行内红条显示错误码 + `detail` | `index.html:740`；`882-887` |
| `inflight` | string \| null | 幂等键字符串；未提交为 `null` | D | 是（流程标记） | `null` → 连接灯「已连接」、提交按钮「提交本轮报价」；非空 → 连接灯「处理中」、全部写入口禁用、按钮「提交中…」 | `index.html:741`；`811-814`、`890-891` |
| `retryKey` | string \| null | 与 `inflight` 同格式；仅 `TIMEOUT`／`VERSION_CONFLICT` 后非空 | D | 是（流程标记） | `null` → 按钮「提交本轮报价」；非空 → 按钮「重试提交（同一笔）」并复用该键 | `index.html:742`；`891`、`972` |
| `demoError` | string \| null | 仅取上表 6 码；**仅演示态使用** | D（DEMO 控制台） | 是 | `null` → 不注入错误；非空 → 下一次提交注入该码。**不得进入生产请求体刊** | `index.html:743`；`1153-1164` |

> **A 回签口径（2026-11-13）**：服务端响应**不直接下发单一全局 `version`**，而是 `my_offer.version`／`opponent_offer.version` 各自递增（`api.py` 的 `latest_offer`）。前端全局 `S.version` = 双方最新版本的最大值；提交时 `base_version` 取该值；`serverVersion` 在 `VERSION_CONFLICT` 时从响应的 `current_state` 中取同口径最大值。`ap`／`apMax` 现状未在状态投影中暴露（引擎为每行动固定 1 点、每轮 3 点、场景可配 `action_points_per_round`），**A 须在第 5 天接真接口前把 `action_points` 补入投影**；契约中 `apMax=5` 的假设随之按场景配置复核。

---

## 2. 字段总表 B：报价、条款与手牌

| 字段名 | 类型 | 取值范围 / 枚举 | 产出方 | 前端可写 | 为空 / 默认时的 UI 表现 | 现状依据 |
|---|---|---|---|---|---|---|
| `draft` | object | `{ [clauseId]: optionString }`；键为 `c1..c5`，值为该条款 `opts` 中的一项 | D（唯一允许前端写的业务草稿） | **是** | `{}` → 草稿徽标 `#draftChip` 隐藏、条款下拉显示 `mine`、提交按钮不禁用（是否允许空草稿提交见开放问题 P7） | `index.html:745`；`823-826`、`845-859` |
| `selectedCard` | string \| null | `k1`／`k2`／`k3`，未选为 `null` | D | **是** | `null` → 预演四格显示「未选择策略卡，按当前报价推演」，行动点显示基准值；非空 → 对应卡高亮、预演联动 | `index.html:744`；`897-904`、`916-934` |
| `clauses` | array（5 条） | 见下表 2.1；固定 5 条，不得增删 | A（条款集与 `mine`／`opts`）＋C（`status`）＋B（`theirs`／`conf`） | 否 | 空数组 → 报价板空态（不得渲染假设条款）；不足 5 条视为数据不完整 | `index.html:746-752` |
| `cards` | array | 见下表 2.2；当前 3 张 | B（场景配置） | 否 | 空数组 → 手牌区空态，`结束本轮`仍可点 | `index.html:753-757` |
| `actions` | object | `{ [idempotencyKey]: {key, round, at, ap} }`；只读账本镜像 | A（真值）／D（本场镜像） | 否 | `{}` → 标签「已记账行动 0 笔」；非空 → 「已记账行动 N 笔」+ 绿色 chip | `index.html:758`；`828-831` |
| `submittedKeys` | object | `{ [key]: true }`；已入账键集合 | A（服务端账本）＋D（前端拦截缓存） | **否**（前端只读，拦截逻辑在适配层） | `{}` → 不拦截；命中 → toast「该行动已记账，未重复提交」且不发起请求 | `index.html:759`；`977-980` |
| `rehearsal` | object | `{react, apCost, riskLevel, basis}`；**必须标注为预演值** | B（反应预测）＋C（风险/依据可信度） | 否 | 未选卡时 `react`「未选择策略卡，按当前报价推演」；任何数值前必须有「预计」或「预演」标注，不得写成实际收益 | 现状为前端硬编码 map：`916-934`（**违规点 V6**） |

### 2.1 `clauses[]` 子字段

| 子字段 | 类型 | 取值 | 产出方 | 前端可写 | 为空时 UI | 说明 |
|---|---|---|---|---|---|---|
| `id` | string | `c1..c5` | A | 否 | — | 与 `draft` 键一一对应 |
| `no` | string | `"01".."05"` | A | 否 | — | 抽屉与未决清单引用编号用 `no` |
| `name` | string | 条款名 | A | 否 | — | 现状 5 条见 `index.html:747-751` |
| `mine` | string | 必须属于 `opts` | A | 否 | — | 我方当前立场，未改动时渲染此值 |
| `opts` | string[] | ≥2 项 | B（场景） | 否 | 空 → 该行下拉不可用并标「选项缺失」 | 控件为下拉，禁止自由输入（ia-design §3 #7） |
| `theirs` | string | 对方立场**估计值**，可为「未表态」 | B | 否 | 空 → 显示「未知」，不得填估造值 | 必须带 `.est-tag`「估计」+ `conf` |
| `conf` | number | `0..100` | B | 否 | 0 → 可信度条空、显示「无」 | 对方数值可信度百分比 |
| `status` | string | `agreed`（已决）／`open`（待确认）／`pending`（未决） | **C** | 否 | — | `pending` 是抽屉接受按钮禁用的唯一依据（`946-961`） |

> 注：条款行的四态「未修改／已修改／非法／锁定」是 **UI 派生态**，不单独落字段：`draft[id]===undefined` → 未修改；`!==undefined` → 已修改；非法由 A 的 `INVALID_ACTION` 反馈；锁定由 `status=agreed` + `roundLocked` 共同表达。

### 2.2 `cards[]` 子字段

| 子字段 | 类型 | 取值 | 产出方 | 前端可写 | 为空时 UI |
|---|---|---|---|---|---|
| `id` | string | `k1`／`k2`／`k3` | B | 否 | — |
| `title` | string | ≤2 行截断 | B | 否 | — |
| `desc` | string | 单行截断 | B | 否 | — |
| `cost` | number | `0..apMax` | B | 否 | 缺失按 `0` 处理但需记录数据缺陷 |

---

## 3. 字段总表 C：右栏、议题条、连接态（**现状无状态字段，均为硬编码 DOM**）

> 本节字段名 **全部是建议名**，现状在 `index.html` 中写死为静态 HTML，不与 `S` 同源。这是「所有数字同源」的现存最大缺口，需 A 确认是否纳入会话状态。

| 建议字段名 | 类型 | 取值 / 枚举 | 产出方 | 前端可写 | 为空时 UI | 现状位置 |
|---|---|---|---|---|---|---|
| `topic.name` | string | 当前议题名 | B（场景） | 否 | 空 → 议题条显示「未选择议题」，中央报价板保持可用 | `index.html:456-459` |
| `topic.index` / `topic.total` | number | `1..6` | B | 否 | 空 → `-- / 06` | `index.html:459` |
| `topic.randomCheck` | string | `pass`／`conflict`／`idle`（ia-design §3 #2）；现状 DOM class 用 `warn` 表示冲突 | C（议题检查） | 否 | `idle` → 灰底「随机议题检查：待检查」 | `index.html:461`；`1142-1150` |
| `us.leverage` | number | `0..100` | A（我方真实值） | 否 | 空 → 显示「—」，**不得填估计值** | `586-588` |
| `us.timePressure` | number + label | `0..100`；文案「低／中／高」 | A | 否 | 空 → 「—」 | `588` |
| `us.gains` | number | ≥0，当前 `2` | A | 否 | 空 → 「0 项」 | `589` |
| `them.concessionIntent` | number | `0..100` | B（估计） | 否 | 空 → 「未知 · 0% 可信」，**不得补值** | `599` |
| `them.decisionChain` | number + unit | 层数 | B（估计） | 否 | 空 → 「未知」 | `600` |
| `them.confidence` | number | `0..100` | B | 否 | 0 → 可信度条空 | `601` |
| `them.lastMove` | string | 如「R2 单向让步」 | B | 否 | 空 → 「无记录」 | `602` |
| `channels[]` | array | `{id, name, status: "ready"｜"cooldown"}`；当前 3 条 | B（渠道清单）＋C（冷却裁决） | 否 | 空 → 渠道区空态「暂无可用渠道」，且选卡后需提示前置不满足 | `607-613` |
| `hiddenTasks[]` | array | `{id, text, done: boolean}`；当前 2 条 | C（任务判定） | 否 | 空 → 「本场无隐藏任务」，**不得隐藏整块** | `616-621` |
| `batna.us` | string | 我方替代方案文本 | A | 否 | 空 → 「未提供」 | `627` |
| `batna.them` | string \| null | **恒为 `null`**；渲染固定「未知 · 无任何可核验线索，不参与推演」 | A（值恒 null） | 否 | `null` → 固定「未知」；**任何情况下不得填估计值伪装为信息** | `628` |
| `conn` | string | `connecting`／`live`／`busy`／`locked` | A（心跳）＋D（派生） | 否 | 未知 → `connecting` 呼吸灯；不得显示为 `live` | `450`；`58-62`、`810-814` |

**突发事件**：现状无独立字段，仅左栏「会场纪要与事件」时间轴写死（`494-500`）。ia-design §7.3 已定「降级为时间轴 + 议题条随机检查」，因此**不新增 `event` 模态字段**；突发事件以 `timeline[]` 条目 + `topic.randomCheck=conflict` 表达。

---

## 4. 字段总表 D：左栏叙事与情报（B 产出，现状硬编码）

| 建议字段名 | 类型 | 产出方 | 前端可写 | 为空 / 降级时 UI | 现状位置 |
|---|---|---|---|---|---|
| `narration.text` | string | B（模型） | 否 | `modelDown=true` → 降级空态「模型不可用 · 战情解说暂无内容」，并注明不影响报价板 | `472`；`1035-1040` |
| `narration.source` | string | B | 否 | 固定「模型生成 · 仅供参考，不作为事实依据」，**不得在截图/导出中裁掉** | `472` |
| `summaryPoints[]` | string[]（3 条） | B | 否 | 空 → 局势摘要空态，不编造要点 | `477-481` |
| `facts[]` | array | B（含 `time/source/verifiable`） | 否 | 空 → 「暂无可核验依据」；单方记录须标「单方记录」，不得与可核验来源混排 | `487-489` |
| `timeline[]` | array | C（按轮次纪要） | 否 | 空 → 「本场暂无纪要」 | `495-500` |
| `intelCards[]` | array | B（估计值）+ 可信度 | 否 | `modelDown=true` → 整视图空态，**不生成替代结论** | `558-563`、`1041-1042` |
| `dialogue[]` | array | B（对话记录） | 否 | 空 → 对话视图空态；输入框保持 `disabled`（对话为复盘素材，不改条款） | `543-552` |

---

## 5. 字段总表 E：教练评分 `speaker_score`

权重与区间**写死**，前端只做展示与评级映射，不重算加权、不新增维度、不自行解释区间。

| 字段名 | 类型 | 取值 | 产出方 | 前端可写 | 为空时 UI | 依据 |
|---|---|---|---|---|---|---|
| `speakerScore` | object \| **null** | 第 1 轮对方未发言时必须为 `null` | C（口径与落库）＋B（模型原始分） | 否 | `null` → 终局评级徽章显示 `—`、文案「首轮不计分：…不填零分，也不生成替代分数」，四维条不渲染 | ia-design §6.1；`index.html:1099-1108` |
| `speakerScore.total` | number（整数） | `0..100`，服务端取整后返回 | C | 否 | — | `index.html:762`；`1111` |
| `speakerScore.position_clarity` | number | `0..100`，权重 30% | C | 否 | — | `1089-1094` |
| `speakerScore.diplomatic_tact` | number | `0..100`，权重 30% | C | 否 | — | 同上 |
| `speakerScore.emotional_control` | number | `0..100`，权重 20% | C | 否 | — | 同上 |
| `speakerScore.substance_quality` | number | `0..100`，权重 20% | C | 否 | — | 同上 |
| `speakerScore.feedback` | string | 20–40 字，先亮点后问题 | B（模型生成，C 审） | 否 | 空 → 显示「本场无文字反馈」，不得套模板编造 | `index.html:767` |
| `coachAdvice` | object \| null | 异步生成、默认折叠、不得泄露对方底牌 | B＋C | 否 | `null`/未返回 → 折叠入口显示「教练建议生成中」，**不阻塞下一轮** | ia-design 约束 7；**现状未实现（缺口 G1）** |

评级映射（前端唯一允许的计算）：`≥90 S`／`70–89 A`／`50–69 B`／`30–49 C`／`0–29 D`（`index.html:1095`）。**禁止**用 `round===1` 反推 `null`（`index.html:1099` 的 `S.round===1 ||` 属于违规点 V5）。

---

## 6. 接口形状

> 端点路径、方法、鉴权方式由 A 提供，本文**不预设内部地址**（约束 13）。以下只冻结「承载项」与「形状约束」；字段名标「待定」的，A 未确认前不得写进代码。

### 6.1 一轮提交请求（必含承载项）

| # | 承载项 | 值来源 | 字段名状态 | 说明 |
|---|---|---|---|---|
| 1 | **幂等键** | `S.inflight`（首次由 `newKey()` 生成，重试复用 `S.retryKey`） | **承载方式待 A 定**：请求体字段或请求头；本文以 `<idempotency-key>` 占位 | 重试必须逐字节相同；不得在合并后换新键 |
| 2 | **`action_id`** | 与幂等键同值（现状 `newKey()` 生成 `act-<ts>-<rand>`） | 名称已定（`action_schema.json`）；「是否与幂等键同值」待 A 确认（P2） | `action_schema.json` 要求 `minLength:1` |
| 3 | **当前 `version`** | `S.version`（提交瞬间快照，不含本次 +1） | **字段名待 A 定**：`version` / `base_version` / `expected_version`（P3） | 服务端据此判 `VERSION_CONFLICT` |
| 4 | **`round`** | `S.round` | **字段名待 A 定**：`round` / `round_no`（P4） | 与 `action_id` 不得互相推导 |
| 5 | **条款变更** | `S.draft` | **形状待 A 定**（P1）：现状键为 `clause.id`（`c1..c5`），`action_schema.offer_patch` 键为议题名且值必含 `note` | 形状不一致会导致后端匹配不到条款 |
| 6 | **所选卡牌** | `S.selectedCard`；未选为 `null` | `card_id`（已定） | 未选卡时按 `null` 传，禁止省略字段 |
| 7 | `actor` | 会话身份 | `actor`（已定） | 国家代码，如 `us` |
| 8 | `action_type` | 由「有无草稿／有无卡牌」推导 | 枚举已定（9 种） | 推导规则待 A 确认（P6） |
| 9 | `conditions` | 现状无 UI 入口 | `conditions`（已定） | 无附加条件传 `[]`，不得缺省 |
| 10 | `expected_effect` / `public_message` | **现状无输入控件** | 名称已定，**来源待 B/A 定**（P8） | Schema 中必填；空串是否合法须明确 |

**A 已回签（2026-11-13）：上表全部「待确认」项已定论**（逐条结论见第 10 节回签栏），请求体最终形状以下列冻结骨架为准，可直接实现：

```json
{
  "client_action_id": "c-20261113-0001",
  "base_version": 3,
  "action_type": "counter_offer",
  "offer_patch": {
    "全球算力资源分配": {
      "option": "采用附带可核查机制的全球算力资源分配方案",
      "note": "我方立场调整为附带可核查机制的分配方案。"
    }
  },
  "conditions": [],
  "expected_effect": "推动对方就核查机制继续磋商。",
  "public_message": "我方提出反报价：愿在可核查机制前提下推进算力资源分配安排。"
}
```

冻结口径（与 `api.py` 已实现行为一致，2026-11-13 测试 44 项全绿）：

- `client_action_id`：必填、非空字符串，请求体承载，会话内唯一；同键重放逐字节返回首次响应，失败不记账、可同键修正后重试。与服务端生成的 `action_id`（`a000001` 递增）**不是同一个值**。
- `base_version`：必填、整数 ≥0，取提交瞬间的全局版本（口径见第 1 节表后注）；不一致 → 409 `VERSION_CONFLICT` 且响应附 `current_state`。
- `offer_patch`：键为**议题名**（前端负责 `c1..c5` → 议题名映射），值必含 `option` + `note`（`note` 由前端生成）；**增量**，非 5 条全量；非报价类行动必须为 `{}`。
- `expected_effect`／`public_message`：UI 无输入框，由前端依据 `draft` 代拟填入，允许模板化短句，不允许缺省。
- **不得传** `action_id`／`actor`／`card_id`（服务端处理，传了也会被剥离）；`card_id` 现阶段服务端强制为 `null`，卡牌结算第 6 天联调再接；`effect_labels` 可选。
- 请求体**不携带 `round`**：轮次由服务端唯一持有，随一轮完整提交自动推进；终局读响应 `status === "ended"`（无 `ended` 布尔字段）。

### 6.2 成功响应的前端最小需求（字段名以 A 定义为准）

前端必须能拿到，否则无法渲染：

1. 新 `version`（整数）；
2. 新 `ap`（整数）；
3. 更新后的 `clauses`（至少 `status` 与对方估计值）；
4. `actions` 账本增量（用于「已记账行动 N 笔」，防止重复记账）；
5. 若本轮结束：新 `round` 与重置后的 `ap`；
6. 终局场景：`speakerScore`（可为 `null`）。

现状 `handleResult` 用本地 `S.version++`、`S.ap-=2`、`S.draft={}` 模拟成功（`index.html:1017-1026`），**这三点 T2 必须迁入 `mockAdapter`**，渲染层不得自增。

### 6.3 错误响应（固定两字段，6 码全覆盖）

统一形状：`{"error": "<code>", "detail": "<说明>"}`。`detail` 文案取自 `index.html:771-778`，评审时与实现逐字对齐。**例外（A 回签新增）**：`VERSION_CONFLICT`（409）在此形状之外额外携带 `current_state` 字段，内容为与 `GET /state` 相同的全量状态投影（含 `my_offer`／`opponent_offer`／`open_issues`），供前端做可视差异与手动合并。

```json
{"error":"INVALID_ACTION","detail":"该行动不满足当前条款约束，未生效。"}
{"error":"SESSION_BUSY","detail":"会话正被另一笔行动占用，请求排队中。"}
{"error":"MODEL_UNAVAILABLE","detail":"解说与情报模型暂不可用，报价板不受影响。"}
{"error":"ROUND_LOCKED","detail":"本轮已锁定，无法再提交行动。"}
{"error":"VERSION_CONFLICT","detail":"客户端版本落后于服务端，需合并后重提。"}
{"error":"TIMEOUT","detail":"上游未在时限内返回，草稿已保留。"}
```

### 6.4 错误码 → 状态字段变更（前端唯一允许的映射）

| 错误码 | 字段变更 | `draft` | 是否重试 | 现状依据 |
|---|---|---|---|---|
| `INVALID_ACTION` | `inlineError={error,detail}`；`inflight=null` | **保留** | 否，用户改条款 | `1006-1008` |
| `SESSION_BUSY` | `inflight=null`；顶栏 `busy`；自动重试 1 次后转手动 | **保留** | 是，**同键** | `985-991` |
| `MODEL_UNAVAILABLE` | `modelDown=true`；`inflight=null` | **保留** | 否 | `1009-1012` |
| `ROUND_LOCKED` | `roundLocked=true`；`inflight=null` | **保留** | 否 | `1013-1015` |
| `VERSION_CONFLICT` | `conflict=true`；`serverVersion=服务端版本`；`retryKey=key` | **保留并计数** | 合并后**同键**重提 | `1001-1005` |
| `TIMEOUT` | `retryKey=key`；`inflight=null` | **保留** | 是，**同键** | `998-1000` |

---

## 7. 一致性不变量（违反即返工）

| # | 不变量 | 判定方式 |
|---|---|---|
| I1 | `#mVer`／`#bdVer`／`#drVer`／`#fv` 文本完全相等 | 三处主位 + 终局一处，同一 `S.version` |
| I2 | 任何错误分支执行后 `Object.keys(S.draft).length` 不变 | 提交前后对比草稿计数 |
| I3 | `submittedKeys[key]` 命中时不发起请求、`actions` 条数不变 | 同一键连点两次，账本仍为 1 笔 |
| I4 | `conflict=true` 时提交按钮 `disabled`，合并后恢复 | 冲突条与按钮态联动 |
| I5 | `modelDown=true` 时条款 `select` 仍可用、提交仍可成功 | 模型故障不阻塞报价 |
| I6 | 存在 `status=pending` 时 `#acceptBtn.disabled === true` 且 `#acceptWhy` 列出编号 | 抽屉打开即判定 |
| I7 | 右栏对方数值全部带「估计」标签 + 可信度；`batna.them` 恒「未知」 | 目视 + DOM 检查 |
| I8 | 预演四格无任何数值被表述为实际收益 | 文案检查「预计／预演」前缀 |

---

## 8. 现状违规点（T1 冻结、T2 处置，作为过程证据）

| # | 现状（改前） | 问题 | 契约要求（改后） | 位置 |
|---|---|---|---|---|
| V1 | 成功分支本地 `S.version++` | 前端自增真值，三处可能不同步 | 只接受适配器返回的新版本 | `1020` |
| V2 | `mergeBtn` 直接 `S.version=S.serverVersion` | 未经差异确认即改写版本 | 合并需显式确认，版本仍由服务端响应落定 | `1075` |
| V3 | `toNew` 本地 `S.version++` 并重置全套状态 | 新会话未走服务端，版本凭空跳号 | 新会话须由 A 初始化并返回初始版本 | `1127` |
| V4 | 成功固定 `S.ap-2`、账本固定 `ap:2` | 与所选卡 `cost`（2／1／0）不一致 | `ap` 扣减以服务端结算为准 | `1019-1021` |
| V5 | `renderFinale` 以 `S.round===1` 推断 `null` | 非首轮的 `null` 会被误判为有分 | 仅以 `speakerScore===null` 判定 | `1099` |
| V6 | 预演四格由前端硬编码 map 生成 | 预计值无服务端来源，违反同源 | 迁入适配层，由 B/C 提供 | `916-934` |
| V7 | 右栏五块、议题条、左栏四块为静态 DOM | 数字不在 `S` 内，无法同源 | 纳入 store 只读渲染 | `456-500`、`584-630` |
| V8 | `endRound` 本地 `round++` 并重置 `ap` | 轮次推进无接口，与服务端必不一致 | 走 A 的「结束本轮」接口 | `1057-1062` |
| V9 | 幂等拦截仅前端 `submittedKeys` | 换端/刷新后重复记账 | 服务端账本二次校验（P2） | `977-980` |
| V10 | `demoError` 与业务状态同处 `S` | 演示注入有混入生产请求风险 | 隔离到 mockAdapter | `743`、`1153-1164` |

---

## 9. 需要 A／C 在第 3 天前确认的开放问题

> 一条一行。A = 会话后端，C = 规则与审计；B 相关项由 D 转达。未回签前，代码一律按「我的默认取值」实现，评审后如不同需返工对应模块。

| ID | 问题 | 我的默认取值 | 如果不同会导致什么 | 需谁定 |
|---|---|---|---|---|
| P1 | `draft` 键用 `clause.id`（`c1..c5`）还是 `action_schema.offer_patch` 的议题名？`note` 由谁填？ | 用 `clause.id`；`note` 由前端按「我方：{option}」拼一句 | 后端按议题名匹配 → 条款变更全部落空，行动被判 `INVALID_ACTION` | A |
| P2 | 幂等键与 `action_id` 是否同一个值？承载在请求体还是请求头？服务端账本以哪个为唯一键？ | 同一个值，承载在请求头 `<idempotency-key>`；服务端以该值为唯一键，同键重放返回首次结果 | 两者不同 → 重试链断裂；服务端不校验 → 刷新后双记账（违反 I3） | A |
| P3 | 提交时当前版本字段名与语义：`version` / `base_version` / `expected_version`？ | `version`，值为提交瞬间的本地版本 | 名称不符 → 冲突检测失效，可能覆盖对方更新 | A |
| P4 | `round` 字段名？`round` 与 `action_id` 是否允许互相推导？ | `round`；不允许推导，独立传 | 后端按解析 `action_id` 取轮次 → 轮次与行动点错配 | A |
| P5 | `VERSION_CONFLICT` 后同键重提，服务端语义是「重放首次结果」还是「视为新行动」？ | 重放首次结果，不新增版本、不重复扣点 | 视为新行动 → 一次操作记两笔，版本跳号 | A |
| P6 | `action_type` 推导规则：仅改条款 / 仅选卡 / 两者都有 / 都没有，各对应哪种枚举？空草稿是否允许提交？ | 改条款 → `counter_offer`；仅选卡 → `probe`；都有 → `conditional_exchange`；都没有 → 禁止提交（渲染为禁用 + 原因） | 规则不符 → 合法操作被判 `INVALID_ACTION`；空提交产生无意义行动 | A |
| P7 | `expected_effect` 与 `public_message` 为 Schema 必填，但 UI 无输入框，由谁产出？允许空串吗？ | 由 B 依据 `draft` 生成；B 不可用时返回 `MODEL_UNAVAILABLE`，不提交半成品 | 无来源 → 请求必然校验失败；允许空串 → 复盘素材缺失 | A＋B |
| P8 | `ap` 扣减口径：按所选卡 `cost`（2/1/0）、按行动类型固定、还是服务端按规则结算？ | 服务端按 `card.cost` 结算，未选卡按 1 点 | 与现状固定 2 点不同 → 预演「行动点消耗」与实际不一致 | A |
| P9 | 「结束本轮」是否必须是接口？跳轮/超时如何处理？ | 走接口，服务端返回新 `round` 与重置后的 `ap` | 前端本地推进 → 服务端轮次滞后，`ROUND_LOCKED` 误判 | A |
| P10 | `clauses[].status` 由谁裁决？`pending` 与 `open` 的边界是什么？ | **C** 裁决：对方已确认为 `agreed`；我方已提出待对方回应为 `open`；双方均未表态或存在冲突为 `pending` | 边界不清 → 抽屉接受按钮该禁不禁，违反 I6 | C |
| P11 | `speakerScore` 的 `null` 触发条件：仅第 1 轮，还是「对方未发言」的任意轮？`total` 是否由服务端取整？ | 任意轮只要对方未发言即 `null`；`total` 服务端取整后返回 | 前端按 `round===1` 推断（现状 V5）→ 非首轮空分被误显示为有分 | C |
| P12 | 右栏五块（我方态势／对方态势／渠道／隐藏任务／BATNA）、议题条、左栏四块是否纳入会话状态接口？字段名能否采用本文建议名？ | 全部纳入，采用本文建议名，前端只读 | 仍为硬编码 → 无法满足「所有数字同源」，复盘数据与服务端不一致 | A＋C |
| P13 | `topic.randomCheck` 枚举用 `pass/conflict/idle` 还是 DOM 现状的 `pass/warn/idle`？ | 数据层用 `conflict`，渲染层映射为 `warn` 样式 | 数据层用 `warn` → 语义与 ia-design 不符，机器不可读 | C |
| P14 | `conn` 由 A 心跳推送还是前端由 `inflight/roundLocked` 派生？是否需要 `connecting` 态？ | A 推送 `live/busy/locked`；`connecting` 由前端在首帧派生 | 仅前端派生 → 真实断连不可见，用户误以为已连接 | A |
| P15 | 教练建议 `coachAdvice` 现状未实现，本轮是否必须补？异步生成的超时与降级如何定义？ | 本轮只保留折叠入口占位，不实现生成链路；超时按 `MODEL_UNAVAILABLE` 降级 | 若要求本轮交付 → 需新增接口与前端模块，影响 T2 排期 | A＋B |

---

## 10. 回签栏

| 角色 | 需确认条目 | 结论（同意／修改意见） | 日期 |
|---|---|---|---|
| A 会话后端 | P1–P9、P12、P14 | **已回签**。P1 用议题名、`note` 由前端生成；P2 独立传输字段 `client_action_id`、请求体承载、会话级去重、同键重放返回首次结果；P3 定名 `base_version`；P4 请求体不传 `round`，服务端 `action_id` 与轮次不互推；P5 同键重放仅对已生效行动返回首次结果，失败不记账；P6 前端显式传 `action_type`：改条款→`counter_offer`、仅选卡→`probe`、都有→`conditional_exchange`、空草稿且无卡→禁止提交；P7 由前端依 `draft` 代拟；P8 引擎现状为每行动固定 1 点、每轮 3 点（场景可配），卡牌差异化扣点未接，`action_points` 投影由 A 在第 5 天前补；P9 轮次随一轮完整提交由服务端自动推进，暂无独立「结束本轮」接口（UI 如需要另提 backlog）；P12 本轮投影以 `api.py` 现状 9 字段为准，右栏五块／议题条／左栏数据由 B 场景提供、A 第 5 天联调前补入投影；P14 无心跳接口，前端本地推断，唯一真实信号 409 `SESSION_BUSY` | 2026-11-13 |
| C 规则与审计 | P10、P11、P12、P13 |  |  |
| B 场景与模型 | 经 D 转达 P7、P12、P15 |  |  |
| D 前端 | 全文 + V1–V10 处置排期 |  |  |

**回签后本文升级为 v2 冻结版；未回签条目在 T2 中按「我的默认取值」实现，并在代码中保留对应 P 编号注释，便于评审后定点返工。**
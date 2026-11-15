# Diplomat 状态字段契约（T1 · v2 合并版）

> 用途：冻结 `index.html` 里散落的 `S` 状态与错误处理，作为 A（会话后端）／B（场景与模型）／C（规则与审计）／D（前端）四方对齐的唯一字段口径。
> 上游依据：`docs/ia-design.md`（信息架构定稿）、`index.html`（第 1 天原型，`S` 定义见 `index.html:731-769`）、`action_schema.json`（行动 JSON Schema）、`state-contract A评.md`（A 的原始回签，含正文批注）。
> 版本状态：**v2 已合并 A 回签 + C 代码口径答复，但尚未冻结**。阻断冻结的是 §0.3 的 K1–K8，需 D 裁决。
> 本文件只做契约描述，不含实现改动；实现改造在 T2 执行。

---

## 0. 阅读前提

### 0.1 评审依据分歧声明（先读，避免误判为“已全员确认”）

| 事实 | 影响 | 处理 |
|---|---|---|
| C 在 `Diplomat_webdemo2.0` 全树未找到 `docs/state-contract.md`（只有 `docs/action_schema.md`、`docs/evaluation.example.json`、`docs/offer_version.md`） | C 的 11 条答复依据的是**代码实际契约**，不是对 v1 全文的逐条确认 | 本文把 C 的 11 条作为「代码事实」回填；**C 仍需拿到本文后复核**右栏五块、议题条、左栏四块、教练建议、字段命名 |
| A 的回签写在根目录 `state-contract A评.md`，正文含批注与冻结骨架 | v1 的 `docs/state-contract.md` 未同步 | 本文为合并版；如与 A 评原文有出入，以 A 评为准并回填 |
| B 未回签 P7／P12／P15 | 模型生成来源未定 | 相关条目保留“未定”，T2 按默认值 mock |

### 0.2 四条冻结（不可改，冲突见 §0.3）

1. **字段名以 `index.html` 现状为准，不改名**；现状没有字段的，本文标「建议名／代码契约名」，待回签后才成立。
2. **错误响应只有 `error` 与 `detail`**，前端契约错误码只有 6 个：`INVALID_ACTION`／`SESSION_BUSY`／`MODEL_UNAVAILABLE`／`ROUND_LOCKED`／`VERSION_CONFLICT`／`TIMEOUT`。后端真实存在更多码，前端**映射而不新增**（见 K2）。
3. **前端不得本地维护业务真值**：`version`／`round`／`ap`／条款状态的真值在服务端；前端只写「临时交互态」。
4. **`version` 存整数、展示加 `v` 前缀**；顶栏 `#mVer`、报价板 `#bdVer`、协议抽屉 `#drVer`、终局 `#fv` 渲染同一个值（`index.html:806-809`）。

### 0.3 冲突裁决表（K1–K8；**K3=B、K5=A 已于 2026-11-13 裁决，其余 6 项按默认值执行**）

> 这些是 A/C 回签与冻结约束的正面冲突。我未擅自改冻结约束，默认值均按冻结口径；若 D 批准变更，改对应一行即可。

| ID | 冲突 | A/C 主张 | 冻结约束 | 我的默认（未裁决时） | 不裁决的后果 |
|---|---|---|---|---|---|
| K1 | `VERSION_CONFLICT` 响应形状 | A：409 额外携带 `current_state` 全量投影 | 错误对象只有 `error`/`detail` | 前端**不依赖** `current_state`，合并数据改从 `GET /state` 拉取 | 若按 A 实现，错误契约出现第三字段，评审可被抓“自造字段” |
| K2 | 错误码全集 | A：真实 17 码 + API 层码，6 码只是专门 UI | 前端错误码仅 6 个 | 其他码**统一映射为 `INVALID_ACTION` 行内红条 + 原文 `detail`**，不新增码、禁止静默 | 若直接把 17 码写进 UI，违反“不新增错误码” |
| K3 | 「结束本轮」按钮 | A：无独立接口，轮次随一轮完整提交自动推进 | UI 必须有「结束本轮」（`index.html:643`）且 `3/3` 可重置 | **D 已裁决 B（2026-11-13）**：按钮文案改为「提交本轮总结」，点击只记录、**不推进轮次**；轮次仅由报价提交推进；同步改 demo-storyboard 镜头 04/06 旁白 | —（已裁决；若不改，按钮语义与 A 接口冲突） |
| K4 | 行动点口径 | A：引擎每行动固定 1 点、每轮 3 点（场景可配），卡牌差异化未接 | 写死上限 5、显示 `3/5` | **D 已裁决 3（2026-11-15）**：引擎/B/默认场景统一 3；UI 改 `3/3`；A 改 `load_scenario_bridge.py` 的 5→3。投影 `action_points.max` 到位后仍以投影为准 | —（已裁决） |
| K5 | `speaker_score` 归属 | C：C 无此字段，只有 `interest/image/trust` 三指数；A 第三轮定 C＋B | 四维权重与五档评级写死，`speaker_score` 必须存在，首轮 `null` | **D 已裁决（2026-11-15）：接受 A 第三轮 C＋B**——C 口径/落库、B 模型分与 `feedback`、A 透传；**D 不生成**。前端只展示；外层 `speakerScore`、内层 snake_case。C 三指数**不得进入 UI 四维条** | —（已裁决；服务端未实现，终局 null） |
| K6 | 条款状态 | C：无 `status` 枚举；`pending/decided` 由 `open_issues` 派生；`locked` 是场景布尔、与两态正交 | 约束 9 用 `status=pending` 禁用接受按钮 | 保留 `status` 作为**前端适配层派生态**，真值来自 `open_issues`；`locked` 单列布尔，不塞进 `status` | 不裁决 → 接受按钮禁用逻辑失去真值依据，或把 locked 当第三态 |
| K7 | BATNA 字段名与泄露 | C：`batna_comparison` 当前未按 viewer 过滤，会把对方真值与 `net_gain` 一起返回；C 承诺改 | 对方 BATNA 恒显示「未知」 | 前端只接收己方 `batna_comparison`（四项全量）；对方视角同一结构**四项全 `null`**（含 `batna`），前端不读取、固定渲染「未知」，并断言对方 `batna` 为 `null` | 不裁决 → 对方 BATNA 真值上屏，违反“机密零泄漏” |
| K8 | `action_schema.json` 与 A 冻结请求体不一致 | A：请求体不传 `action_id`/`actor`/`card_id`，传 `client_action_id`/`base_version` | `action_schema.json` 把 `action_id`/`actor`/`card_id` 列为 **required** | 以 A 的 `api.py` 已测行为为准；**A 必须更新 `action_schema.json`**，否则 B/C 按 schema 生成的行动会被前端适配层丢弃 | 不裁决 → schema 校验与真实接口二选一必然失败 |

---

## 1. 字段总表 A：会话与回合核心

产出方代码：**A** 会话后端／**B** 场景与模型／**C** 规则与审计／**D** 前端本地。

| 字段名 | 类型 | 取值范围 / 枚举 | 产出方 | 前端可写 | 为空 / 默认时的 UI 表现 | 现状依据 |
|---|---|---|---|---|---|---|
| `version` | number（整数） | ≥1；会话内单调递增；演示值 `12` | A | **否** | 不可为空；缺失即视为 `VERSION_CONFLICT` 或加载失败，不进 `ready` | `index.html:732`；`806-809` |
| `serverVersion` | number（整数）\| null | ≥1；仅 `VERSION_CONFLICT` 时非空 | A | **否** | `null` → 冲突条 `#conflictBar` 不渲染；非空 → 「本地 v{version}，服务端 v{serverVersion}」+ 草稿处数 | `index.html:739`；`876-880` |
| `round` | number（整数） | `1..maxRound`，当前 `3` | A | **否**；请求体不传（A 回签 P4）；**仅由报价提交推进，`提交本轮总结`不推进（K3=B）** | 不可为空；顶栏渲染 `R{round} / {maxRound}` | `index.html:733`；`805` |
| `maxRound` | number（整数） | 固定 `6` | A（会话配置） | 否 | 缺失 → `R{round} / —`，视为配置错误 | `index.html:733`；`805` |
| `ap` | number（整数） | `0..apMax`；UI 演示 `3`（K4） | A（`action_points` 投影，第 5 天前补） | **否** | 为 `0` → 卡牌全 `disabled`，`提交本轮总结`仍可用 | `index.html:734`；`900`、`907-912` |
| `apMax` | number（整数） | UI 写死 `3`（K4 裁决）；真实以投影 `max` 为准 | A（会话配置） | 否 | 缺失 → 行动点不渲染 | `index.html:734` |
| `phase` | string（枚举） | 现状只用 `loading`／`ready`；目标取 ia-design §3 #7 与 §4 并集：`loading`／`ready`／`dirty`／`submitting`／`error`／`conflict`／`degraded`／`locked`／`finale` | D（流程派生） | **是**（仅流程态） | `loading` → 报价板 5 行骨架（`839`）、手牌禁用；`ready` → 正常 | `index.html:735`；`837-842`、`1184-1193` |
| `modelDown` | boolean | `false`／`true` | B（经 A 以 `MODEL_UNAVAILABLE` 送达） | 是（仅置位） | `true` → 左栏解说与情报视图空态，**报价板与预演不变** | `index.html:736`；`1035-1043` |
| `roundLocked` | boolean | `false`／`true` | A（**暂不下发** `ROUND_LOCKED`，保留码位） | 是（仅置位） | `true` → 顶栏「本轮锁定」、手牌/提交总结/条款下拉/接受按钮全禁用 | `index.html:737`；`812-813`、`856`、`900`、`913`、`962` |
| `conflict` | boolean | `false`／`true` | D（由 `VERSION_CONFLICT` 派生） | **是**（派生标记） | `true` → 冲突条显示、提交按钮 `disabled`（`890`），必须合并 | `index.html:738`；`875-880`、`890`、`1074-1079` |
| `inlineError` | object \| null | `{error, detail}`；`error` 只取 6 码（K2） | D（由错误响应回填） | 是（仅展示缓存） | `null` → `#inlineErr` 隐藏；非空 → 行内红条显示码 + `detail` | `index.html:740`；`882-887` |
| `inflight` | string \| null | `client_action_id` 字符串；未提交 `null` | D | 是（流程标记） | `null` → 「已连接」+「提交本轮报价」；非空 → 「处理中」+ 全写入口禁用 +「提交中…」 | `index.html:741`；`811-814`、`890-891` |
| `retryKey` | string \| null | 与 `inflight` 同格式；仅 `TIMEOUT`／`VERSION_CONFLICT` 后非空 | D | 是（流程标记） | `null` → 「提交本轮报价」；非空 → 「重试提交（同一笔）」复用同键 | `index.html:742`；`891`、`972` |
| `demoError` | string \| null | 仅 6 码；**仅演示态** | D（DEMO 控制台） | 是 | `null` → 不注入；非空 → 下一次提交注入。**不得进入生产请求体** | `index.html:743`；`1153-1164` |

> **A 回签口径（2026-11-13）**：服务端不下发单一全局 `version`，而是 `my_offer.version`／`opponent_offer.version` 各自递增（`api.py` 的 `latest_offer`）。前端 `S.version` = 双方最新版本最大值；提交时 `base_version` 取该值；`serverVersion` 在冲突时取同口径最大值（来源受 K1 影响）。`ap`／`apMax` 现状未暴露，**A 须在第 5 天前把 `action_points` 补入投影**（K4）。

---

## 2. 字段总表 B：报价、条款与手牌

| 字段名 | 类型 | 取值范围 / 枚举 | 产出方 | 前端可写 | 为空 / 默认时的 UI 表现 | 现状依据 |
|---|---|---|---|---|---|---|
| `draft` | object | `{ [clauseId]: optionString }`；键 `c1..c5`；提交时映射为议题名（A 回签 P1） | D（唯一允许前端写的业务草稿） | **是** | `{}` → 草稿徽标隐藏、下拉回落 `mine`、提交不禁用（空提交见 P6） | `index.html:745`；`823-826`、`845-859` |
| `selectedCard` | string \| null | `k1`／`k2`／`k3`；未选 `null` | D | **是** | `null` → 预演「未选择策略卡，按当前报价推演」；非空 → 卡高亮 + 预演联动 | `index.html:744`；`897-904`、`916-934` |
| `clauses` | array（固定 5 条） | 见 2.1 | A（条款集、`mine`、`opts`）＋B（`theirs`、`conf`）＋C（`open_issues`） | 否 | 空数组 → 报价板空态；不足 5 条视为数据不完整 | `index.html:746-752` |
| `cards` | array | 见 2.2；当前 3 张 | B（场景配置） | 否 | 空 → 手牌空态，`结束本轮`仍可点 | `index.html:753-757` |
| `actions` | object | `{ [clientActionId]: {key, round, at, ap} }` 只读镜像 | A（真值）／D（本场镜像） | 否 | `{}` → 「已记账行动 0 笔」；非空 → 「N 笔」+ 绿色 chip | `index.html:758`；`828-831` |
| `submittedKeys` | object | `{ [clientActionId]: true }` | A（服务端账本）＋D（前端拦截缓存） | **否** | `{}` → 不拦截；命中 → toast「该行动已记账…」且不发请求 | `index.html:759`；`977-980` |
| `open_issues` | string[] | 未决条款**议题名**列表（C 代码契约） | **C** | 否 | `[]` → 接受按钮可用；非空 → 禁用并在上方逐条列名 | C 答复 #7；现状不存在（V11） |
| `rehearsal` | object | `{react, apCost, riskLevel, basis}`；**必须标预演** | B（反应）＋C（风险/依据） | 否 | 未选卡 → 「未选择策略卡，按当前报价推演」；数值前必须有「预计／预演」 | 现状硬编码 `916-934`（V6） |

### 2.1 `clauses[]` 子字段

| 子字段 | 类型 | 取值 | 产出方 | 前端可写 | 为空时 UI | 说明 |
|---|---|---|---|---|---|---|
| `id` | string | `c1..c5` | A | 否 | — | 与 `draft` 键对应 |
| `no` | string | `"01".."05"` | A | 否 | — | 未决清单引用 `no` |
| `name` | string | 条款名 / **议题名** | A | 否 | — | 提交时 `draft` 键映射到此字段（P1） |
| `mine` | string | 必须属于 `opts` | A | 否 | — | 未改动时渲染此值 |
| `opts` | string[] | ≥2 项 | B（场景） | 否 | 空 → 下拉不可用并标「选项缺失」 | 禁止自由输入 |
| `theirs` | string | 对方立场**估计值**，可「未表态」 | B | 否 | 空 → 「未知」，不得填估造值 | 必须带「估计」标签 + `conf` |
| `conf` | number | `0..100`，仅作前端分级输入 | B | 否 | 0 → 显示「未知」 | UI 显示 高/中/低/未知，tooltip 写阈值（C 回 D 2026-11-15） |
| `status` | string（**派生态**） | `pending`（`name ∈ open_issues`）／`decided`（不在列表）；`open`（待确认）**缺真值来源（P16）** | A 适配层派生（真值 C 的 `open_issues`） | 否 | 两条都缺失 → 显示「状态未知」，不得默认 `agreed` | 见 K6；C 明确无 `status` 枚举 |
| `locked` | boolean | 场景锁定（与 `status` 正交） | C／场景 | 否 | `false` → 不显示锁标；`true` → 行内「已锁定」，但**不影响未决判定** | C 答复 #6（`TERM_LOCKED` 是内部码，不上面） |

> 条款行四态「未修改／已修改／非法／锁定」仍是 UI 派生态：`draft[id]===undefined` → 未修改；`!==undefined` → 已修改；非法由 `INVALID_ACTION` 反馈；锁定由 `locked` 或 `roundLocked` 表达，**不塞进 `status`**。

> **状态到 UI 的映射（CSS 类名沿用现状，不改）**：`decided` → `.st-tag.agreed`「已决」；`pending` → `.st-tag.pending`「未决」；`open`（若 A 补真值，P16）→ `.st-tag.open`「待确认」。抽屉未决原因文案固定为「第 {no} 条尚未被任一方报价覆盖」——这是引擎事实（C 答复 #7），**不得改写为业务解释**（V12）。

### 2.2 `cards[]` 子字段

| 子字段 | 类型 | 取值 | 产出方 | 前端可写 | 为空时 UI |
|---|---|---|---|---|---|
| `id` | string | `k1`／`k2`／`k3` | B | 否 | — |
| `title` | string | ≤2 行截断 | B | 否 | — |
| `desc` | string | 单行截断 | B | 否 | — |
| `cost` | number | `0..apMax`；**实际扣点第 6 天联调（K4）** | B | 否 | 缺失按 0 处理并记数据缺陷 |

---

## 3. 字段总表 C：右栏、议题条、连接态

> v1 中这些字段在 `index.html` 全是硬编码 DOM。A 回签 P12：本轮投影以 `api.py` 现状 9 字段为准，右栏五块／议题条／左栏由 **B 场景提供、A 第 5 天联调前补入投影**。因此下列名称仍是**建议名**，未回签前只用于 T2 的 mock 形状。

| 建议字段名 | 类型 | 取值 / 枚举 | 产出方 | 前端可写 | 为空时 UI | 现状位置 |
|---|---|---|---|---|---|---|
| `topic.name` | string | 当前议题名 | B（场景） | 否 | 空 → 「未选择议题」，报价板仍可用 | `456-459` |
| `topic.index` / `topic.total` | number | `1..6` | B | 否 | 空 → `-- / 06` | `459` |
| `topic.randomCheck` | string | `pass`／`conflict`／`idle` | **A（编排层派生，依据 C 的 `warnings[{code,field,message}]`）** | 否 | `idle` → 「随机议题检查：待检查」；`conflict` **不阻塞提交**，仅提示并保留原场景 | C 答复 #10；`461`、`1142-1150` |
| `us.leverage` | number | `0..100` | A（真实值） | 否 | 「—」，**不得填估计值** | `586-588` |
| `us.timePressure` | number + label | `0..100`；「低／中／高」 | A | 否 | 「—」 | `588` |
| `us.gains` | number | ≥0，当前 `2` | A | 否 | 「0 项」 | `589` |
| `them.concessionIntent` | number | `0..100` | B（估计） | 否 | 「未知 · 可信度未知」，**不得补值** | `599` |
| `them.decisionChain` | number | 层数 | B（估计） | 否 | 「未知」 | `600` |
| `them.confidence` | number | `0..100`，仅作前端分级输入 | B | 否 | 0 → 「未知」 | `601`；UI 分级 高/中/低/未知 |
| `them.lastMove` | string | 如「R2 单向让步」 | B | 否 | 「无记录」 | `602` |
| `channels[]` | array | `{id, name, status:"ready"｜"cooldown"}`；3 条 | B（清单）＋C（冷却） | 否 | 空 → 「暂无可用渠道」+ 选卡前置提示 | `607-613` |
| `hiddenTasks[]` | array | `{id, text, done}`；2 条 | C | 否 | 空 → 「本场无隐藏任务」，**不隐藏整块** | `616-621` |
| `batna_comparison` | object | `{batna, achieved, net_gain, better_than_batna}`（C 代码契约） | **C**（按 viewer 裁剪） | 否 | 己方四项可显；**对方视角四项全 `null`**，渲染固定「未知」，前端不做比较、不重算 `net_gain` | K7；C 答复 #9；`624-630` |
| `conn` | string | `connecting`／`live`／`busy`／`locked` | **D（本地推断；A 无心跳接口）** | 是（派生） | 未知 → `connecting`；唯一真实信号 409 `SESSION_BUSY` | A 回签 P14；`450`、`810-814` |

**突发事件**：不新增独立字段。以 `timeline[]` 条目 + `topic.randomCheck=conflict` 表达（ia-design §7.3）。

---

## 4. 字段总表 D：左栏叙事与情报

| 建议字段名 | 类型 | 产出方 | 前端可写 | 为空 / 降级时 UI | 现状位置 |
|---|---|---|---|---|---|
| `narration.text` | string | B（模型） | 否 | `modelDown=true` → 「模型不可用 · 战情解说暂无内容」，注明不影响报价板 | `472`；`1035-1040` |
| `narration.source` | string | B | 否 | 固定「模型生成 · 仅供参考，不作为事实依据」，截图/导出不得裁掉 | `472` |
| `summaryPoints[]` | string[]（3 条） | B | 否 | 空 → 摘要空态，不编造要点 | `477-481` |
| `facts[]` | array（`time/source/verifiable`） | B | 否 | 空 → 「暂无可核验依据」；单方记录标「单方记录」，不与可核验来源混排 | `487-489` |
| `timeline[]` | array（按轮次） | C | 否 | 空 → 「本场暂无纪要」 | `495-500` |
| `intelCards[]` | array（估计值 + 可信度） | B | 否 | `modelDown=true` → 整视图空态，**不生成替代结论** | `558-563`、`1041-1042` |
| `dialogue[]` | array | B | 否 | 空 → 对话空态；输入框保持 `disabled`（对话不改条款） | `543-552` |

---

## 5. 字段总表 E：教练评分 `speaker_score`

权重与区间**写死**：前端只做展示与评级映射，不重算加权、不新增维度、不自行解释区间。

| 字段名 | 类型 | 取值 | 产出方 | 前端可写 | 为空时 UI | 依据 |
|---|---|---|---|---|---|---|
| `speaker_score` | object \| **null** | 对方未发言时必须 `null` | **C（口径/落库）＋B（模型分/feedback），A 透传；D 不生成（K5 2026-11-15）** | 否 | `null` → 徽章 `—` +「首轮不计分…不填零分，不生成替代分数」，四维条不渲染 | ia-design §6.1；`1099-1108` |
| `speaker_score.total` | number（整数） | `0..100`，服务端**取整后**返回 | C（口径/落库） | 否 | — | `762`；`1111` |
| `position_clarity` | number | `0..100`，权重 30% | 同上 | 否 | — | `1089-1094` |
| `diplomatic_tact` | number | `0..100`，权重 30% | 同上 | 否 | — | 同上 |
| `emotional_control` | number | `0..100`，权重 20% | 同上 | 否 | — | 同上 |
| `substance_quality` | number | `0..100`，权重 20% | 同上 | 否 | — | 同上 |
| `speaker_score.feedback` | string | 20–40 字，先亮点后问题 | B（模型生成，C 审） | 否 | 空 → 「本场无文字反馈」，不得套模板编造 | `767` |
| `coachAdvice` | object \| null | 异步、默认折叠、不泄露底牌 | B＋C（**P15 未回签**） | 否 | 未返回 → 折叠入口「教练建议生成中」，**不阻塞下一轮** | ia-design 约束 7；现状未实现 |

**C 口径补充（2026-11-13，采纳为实现细节，不改变字段契约）：**

| 项 | C 口径 | 前端处理 |
|---|---|---|
| 加权与取整位置 | 均在 C（若归 C）；取整用 `round_half_up`（`engine/indices.py:38`），不用 Python 银行家舍入 | 前端拿到已取整 `total`，**不重算** |
| 分档顺序 | **先取整再分档**；左闭右闭；`89.5 → 90 → S` | `gradeOf(total)` 不变：`>=90 S`／`>=70 A`／`>=50 B`／`>=30 C`／否则 `D` |
| 首轮 null | 归 C 则第 1 轮返 `null`；但**现有接口没有该字段**，不能承诺“已返 null” | 只以 `speaker_score === null` 判定，**删除 `round===1` 兜底**（V5） |
| feedback 隐私 | 只读 `public_events` 与己方指数；**禁读** `private_state_by_party`、对方 BATNA、对方红线 | 左栏/终局展示时不追加解释，不推测对方底牌 |
| 三指数 | C 现有 `interest/image/trust`（`engine/state.py:15`） | **不得进 UI 四维条**，不得新增维度（K5） |

---

## 6. 接口形状

> 端点路径、方法、鉴权由 A 提供，本文**不预设内部地址**（约束 13）。以下为 A 已回签的冻结骨架（2026-11-13，`api.py` 44 项测试绿）。

### 6.1 一轮提交请求（A 冻结骨架）

```json
{
  "client_action_id": "c-20261113-0001",
  "base_version": 3,
  "action_type": "counter_offer",
  "offer_patch": {
    "<议题名>": {
      "option": "A 城",
      "note": "我方立场调整为 A 城。"
    }
  },
  "conditions": [],
  "expected_effect": "推动对方就选址继续磋商。",
  "public_message": "我方提议将联合实验室落在 A 城。"
}
```

冻结口径：

| 项 | 规则 | 与 `index.html` 的映射 |
|---|---|---|
| `client_action_id` | 必填非空、请求体承载、会话内唯一；同键重放**逐字节返回首次响应**；失败不记账、可同键修正后重试。与服务端 `action_id`（`a000001` 递增）**不是同一个值** | `S.inflight`／`S.retryKey` 的值 |
| `base_version` | 必填整数 ≥0；取提交瞬间全局版本；不一致 → 409 `VERSION_CONFLICT` | `S.version`（双方最新最大值） |
| `offer_patch` | 键为**议题名**（前端负责 `c1..c5` → `clauses[].name`）；值必含 `option` + `note`（前端生成）；**增量**，非 5 条全量；非报价类行动必须 `{}` | `S.draft` 逐项映射 |
| `action_type` | 前端**显式传**：改条款 → `counter_offer`；仅选卡 → `probe`；都有 → `conditional_exchange`；都没有 → **禁止提交**（按钮禁用 + 原因） | 由 `draft` / `selectedCard` 推导 |
| `expected_effect` / `public_message` | UI 无输入框，由**前端依 `draft` 代拟**，允许模板化短句，不允许缺省。**不是模型生成内容**，不得标“AI 生成” | 前端模板拼装 |
| 不得传 | `action_id`／`actor`／`card_id`（服务端剥离）；`card_id` 现阶段强制 `null`，卡牌结算第 6 天联调 | `S.selectedCard` 暂只用于预演 |
| 不传 `round` | 轮次由服务端唯一持有，随一轮完整提交自动推进；终局读响应 `status === "ended"` | `S.round` 只读展示 |
| 约束 | `action_schema.json` 与上表不一致（K8），**A 需更新 schema** | — |

### 6.2 成功响应的前端最小需求

1. 新 `version`（整数，取双方最大值）；
2. 新 `ap`（整数，来自 `action_points` 投影）；
3. 更新后的 `clauses`（`status` 派生所需字段 + 对方估计值）；
4. `actions` 账本增量；
5. 若轮次推进：新 `round`（响应提供，请求不传）；
6. 终局：`speaker_score`（可 `null`）、`status`（`"ended"`）、`audit`；
7. `open_issues`（string[]，用于接受按钮禁用）。

现状 `handleResult` 用本地 `S.version++`、`S.ap-=2`、`S.draft={}` 模拟成功（`index.html:1017-1026`），**T2 必须迁入 `mockAdapter`**。

### 6.3 错误响应

统一形状 `{"error": "<code>", "detail": "<说明>"}`，前端契约只认 6 码。`detail` 必须是人类可读中文，且 `INVALID_ACTION` 的 `detail` 须包含**条款名与原因**（C 答复 #11：C 返回 `(ok, code, message)`，A 原样放入 `detail`；前端不解析结构化 `clause` 字段）。

```json
{"error":"INVALID_ACTION","detail":"该行动不满足当前条款约束，未生效。"}
{"error":"SESSION_BUSY","detail":"会话正被另一笔行动占用，请求排队中。"}
{"error":"MODEL_UNAVAILABLE","detail":"解说与情报模型暂不可用，报价板不受影响。"}
{"error":"ROUND_LOCKED","detail":"本轮已锁定，无法再提交行动。"}
{"error":"VERSION_CONFLICT","detail":"客户端版本落后于服务端，需合并后重提。"}
{"error":"TIMEOUT","detail":"上游未在时限内返回，草稿已保留。"}
```

**K1／K2 落地规则（未裁决前）：**

| 情况 | 前端行为 |
|---|---|
| 409 `VERSION_CONFLICT` 额外带 `current_state` | **忽略该字段**；合并数据从 `GET /state` 拉取。若 D 批准 K1，改为读 `current_state` 并同步更新本条 |
| 响应 `error` 不在 6 码内（如 `TERM_LOCKED`／`AGREEMENT_HAS_OPEN_ISSUES`） | 统一进 `inlineError`，码位显示 `INVALID_ACTION`，`detail` **原样渲染**；禁止 `else` 静默。`AGREEMENT_HAS_OPEN_ISSUES` 的 `message` 已列条款名，直接展示 |
| `TIMEOUT` | 由前端计时产生，阈值 **150 秒**（A 回签）；`index.html` 的 900ms 仅 mock |
| `ROUND_LOCKED` | 后端暂不下发，前端保留码位与禁用逻辑 |

### 6.4 错误码 → 状态字段变更（前端唯一允许的映射）

| 错误码 | 字段变更 | `draft` | 是否重试 | 现状依据 |
|---|---|---|---|---|
| `INVALID_ACTION` | `inlineError={error,detail}`；`inflight=null` | **保留** | 否，用户改条款 | `1006-1008` |
| `SESSION_BUSY` | `inflight=null`；顶栏 `busy`；自动重试 1 次后转手动 | **保留** | 是，**同键** | `985-991` |
| `MODEL_UNAVAILABLE` | `modelDown=true`；`inflight=null` | **保留** | 否 | `1009-1012` |
| `ROUND_LOCKED` | `roundLocked=true`；`inflight=null` | **保留** | 否 | `1013-1015` |
| `VERSION_CONFLICT` | `conflict=true`；`serverVersion=同口径最大值`；`retryKey=key` | **保留并计数** | 合并后**同键**重提 | `1001-1005` |
| `TIMEOUT` | `retryKey=key`；`inflight=null` | **保留** | 是，**同键** | `998-1000` |

### 6.5 接受协议响应（C 的审计形状）

C 的 `audit_agreement` 返回（`agent/audit/auditor.py:45-57`、`138-142`），A 原样放进 accept 响应的 `audit` 字段，**不单开接口**：

```json
{
  "audit": {
    "ok": false,
    "issues": [
      {"check": "clause_coverage", "severity": "blocking", "message": "条款「争议仲裁归属」尚未被任一方报价覆盖。", "clause": "争议仲裁归属", "party": null}
    ],
    "summary": {"blocking": 1, "warning": 0}
  }
}
```

前端规则：`summary.blocking > 0` → 接受按钮 `disabled`，在按钮上方逐条显示 `message`；**不新建审计面板**（范围锁定）。`open_issues` 为空但 `audit.blocking` 非空时，以 `audit` 为准并提示「存在阻塞项」。

### 6.6 「提交本轮总结」语义（K3=B，已裁决 2026-11-13）

A 回签：无独立「结束本轮」接口，轮次随一轮完整提交自动推进；请求体不传 `round`。D 裁决：**不新增接口、不改轮次口径**，按钮改为「提交本轮总结」。

| 项 | 冻结行为 |
|---|---|
| 按钮文案 | `#endRound` 由「结束本轮」改为「提交本轮总结」（`index.html:643`） |
| 点击行为 | 只写入一条总结记录（进入对话/纪要视图，作为复盘素材）；**不调用报价提交接口、不推进 `round`、不扣 `ap`** |
| 草稿 | `draft` 非空时只 toast 提示「草稿仍保留」，不清空、不回滚；**不弹 `window.confirm`**（避免录屏入镜） |
| 轮次推进 | 仅由「提交本轮报价」成功推进；推进后的 `round`/`ap` 由服务端响应刷新 |
| 失败 | 总结写入失败必须有提示，不得静默（T3 交互态） |
| 演示 | Demo 镜头 04/06 旁白按 `demo-storyboard.md` 的 K3 备注执行；若需保持 `R3/6`，先点 DEMO「复位场景」 |

---

## 7. 一致性不变量（违反即返工）

| # | 不变量 | 判定方式 |
|---|---|---|
| I1 | `#mVer`／`#bdVer`／`#drVer`／`#fv` 文本完全相等 | 同一 `S.version` |
| I2 | 任何错误分支后 `Object.keys(S.draft).length` 不变 | 提交前后对比 |
| I3 | 命中 `submittedKeys[clientActionId]` 时不发请求、`actions` 条数不变 | 同键连点两次，账本仍 1 笔 |
| I4 | `conflict=true` 时提交按钮 `disabled`，合并后恢复 | 冲突条与按钮联动 |
| I5 | `modelDown=true` 时条款下拉仍可用、提交仍可成功 | 模型故障不阻塞报价 |
| I6 | `open_issues.length > 0` 或 `audit.summary.blocking > 0` 时 `#acceptBtn.disabled === true`，且上方列出条款名 | 抽屉打开即判定 |
| I7 | 右栏对方数值全部带「估计」+ 可信度分级（高/中/低/未知），tooltip 写阈值；对方视角 `batna_comparison` 四项全 `null` 且显示「未知」 | 目视 + DOM 断言 |
| I8 | 预演四格无任何数值被表述为实际收益 | 文案检查「预计／预演」 |
| I9 | 6 码以外的响应不静默：必进行内红条并原文展示 `detail` | 注入 `TERM_LOCKED` 验证 |
| I10 | 前端四维条只读 `speaker_score` 四项，不出现 `interest/image/trust` | DOM 检查 |

---

## 8. 现状违规点（T2 处置，过程证据）

| # | 现状（改前） | 问题 | 契约要求（改后） | 位置 |
|---|---|---|---|---|
| V1 | 成功分支本地 `S.version++` | 前端自增真值，三处可能不同步 | 只接受适配器返回的新版本 | `1020` |
| V2 | `mergeBtn` 直接 `S.version=S.serverVersion` | 未经差异确认即改写版本 | 合并需显式确认，版本由服务端落定 | `1075` |
| V3 | `toNew` 本地 `S.version++` 并重置全套状态 | 新会话未走服务端，版本跳号 | 新会话须由 A 初始化返回版本 | `1127` |
| V4 | 成功固定 `S.ap-2`、账本固定 `ap:2` | 与所选卡 `cost`（2/1/0）及引擎 1 点都不一致 | `ap` 扣减以服务端结算为准 | `1019-1021` |
| V5 | `renderFinale` 以 `S.round===1` 推断 `null` | 非首轮 `null` 被误判为有分 | 仅以 `speaker_score===null` 判定 | `1099` |
| V6 | 预演四格前端硬编码 map | 预计值无服务端来源 | 迁入适配层，B/C 提供 | `916-934` |
| V7 | 右栏五块、议题条、左栏四块为静态 DOM | 数字不在 `S` 内 | 纳入 store 只读渲染 | `456-500`、`584-630` |
| V8 | `endRound` 本地 `round++` 并重置 `ap` | 轮次推进无接口 | 走 K3 裁决方案 | `1057-1062` |
| V9 | 幂等仅前端 `submittedKeys` | 换端/刷新后重复记账 | 服务端以 `client_action_id` 会话级去重 | `977-980` |
| V10 | `demoError` 与业务状态同处 `S` | 演示注入有混入生产风险 | 隔离到 mockAdapter | `743`、`1153-1164` |
| V11 | `status` 三态（agreed/open/pending）由 HTML 硬编码 | C 无 `status` 枚举，只有 `open_issues` | 适配层派生 `decided/pending`；`open` 待 P16 | `746-752` |
| V12 | 抽屉未决原因写死「需先决出或明确写入附件保留」 | C 的事实原因只有「尚未被任一方报价覆盖」 | 原因文案改为引擎事实，不编业务原因 | `952-956` |

---

## 9. 开放问题与回签结论

> 一条一行。A = 会话后端，C = 规则与审计，B = 场景与模型。**结论列写“未回签”的，T2 按默认值实现并留 P 编号注释。**

| ID | 问题 | 我的默认 | 结论（A/C 回签） | 剩余动作 |
|---|---|---|---|---|
| P1 | `draft` 键用 `clause.id` 还是议题名？`note` 谁填？ | `clause.id`；`note` 前端拼 | **A 定：提交键用议题名，前端负责 `c*`→议题名映射；`note` 前端生成** | T2 适配层加映射 |
| P2 | 幂等键与 `action_id` 同值？承载位置？ | 同值、请求头 | **A 定：`client_action_id` 独立字段、请求体承载、会话级去重、同键重放返回首次结果；与服务端 `action_id` 不同值** | 更新 T2 `httpAdapter` |
| P3 | 版本字段名 | `version` | **A 定：`base_version`** | 同上 |
| P4 | `round` 字段名 | `round` | **A 定：请求体不传 `round`；服务端持有并随提交推进** | 前端只读展示 |
| P5 | 冲突后同键重提语义 | 重放首次结果 | **A 定：仅对已生效行动返回首次结果；失败不记账，可同键修正重试；`TIMEOUT` 由前端 150s 计时** | T2 落地重试链 |
| P6 | `action_type` 推导 / 空提交 | 见 v1 默认 | **A 定：改条款→`counter_offer`；仅选卡→`probe`；都有→`conditional_exchange`；都没有→禁止提交** | 按钮禁用 + 原因 |
| P7 | `expected_effect`/`public_message` 来源 | B 生成 | **A 定：前端依 `draft` 代拟；B 未回签** | T2 模板化生成，标“非模型生成” |
| P8 | 行动点扣减 | 按卡 cost | **A 定：引擎每行动固定 1 点、每轮 3 点（场景可配），卡牌差异化未接；第 5 天补 `action_points` 投影** | 见 K4 |
| P9 | 结束本轮接口 | 走接口 | **A 定：无独立接口，随完整提交推进** | 见 K3 |
| P10 | `status` 裁决与 `pending/open` 边界 | C 三态 | **C 定：无 `status` 枚举；`pending/decided` 由 `open_issues` 派生；`locked` 是场景布尔、与两态正交；无 `waived`** | 见 K6；P16 补 `open` |
| P11 | `speaker_score` 的 `null` 与取整 | 服务端取整 | **C 定：C 不产出该字段；若归 C 则仅终局一次、第 1 轮 `null`；加权与 `round_half_up` 取整在 C；先取整再分档、左闭右闭** | 见 K5 |
| P12 | 右栏/议题/左栏是否入投影 | 全部纳入 | **A 定：本轮投影以 `api.py` 9 字段为准；右栏/议题/左栏由 B 提供，A 第 5 天前补入。C 未答** | T2 用 mock；联调前复核 |
| P13 | `randomCheck` 三态 | `pass/conflict/idle` | **C 定：C 只有 adapter `warnings{code,field,message}`；三态在 A 编排层派生；`conflict` 不阻塞** | 已采纳，A 负责派生 |
| P14 | `conn` 来源 | A 推送 | **A 定：无心跳接口；前端本地推断；唯一真实信号 409 `SESSION_BUSY`** | 已采纳 |
| P15 | `coachAdvice` 是否本轮补 | 只留占位 | **未回签（A 未答，B 未回）** | T2 只做折叠占位 |
| P16 | `open`（待确认）态的真值来源 | 不出现该态，只显示 `decided/pending` | **未回签** | 需 C 或 A 给派生规则；否则 T2 mock 保留三态仅为视觉 |
| P17 | K1 `current_state` 是否进入错误契约 | 不进入 | **待 D 裁决** | 裁决后改 6.3 |
| P18 | K5 `speaker_score` 由谁产出 | A 终局端点 | **D 裁决（2026-11-15）：接受 C＋B，A 透传，D 不生成** | 前端只展示；服务端未实现，终局 null |
| P19 | K3 结束本轮按钮语义 | `statement` 空变更 | **D 裁决 B：改为「提交本轮总结」，只记录不推轮次；轮次仅由报价推进** | 改 `#endRound` 文案 + §6.6 + demo-storyboard 04/06 |
| P20 | K4 真实行动点 3 点 vs UI 5 点 | UI 维持 5，联调按投影 | **D 裁决 3（2026-11-15）**：UI/mock 改 `3/3`；A 改 bridge 5→3 | 已改 mock/空态；待投影补入 |

---

## 10. 回签栏

| 角色 | 需确认条目 | 结论 | 日期 |
|---|---|---|---|
| A 会话后端 | P1–P9、P12、P14 | **已回签**（原文见 `state-contract A评.md`；结论已合并至 §9） | 2026-11-13 |
| C 规则与审计 | P10、P11、P12、P13 | **部分回签**：11 条代码口径已答复并合并；**未读到本文件**，右栏/左栏/教练建议/字段命名待复核 | 2026-11-13 |
| B 场景与模型 | 经 D 转达 P7、P12、P15 | **未回签** | — |
| D 前端 | 全文 + K1–K8 裁决 + V1–V12 处置 | **已裁决 K3=B、K5=A（2026-11-13）**；K1/K2/K4/K6/K7/K8 按默认值执行 | 2026-11-13 |

---

## 11. 下一步（不自动执行）

1. **K3=B、K5=A 已裁决并落地**（§6.6、§5、`demo-storyboard.md` 镜头 04/06）；K1/K2/K4/K6/K7/K8 按 §0.3 默认值执行，T2 代码留 K 编号注释。
2. C 拿到本文件后只复核 4 处：右栏五块、议题条、左栏四块、教练建议；其余 11 条已按其代码口径回填。
3. B 回 P7／P12／P15，否则 T2 的 `mockAdapter` 继续用第 1 天文案。
4. K 与 P 全部有结论后，本文升 v3 冻结版，再开 T2。
---

## 12. A 答复同步（2026-11-15）

> 依据：`A答复C接口问题_2026-11-15.md`。与本契约冲突处，以 A 答复为准；已在适配层落地（T3）。

| 项 | A 结论 | 前端落地 |
|---|---|---|
| G1 session | `session_id` 在 **path**；开局 `POST /session` → `session_id` + 全量投影；`GET /session/{id}/state`、`POST /session/{id}/action`、`POST /session/{id}/debrief` | `httpAdapter.withSession()` 唯一拼 path；`openSession()` 开局 |
| G4 键名 | `offer_patch`、`open_issues`、`my_offer.offers` 全部用**议题名** | `toOfferPatch` 已是议题名；id 仅本地草稿键 |
| K1 | 409 `VERSION_CONFLICT` 保留 `current_state` | 提交响应存 `currentState`，合并时优先整棵替换；缺失才 `GET /state` |
| G2 | 400/404/405/409/422/500/503 统一 `{error, detail}`；500=`INTERNAL_ERROR`；404=`SESSION_NOT_FOUND`；409 `SESSION_BUSY` 自动重试 1 次同键；503 `MODEL_UNAVAILABLE` 业务降级 | 6 码业务 UI；非 6 码行内红条原文 detail；网络/5xx/非 JSON 走服务不可用通道；404 显示会话失效并可重新开局 |
| 鉴权 | 当前无；前端不需要注入密钥 | `buildHeaders()` 仅 Content-Type，留 TODO |
| CORS | `api.py` 已配 `allow_origins=["*"]` | 前端不处理 |
| G5/G6/G7 | 无 summary/reset/topic 接口；summary=`debrief` 202；reset=重新 `POST /session`；切题=重开一局 | `summary` 处理 202 受理；`reset` 重新开局；`nextTopic/randomCheck` 明确提示不支持 |

**仍未回签**：P15 教练建议、P16 `open` 态；B 的 P7/P12/P15。P20（K4）已于 2026-11-15 裁决为 3。
---

## 13. A 第二轮答复同步（2026-11-15）

> 依据：`A答复C接口问题_2026-11-15_第二轮.md`。与本文冲突处，以第二轮为准；已在 T3 收口中落地。

| 项 | 结论 | 前端落地 |
|---|---|---|
| accept | `POST /session/{id}/action`，`action_type:"accept"`，`offer_patch:{}`，`expected_effect/public_message` 必填；未决时 400 `INVALID_ACTION`；终局读 `status:"ended"` | `httpAdapter.accept()`；store 同键重试仅 1 次；成功后按投影开终局 |
| 条款 options | 投影固定 9 字段，**暂无 options**；计划补 `clauses[{name,type,options,initial}]`；过渡按场景静态映射 | `projectState` 优先 `payload.clauses`，其次 `CONFIG.clauseOptions`，最后现有 opts |
| action_points | 投影未暴露；计划 `{current,max}`；未补入前每轮 3 点、每行动 1 点；`apMax=5` 旧假设作废 | 已裁决 K4=3：mock/空态 `3/3`；投影存在时以 `max` 覆盖 |
| speaker_score | 服务端未实现；终局 null 态 | 不本地算分，不填零 |
| debrief | 202 纯受理，无复盘/教练内容 | 提示已受理，内容不返回 |
| 开局 | `{scenario_id:"ai_governance", agent:"us", scenario_path:null}`；agent 仅 `us` | `openSession` 默认；可配置覆盖 |
| offers | 只含 `option` + `note`，不含 options | 只读；选项来源为 `clauses`/`clauseOptions` |
| 500 | `INTERNAL_ERROR` 按服务不可用、不重试、保留草稿 | G2 通道 |

**C 已澄清（2026-11-15）**：单数 `accept_requires_no_open_issue` 是 B 契约的正式字段名（`scenario.schema.json` required），复数 `accept_requires_no_open_issues` 是 C 引擎内部键名；C 适配层已双读兼容（单数优先，同时出现且冲突时报契约错误），B 真实场景实测可正常进引擎。**前端不读该字段**（只消费 A 的 API 投影），无需处理本项。

**仍需第 5 天前补入投影**：条款 `options` 与 `action_points`。
---

## 14. A 第三轮答复同步（2026-11-15）

> 依据：`A答复C接口问题_2026-11-15_第三轮.md`。与本文冲突处，以第三轮为准。

| 项 | 结论 | 前端落地 |
|---|---|---|
| clauses 形状 | 冻结 enum `{name,type,options,initial}` 与 numeric `{name,type,unit,range{min,max,step},initial}`；11-16 上午联调前补入 | `clauseFrom()` 支持两种；numeric 渲染数值输入，`setDraft` 按数值比较 |
| action_points | `{current,max}`；每行动扣 1、每轮重置 max；max 取场景 `action_points_per_round` | 投影存在才覆盖 `ap/apMax` |
| K4 | 默认 `ai_governance` 线上实际 5（bridge 硬编码），引擎/B/默认场景为 3；**D 已裁决 3（2026-11-15）** | mock/空态改 `3/3`；A 改 bridge 5→3；投影到位后以 `max` 为准 |
| speakerScore | 产出方 **C（口径/落库）＋B（模型分/feedback），A 透传，不由 D**；外层 camelCase `speakerScore`，内层 snake_case；当前未实现，终局 null | `projectState` 优先 `payload.speakerScore`，兼容 `speaker_score`；前端只展示 |
| C 单复数 | 第三轮附 4 仍列待确认；C 已于 2026-11-15 澄清为跨模块命名差异，适配层双读，不是 bug | 前端不读该字段 |

> **K5 已确认（2026-11-15）**：接受 A 第三轮 C＋B（C 口径/落库、B 模型分/feedback、A 透传，D 不生成）；§5 与 §9 P18 已同步。前端只展示，无本地评分。
---

## 15. C 回 D：可信度定性分级（2026-11-15）

| 项 | 结论 |
|---|---|
| 展示 | 右栏对方态势、报价板对方列、情报卡的可信度只显示「高／中／低／未知」，**不显示百分比** |
| 规则 | 高 ≥70；中 40–69；低 1–39；未知：null／0／无数据 |
| 归属 | **D 前端按透明规则推导**；非业务真值，不影响数字同源（金额/版本/评分仍全来自服务端） |
| 审计 | 规则写入 tooltip，可截图；C 零改动 |
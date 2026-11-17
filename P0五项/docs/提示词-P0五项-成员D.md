# P0 五项 · 提示词包（成员 D 自办部分）

> 用途：把 P0 五项逐个拆成「可以直接粘给 AI 执行」的任务卡。
> 范围：**只覆盖成员 D 能独立推进的前端部分**。依赖 A（后端判定/契约）或 B（卡池数据）的，统一放在第五节，先不写提示词。
> 生成日期：2026-11-17 ｜ 对应差距分析：`docs/谈判页差距对比-纪要v2.md`

---

## 一、怎么用这份包

1. **一次只发一张卡**。发之前把上一张的验收跑完，界面回到干净状态再发下一张，否则 AI 会把两处改动混在一起，出问题说不清是谁的锅。
2. **每张卡都要带第二节的「通用上下文头」**。新会话的 AI 不知道这个项目长什么样，省掉这段它会自己造组件、装依赖、改主题。
3. **卡 0 必须先做**。卡 2～卡 5 都要读条款表，没有卡 0 它们只能各自 mock 一份数据，最后对不上。
4. 每张卡末尾都有「验收」和「禁止」，**不要删**。验收是给自己留证据的，禁止是防 AI 顺手重构的。
5. 卡做完，界面截图丢进 `Diplomat-components(1)/docs/evidence/`，文件名按 `p0-<编号>-<档位>.png`。

---

## 二、通用上下文头（每条提示词开头都粘这段）

```text
【项目上下文】
项目：Diplomat 外交谈判智能体 · 前端 Demo，我是成员 D（负责 UI / 教练 Agent / Demo 统筹）。
目录：D:/STUDY/研究生/华为云/11.11/Diplomat-components(1)
技术栈：原生 ES Module，组件是「返回 HTML 字符串的函数」，无框架、无状态库；Vite 构建；
        另有 build-single.mjs（esbuild IIFE + 图片内联）产出双击即开的单文件版。

代码地图：
- src/main.js            渲染入口：render* 函数 + 事件委托（data-action 属性）
- src/stores/NegotiationStore.js  唯一状态容器，所有方法是同步的，只改 this.state
- src/domain/negotiation.js       topic 配置、strategyCatalog（策略卡）、createInitialNegotiation()
- src/domain/clauses.js          （卡 0 新建）条款表
- src/components/*.js            展示函数，输入 state 返回 HTML 字符串
- src/services/{adapter,idempotency,coach}.js  提交适配器 / 幂等 / 教练

已经通过验收、不许动的部分：
1. 提交链路是「prepareTurn → adapter.submitAction → applyTurn」三段式，失败只调 failSubmit，草稿（selectedIds）必须保留。
2. 六个错误码（INVALID_ACTION / SESSION_BUSY / MODEL_UNAVAILABLE / ROUND_LOCKED / VERSION_CONFLICT / SESSION_ENDED）
   各有独立 UI 分支，横幅在 #errorSlot。
3. 协议版本号在三处显示且必须一致：顶栏 .version-chip、手牌区 .action-points 内、谈判树抽屉 header。
4. 教练面板独占 coach / coachStatus / coachCollapsed 三个槽位，默认折叠，异步不阻塞，绝不改谈判事实。
5. 双档 1440×900 与 1920×1080 均不得出现横向滚动。

硬约束：
- 不引入任何新依赖（不许 npm i react / zustand / 任何 UI 库）。
- 新增状态一律进 store.state，不许挂在模块级变量或组件闭包里。
- 所有插入 DOM 的可变文本必须过 escapeHTML。
- 面板一律默认折叠，不许抢焦点、不许盖住会场主流程。
- 改完必须两条构建都过：vite build 通过 + build-single.mjs 产出单文件版不白屏。
```

---

## 三、执行顺序与排期

| 序 | 任务卡 | 对应 P0 | 工期 | 依赖 | 做完后页面上多了什么 |
|---|---|---|---|---|---|
| 0 | 条款进 Store | 前置 | 0.5 天 | 无 | 条款成为唯一事实源（还看不见变化） |
| 1 | 基础行动条 | P0-1 | 1 天 | 卡 0 | 不抽卡也能「接受/拒绝/维持/最后报价/退出」 |
| 2 | 条款变化摘要 | P0-3 | 0.5 天 | 卡 0 | 对方回应气泡顶部出现「接受 2·修改 1·剩余 2」 |
| 3 | 待表态窗口 + 过渡额度 | P0-2 | 1 天 | 卡 1、2 | 顶部状态带：待表态·剩 1 轮·过渡 1/1 |
| 4 | 僵局计时 + 终局五态 | P0-5 | 1～1.5 天 | 卡 0、1 | 顶栏「僵局 0/3」+ 五态终局卡 |
| 5 | 协议签署板 | P0-4 | 1.5～2 天 | 卡 0、1 | 右侧抽屉可逐条签条款、提交修订 |

**合计 5.5～6.5 天。** 如果 Demo 需要签署板当门面，把卡 5 提前到卡 1 之后——但那时卡 2/3 的摘要与窗口要延后。

排期建议（按 5 天窗口压）：
- D1 上午 卡 0 → D1 下午 卡 2（半天出第一个可见效果，好给团队看进度）
- D2 卡 1 ｜ D3 卡 3 ｜ D4 卡 4 ｜ D5 卡 5（卡 5 若压不下，先交只读版 + 「提交修订」按钮灰置）

---

## 四、任务卡

### 卡 0 · 条款进 Store（前置，0.5 天）

```text
（此处粘第二节的「通用上下文头」）

【任务】
把现在写死在 src/components/content.js 里的 QUOTE_ROWS（5 条条款）提到领域层，成为 store 里
可被规则读写的单一事实源。这一步不改任何视觉，只改数据来源。

【落点】
1. 新建 src/domain/clauses.js：
   - export const CLAUSE_STATUS = { open:'未决', pending:'待确认', decided:'已决', rejected:'已拒绝' }
   - export function createInitialClauses() 返回 5 条，字段：
       id          短横线小写英文，如 'compute-quota'
       name        中文条款名，沿用现有 5 条：公共算力配额 / 安全审查范围 / 逐案许可豁免 / 第三方观察员 / 争端解决机制
       ourStance   我方立场文本，初值 '维持现立场'
       theirStance 对方立场文本，沿用现有 opponent 字段
       theirValue  估计值对象，沿用现有 value 字段结构（kind/num/unit/label）
       confidence  可信度 0-100 的整数，用于标注「估计值」的可信程度
       status      CLAUSE_STATUS 的 key，初值沿用现有 status
       changedRound 最近一次状态变化的轮次，初值 1
       changedVersion 最近一次状态变化的协议版本，初值 1
   - export function clausesSummary(clauses) 返回 { decided, pending, open, rejected, total }
2. src/domain/negotiation.js 的 createInitialNegotiation() 增加：
   clauses: createInitialClauses()
   clausesVersion: 1
3. src/stores/NegotiationStore.js 增加只读 getter clausesSummary（调 clausesSummary(this.state.clauses)）。
4. src/components/content.js 删掉 QUOTE_ROWS 常量，ReportContent({ topic }) 改为 ReportContent({ topic, clauses })，
   渲染时读传入的 clauses，状态文案取 CLAUSE_STATUS。代码里不要再有任何硬编码条款名。
5. src/main.js 调用 ReportContent 的地方传 store.state.clauses。

【规则】
- 战报弹窗的视觉、列宽、状态徽标配色一律不变，这次只换数据来源。
- 条款 id 一旦定下不要改，后面四项都会引用。
- confidence 先给保守值（60～80），并在对方立场列附近用现有 .quote-opponent 结构展示「估计值 · 可信度 72%」，不要新造一套样式类。

【验收】
- 打开战报：条款仍是 5 行，状态与原来一致（2 已决 / 2 待确认 / 1 未决），文案无变化。
- 控制台执行 __diplomat.store.state.clauses.length === 5 为 true。
- 全局搜索 QUOTE_ROWS 无结果；搜索 5 个条款名只应出现在 src/domain/clauses.js 一处。
- vite build 与 build-single.mjs 均通过，单文件版 file:// 打开正常。

【禁止】
- 不许顺手重排战报布局、改字体改配色。
- 不许把 clauses 做成异步加载或从网络取。
- 不许在这个卡里动提交链路。
```

---

### 卡 1 · 基础行动条（P0-1，1 天）

```text
（此处粘第二节的「通用上下文头」+ 卡 0 已完成）

【任务】
在策略卡区顶部加一条「始终可用」的基础行动条：接受 / 拒绝 / 维持现立场 / 最后报价 / 宣布退出。
它不依赖抽卡、不消耗行动点，但受轮次锁、会话结束、待表态窗口制约。
这是纪要 §5.4 的硬要求——用户必须能在任何时刻收束谈判，而不是只能一直出牌。

【落点】
1. 新建 src/components/ActionBar.js：
   export function ActionBar({ actions }) → 返回 <div class="action-bar" role="toolbar" aria-label="基础行动">…</div>
   actions 是数组，每项 { id, label, hint, disabled, reason, used }
2. src/components/StrategyPanel.js：在 #strategyCards 上方插入 ActionBar 占位 div id="actionBar"，
   StrategyPanel({ ..., baseActions }) 透传。
3. src/stores/NegotiationStore.js：
   - state.baseAction = { kind:'none', atRound:0, atVersion:0 }，kind 取值 none|accept|reject|hold|final|exit
   - chooseBaseAction(kind)：
       ended / roundLocked / phase==='loading' 时返回 { ok:false, reason }
       'final' 若 state.finalOfferUsed 为 true 返回 { ok:false, reason:'used' }
       成功则写 baseAction 并返回 { ok:true }
   - clearBaseAction()
   - canEndTurn 放宽为：(selectedIds.length > 0 || baseAction.kind !== 'none') && 其余条件不变
   - prepareTurn() 的 payload 增加 baseAction: {...state.baseAction}
   - applyTurn() 把 payload.baseAction 记进 state.actions[actionId].baseAction；
     若 kind==='final' 则 state.finalOfferUsed = true；若 kind==='exit' 则 state.ended = true 且 endReason='withdraw'
   - 加 state.finalOfferUsed = false 初始值
4. src/services/adapter.js：submitAction 的 payload 透传 baseAction（mock 与 http 两条路径都要，http 时放进 body）。
5. src/main.js：
   - renderStrategy() 里渲染 ActionBar（新建 renderActionBar() 更清晰）
   - data-action 增加 base-action（读 data-kind）、confirm-exit
   - 'end-turn' 的 toast 文案区分：纯基础行动时不提示「请先选择策略卡」

【按钮规则（严格按此实现，别自作主张）】
- 接受：只有在存在 pending 或 decided 条款、且对方给过新版本（state.version > 1 且最近一轮对方回应带条款变更）时可用。
        不可用时 disabled=true，reason 文案「当前没有可接受的条款版本」。
- 拒绝：始终可用（除 ended / roundLocked / loading）。
- 维持现立场：始终可用。
- 最后报价：每场 1 次。用过 disabled，reason「本场已使用最后报价」。使用时不消耗行动点但要占一轮。
- 宣布退出：始终可用，点击弹 Modal 二次确认（标题「确认退出谈判？」，
        正文说明会记为「主动退出」而非失败，主按钮「确认退出」，次按钮「继续谈判」）。

【状态与视觉】
- 行动条横排 5 个按钮，高度 36px，与手牌区同栏；窄屏（<1180px）允许换行，不许横向滚动。
- 已选中的基础行动按钮带 aria-pressed="true" 与高亮边框（用现有 --gold 系列变量）。
- disabled 按钮必须有 title 或 aria-describedby 说明原因（手册要求：不可用要解释）。
- 选卡与选基础行动互斥：选了基础行动就清空 selectedIds，反之亦然。切换时给 toast 提示「已切换为基础行动，卡牌选择已清空」。
- 保存草稿语义不变：提交失败时 baseAction 也要保留（failSubmit 里不许清空）。

【验收】
- 一张卡都不选时，点「拒绝」→ 结束本轮按钮变为可点 → 提交成功 → actions 账本里该 action_id 带 baseAction.kind='reject'。
- 点「接受」且没有可接受条款 → 按钮 disabled，hover 有原因。
- 点「最后报价」提交一次后 → 按钮 disabled，reason 正确。
- 点「退出」→ 出现二次确认 → 确认后 ended=true，界面进入终局（卡 4 未做前先复用现有「谈判已结束」弹窗）。
- MODEL_UNAVAILABLE 注入下用基础行动提交 → 失败横幅出现，且行动条选中状态保留。
- 1440×900 与 1920×1080 均无横向滚动。

【禁止】
- 不许把基础行动做成消耗行动点。
- 不许只加界面不改 store（必须走 adapter 提交，否则幂等和错误码会漏）。
- 不许在 ActionBar 里写业务判断——可用性判断放 store，组件只管画。
```

---

### 卡 2 · 条款变化摘要（P0-3，0.5 天）

```text
（此处粘第二节的「通用上下文头」+ 卡 0 已完成）

【任务】
每次对方回应后，在他那条消息气泡顶部加一行「本轮条款变化」摘要：
「接受 2 · 修改 1 · 未变 2」，让人一眼看出这一版动了什么。无变化时不显示，避免噪音。

【落点】
1. src/domain/clauses.js 增加：
   diffClauses(prevClauses, nextClauses) → { accepted:[name], modified:[name], rejected:[name], unchanged:[name] }
   判定：status 由非 decided 变 decided → accepted；status 变 rejected → rejected；
        theirStance 或 theirValue 或 ourStance 变化 → modified；其余 unchanged。
   formatDiff(diff) → 中文短句，如「接受 2 · 修改 1 · 未变 2」，四类为 0 的不写。
2. src/stores/NegotiationStore.js 的 recordOpponentReply(round)：
   现在只 push 一条固定话术。改为先按「本轮对方让步脚本」更新 clauses（写一个
   OPPONENT_PATCHES 数组，按轮次取，最多覆盖 5 轮；不要随机），记录 prev 快照，
   更新后逐条写 changedRound / changedVersion，state.clausesVersion += 1，
   再把 clauseDiff 挂到返回的 speech 对象上。
3. src/components/DialogueStage.js 的 Speech({ ..., clauseDiff }) 增加可选参数：
   clauseDiff 存在且 formatDiff 非空时，在 .speech-meta 下方渲染
   <div class="clause-diff" role="note"><span>本轮条款变化</span><strong>接受 2 · 修改 1</strong></div>
4. src/main.js 的 appendSpeech 透传 clauseDiff（appendSpeech 内部拼 Speech 时要把该字段带上）。

【规则】
- 摘要只统计「本轮」的变化，不是累计。
- 只用中文数字与顿号，不加 emoji、不加颜色语义（红绿）。
- 无变化轮次：clauseDiff 为 { accepted:[], modified:[], rejected:[], unchanged:[5 条] } 时整行不渲染。
- 气泡内不换行溢出：1440 档一行内，数字超过 3 项时允许右侧截断显示「+1」，hover 显示完整。

【验收】
- 正常提交一轮 → 对方回应气泡顶部出现摘要行，数字与 __diplomat.store.state.clauses 的实际差异一致（可在控制台核对）。
- 连续提交 3 轮 → 摘要内容随轮次变化，不重复上一轮数字。
- 某轮无变化 → 该轮气泡不出现摘要行。
- 战报里条款状态与摘要一致（同一份 clauses）。
- 双档无横向滚动。

【禁止】
- 不许把摘要做成 toast 或独立面板（必须在对方气泡内，跟上下文绑定）。
- 不许改动错误横幅、教练面板的位置。
- 不许让 AI 自由发挥生成条款文案——变化必须由 OPPONENT_PATCHES 确定性驱动，Demo 要可复现。
```

---

### 卡 3 · 待表态窗口 + 过渡额度（P0-2，1 天）

```text
（此处粘第二节的「通用上下文头」+ 卡 1、卡 2 已完成）

【任务】
对方给出新协议版本后，进入「待表态」状态：我方必须在 N 轮内对最新版本表态（接受 / 拒绝 / 请求修改），
每个版本允许 1 次「过渡」——把表态延后 1 轮，不算沉默。窗口状态在会场顶部状态带常驻显示。

【落点】
1. src/stores/NegotiationStore.js 增加：
   state.responseWindow = { open:false, version:0, openedRound:0, deadlineRound:0, transitionUsed:false }
   方法 openResponseWindow(version, round)：开窗，deadlineRound = round + 2，transitionUsed=false
   方法 useTransition()：窗口开着且未用过 → transitionUsed=true，deadlineRound += 1，返回 { ok:true }
   方法 closeResponseWindow()：open=false
   方法 checkWindowTimeout()：round > deadlineRound 时返回 true（超时）
2. openResponseWindow 在 recordOpponentReply 里调用（对方给出新版本时）。
   closeResponseWindow 在 applyTurn 里调用（我方完成了一次表态，kind 为 accept/reject/hold/final/revise 任一）。
3. 超时处理放在 main.js 的提交成功回调之后：
   若 checkWindowTimeout() 为 true → metrics.trust -= 3（下限 0），
   appendSpeech 一条系统消息（party='us' 不合适，用现有 system 样式或在 Speech 里加 system:true），
   文案「我方未在窗口内对 vX 表态，对方视为沉默处理」。然后关闭窗口。
4. src/components/Topicbar.js 或会场顶部新增状态带组件 StatusStrip：
   <div class="status-strip" role="status">
     <span class="ss-dot"></span><strong>待表态</strong>
     <span>v3 · 剩 1 轮</span>
     <span class="ss-quota">过渡 0/1</span>
     <button data-action="use-transition" ...>使用过渡</button>
   </div>
   窗口未开时整条不渲染（不留空）。
5. data-action 增加 use-transition。

【规则】
- 「剩余轮数」= deadlineRound - round，最小显示 0，负数不显示。
- 过渡按钮：transitionUsed 后 disabled，文案「过渡已用」。
- 剩余 0 轮时状态带转为警示色（现有 --amber / --red-bg 变量），文案改「最后 1 轮，必须表态」。
- 窗口期内基础行动条的「接受/拒绝」必须高亮（这是主路径），但不许强制、不许遮罩。
- 窗口不阻塞出牌：用户在窗口内仍可选卡提交，提交即视为表态并关窗。

【验收】
- 提交一轮 → 状态带出现「待表态 v2 · 剩 2 轮 · 过渡 0/1」。
- 点「使用过渡」→ 剩余 +1，按钮变灰「过渡已用」。
- 连续推进到 deadlineRound 且未表态 → 信任值 -3，出现系统提示行，窗口关闭。
- 窗口期内提交 → 窗口立即关闭，状态带消失。
- 教练 pending 期间窗口数字与状态带不抖动（教练不许写这个槽位）。

【禁止】
- 不许把窗口做成 modal 或阻塞层（纪要明确要求不打断主流程）。
- 不许自动替我表态。
- 不许在 StatusStrip 里直接读写 store.state——只接收 props。
```

---

### 卡 4 · 僵局计时 + 终局五态（P0-5，1～1.5 天）

```text
（此处粘第二节的「通用上下文头」+ 卡 0、卡 1 已完成）

【任务】
1）顶栏显示僵局计时「僵局 0/3」：连续 3 轮没有产生新协议版本即判僵局。
2）把现在那句「本场谈判已结束」换成五种终局卡，各自有标题、结论、评价口径与主按钮。
   判定先做前端（client-side），所有判定收在一个纯函数里，方便 A 的后端判定接进来时整体替换。

【落点】
1. src/domain/endgame.js（新建）：
   export const END_REASONS = { full_agreement, partial, withdraw, stalemate, rounds_exhausted }
   export function judgeEnd(state) → null | { reason, title, summary, metricsHint }
   判定顺序（先命中先返回）：
     a. state.endReason === 'withdraw'（用户主动退出）        → withdraw
     b. 全部条款 decided 且我方已接受                        → full_agreement
     c. state.stagnantRounds >= 3                            → stalemate
     d. state.round > state.maxRounds                        → 有 decided 条款则 partial，否则 rounds_exhausted
   条款全 decided 但含 rejected 的，算 partial。
2. src/stores/NegotiationStore.js：
   state.stagnantRounds = 0
   state.endReason = null
   在 applyTurn 里：若本次提交产生了 clausesVersion 增长 → stagnantRounds = 0，否则 +1。
   end() 增加参数 reason，写 state.endReason。
   新增 getter judge：() => judgeEnd(this.state)
3. src/components/Topbar.js：在轮次旁加 <em class="stalemate-chip" data-stalemate>僵局 0/3</em>，
   数值 = stagnantRounds，满 3 时加 .danger 类。
4. src/main.js：
   - 新增 renderStalemate()，applyTurn 后调用
   - 现有那个「谈判已结束」的 modal 调用改成 renderEndgame(reason)，五态各自：
       full_agreement   标题「协议达成」 kicker AGREEMENT · 主按钮「查看战报」
       partial          标题「部分协议」  kicker PARTIAL DEAL · 主按钮「查看战报」
       withdraw         标题「我方主动退出」 kicker WITHDRAWN · 主按钮「查看战报」
       stalemate        标题「谈判陷入僵局」 kicker STALEMATE · 主按钮「查看战报」
       rounds_exhausted 标题「轮次用尽」 kicker ROUNDS EXHAUSTED · 主按钮「查看战报」
     次按钮统一「重新谈判」。五种都用同一个 ModalController.open，不新写弹窗。
   - 战报 ReportContent 增加三段小标题：谈判结果 / 协议质量 / 学习表现，
     把现有三项指数按归属拆过去（主体利益、国际形象 → 结果；已决条款比例 → 协议质量；
     行动点使用效率、被拒次数 → 学习表现）。数据先按现有字段推算，缺的字段留「—」。

【规则】
- 判定的唯一入口是 judgeEnd(state)，main.js 不许写 if-else 判定逻辑。
- 终局弹窗出现后，手牌区、行动条、教练面板全部进入只读（disabled 或视觉降级），不许还能出牌。
- 五态配色只用现有变量：达成用 --gold，部分用 --amber，退出用中性，僵局/耗尽用 --red 系。
- 五种终局都必须能通过 __diplomat 探针构造出来（见验收）。

【验收】
- 控制台用 __diplomat.store.state 依次把状态改成五种终局条件，各弹一次，标题与 kicker 对应正确。
- 连续 3 轮提交但条款无变化 → 顶栏显示「僵局 3/3」并弹 stalemate。
- 主动退出 → withdraw，不出现「失败」字样。
- 终局后点手牌、行动条均无效（有 toast 说明）。
- 战报三段小标题都在，缺数据处显示「—」不报错。
- 双档无横向滚动，终局弹窗 1440 档不出现内部滚动条。

【禁止】
- 不许把判定规则写进 UI 组件。
- 不许改 A 的错误码 / 幂等契约。
- 不许把「学员表现」写成分数排名（手册禁止替用户下判断，只给事实 + 提示）。
```

---

### 卡 5 · 协议签署板（P0-4，1.5～2 天）

```text
（此处粘第二节的「通用上下文头」+ 卡 0、卡 1 已完成）

【任务】
把条款表从战报弹窗搬到主流程：右侧抽屉新增「协议签署板」标签页，逐条显示/修改我方立场，
展示对方立场与估计值可信度，可「提交本轮修订」——提交走同一条 adapter 链路（六错误码、幂等、草稿保留全部生效）。

【落点】
1. src/components/ClauseBoard.js（新建）：
   export function ClauseBoard({ clauses }) → 表格式列表，每行：
     序号 · 条款名 · 我方立场（select：维持现立场 / 接受对方版本 / 提出修改 / 拒绝该条）
     · 对方立场 + 估计值 + 可信度 · 状态徽标 · 变更于「第 N 轮 · vX」
   底部固定条：<div class="cb-footer">已修订 2 条 · 未决 1 条 <button class="solid-button" data-action="submit-revision">提交本轮修订</button></div>
2. src/components/Drawer.js：抽屉头部加 tab 切换（签署板 / 谈判树），默认打开「签署板」；
   TreeDrawerBody 内容不动，新增 #clauseBoardBody。
3. src/stores/NegotiationStore.js：
   - state.stanceDrafts = {}（clauseId → 立场枚举），草稿，提交失败必须保留
   - setStanceDraft(clauseId, stance)、clearStanceDrafts()
   - prepareTurn() 支持纯修订提交：stanceDrafts 非空时 payload.revisions = [{ clauseId, stance }]，
     且此时 selectedIds 可为空（canEndTurn 条件再加 || Object.keys(stanceDrafts).length > 0）
   - applyTurn() 落地 revisions：更新 ourStance / status / changedRound / changedVersion，
     clausesVersion += 1，并清空 stanceDrafts
4. src/main.js：
   - data-action 增加 switch-drawer-tab、stance-change、submit-revision
   - 'submit-revision' 走 submitTurn({ fromRevision: true })
   - 提交中按钮 aria-busy，草稿不受影响
5. 战报弹窗里的条款表改成只读摘要，并加一行提示「逐条签署请打开右侧协议签署板」，
   删掉战报里那 5 个可编辑 select（避免两处都能改）。

【规则】
- 接受某条：ourStance = 对方立场，status = decided。
- 提出修改：status = pending，ourStance 记「提出修改：<原立场>」。
- 拒绝该条：status = rejected。
- 还有 open/pending 条款时，「接受」类操作要给出解释：「仍有 N 条未决，接受将形成部分协议」，不禁止但必须提示。
- 草稿语义与卡牌一致：失败保留、重试幂等（action_id 由 stanceDrafts 签名参与计算）。
- 抽屉打开不遮住整页：1440 档抽屉宽度不超过 460px，会场仍可见。
- 面板默认折叠的要求适用于教练；签署板是用户主动打开的，可以展开，但刷新后不自动打开。

【验收】
- 改 2 条立场 → 底部显示「已修订 2 条」→ 提交 → version +1、clausesVersion +1、两条 changedRound 更新为当前轮。
- 注入 MODEL_UNAVAILABLE → 失败横幅出现，抽屉里的 2 条修订仍在（草稿保留）。
- 重试 → 账本只多 1 条 action（幂等，不重复）。
- 战报里不再有可编辑 select，提示行存在。
- 关闭抽屉再打开，草稿仍在（同一次会话内）。
- 双档无横向滚动；抽屉 1440 档不出现内部横向滚动条。

【禁止】
- 不许给签署板另起一套提交/错误处理逻辑（必须复用 submitTurn）。
- 不许把「接受全部」做成一键按钮（纪要要求逐条签署，且手册禁止替用户做决定）。
- 不许改条款数据结构（卡 0 定的字段不动，需要新字段先说明理由）。
```

---

## 五、不属于我的部分（先别写提示词，等对齐）

| 事项 | 卡住的原因 | 等谁 | 我的临时办法 |
|---|---|---|---|
| 行动点改成「每回合 4，子议题 ≥4 项时 5」 | 纪要 §12.1 与现状 5/5 冲突，规则归后端 | 团队 + A | 卡 1～5 全部按现有 5 点写，改口径只改 `state.actionPoints` 与 `canEndTurn` 一处 |
| 卡池 14 张 / 6 族 / 冷却时间表 | 等 B 的 `card_registry.json` 定稿，整表替换 | B | 卡 1 的基础行动不依赖卡池，可以先做 |
| 冷却（报价塑造 1 回合 / 信息试探 2 / 核查履约 3） | 冷却字段在卡注册表里 | B | 前端先留 `strategy.cooldown` 字段的读取位，无值时不渲染 |
| 终局判定的权威结果 | 真正判定权在 A 的 session 状态 | A | 卡 4 的 `judgeEnd` 是纯函数，接 A 时整体替换实现，UI 不动 |
| 条款真实立场与可信度 | 需要 A 的 `project_snapshot` 输出 | A | 卡 0 的 `confidence` 先给保守值，字段名与契约对齐 |
| debrief（赛后复盘）取回方式 | A 未定方案 A/B | A | 战报里「学习表现」先用本地数据，接口到了换数据源 |

---

## 六、每张卡发出去之后，补这一句

```text
做完先别改别的：把改动的文件列出来、每条验收跑一遍并把结果贴给我（通过/不通过 + 实测数值）。
如果有任何一条做不到，直接说做不到和原因，不要用"已优化""已完善"糊过去。
最后确认 vite build 与 build-single.mjs 都通过。
```

---

## 七、给团队的同步话术（可选，发群里用）

> P0 五项我按「前端能自洽」先拆成 5 张任务卡，已排 6 天。前置是把条款表从战报里提进 store（半天），之后接受/拒绝/维持/最后报价/退出、待表态窗口、条款变化摘要、僵局与五态终局、协议签署板依次落地。
> 三件事需要定口径才能收口：① 行动点是否改成「每回合 4」；② 卡池是否整表换成 B 的 14 张 / 6 族（含冷却）；③ 终局判定的权威结果由 A 的后端给，我这边先做前端判定、纯函数封装，接口到了整体替换。
> 这三点不定也不阻塞演示，但越晚定联调越紧。

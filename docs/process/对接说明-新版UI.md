# 新版 UI 对接说明（Diplomat-components → 11.11 主项目）

> 新版 UI：`Diplomat-components(1)/`（Vite 构建，策略卡驱动的黑金界面）
> 旧版主站：`11.11/index.html`（报价板驱动的战情室，含教练 Agent 与错误码体系）
> 本文档回答三件事：白屏为什么发生、现在怎么打开、以及新 UI 与既有任务还差哪些对接。

---

## 一、白屏的原因（已修复）

| # | 原因 | 表现 | 修复 |
|---|---|---|---|
| 1 | 构建产物用绝对路径 `/assets/...`、`/stage-bg.jpg` | 双击 dist/index.html 时资源请求 `file:///assets/...`，全部 404 | `vite.config.js` 加 `base: './'`，产物改相对路径 |
| 2 | 入口脚本是 `<script type="module">` | file:// 下浏览器以 CORS 拦截模块脚本，页面只有空 `#app` | 生成 IIFE 单文件版（见下） |
| 3 | JS 里运行时拼死 `/fab-icon.png` | 即使资源相对化，运行时拼的绝对路径仍 404 | `DialogueStage.js` 改为相对引用 |

验证截图：`file://` 直开单文件版、http 直开 dist、http 直开主站，三者均正常渲染（2026-11-16）。

## 二、现在怎么打开（两种方式）

| 方式 | 操作 | 适用 |
|---|---|---|
| **双击即开（推荐给演示）** | 双击 `new-ui/Diplomat-单文件版.html`（或 `Diplomat-components(1)/` 下同名文件） | 无需任何服务，评委机器也能开 |
| **http 方式（推荐给联调）** | 项目根目录 `py serve.py` → 浏览器开 `http://127.0.0.1:8000/new-ui/`（旧版主站在 `/`） | 后续接真实接口、录屏 |

- 改了 `src/` 之后重新出两个产物：
  - `node node_modules/vite/bin/vite.js build` → 更新 `dist/`（记得同步拷到 `new-ui/`）
  - `node build-single.mjs` → 重新生成单文件版
- `new-ui/` 是构建产物的**部署副本**，不要手改；源码永远在 `Diplomat-components(1)/src/`。

## 三、与既有任务的对接差距（字段映射）

新版 `NegotiationStore.state` 对齐 `docs/state-contract.md` 的情况：

| 契约字段 | 新 UI 现状 | 差距 |
|---|---|---|
| `round` / `maxRounds` | ✅ 有 | — |
| `action_points` | ✅ 有（固定 5，含消耗计算） | 差 max/current 结构 |
| 三项指数 | ✅ 有 `metrics`（interest/image/trust） | 需确认与契约三项口径一致 |
| `public_message` / `action_history` | 部分：`speeches` / `log` | 缺 `action_id` 账本（幂等与证据溯源都要用） |
| `version`（协议版本） | ❌ 无 | 版本三处一致这条硬验收无法做 |
| `clauses` / `my_offer` / `opponent_offer` | ❌ 无（新 UI 是策略卡制，没有报价板条款） | **结构性差异**，不是补字段能解决 |
| `coach_advice` | ❌ 无 | 第 6 天教练面板未接入 |
| 六错误码 / 幂等 / 草稿保留 | ❌ 无（`endTurn` 是同步本地逻辑，无请求） | 第 5 天成果未接入 |
| 终局评价 `speaker_score` | 部分：有战报（report FAB） | 无四维 + BATNA 比较 |

## 四、三条对接路径（选一条）

| 路径 | 做法 | 工作量 | 适合 |
|---|---|---|---|
| **A. 双版本并存（当前已完成）** | 新 UI 作为「策略卡演示版」，旧主站作为「报价板完整版」，入口互通 | 已完成 | 时间紧，两边都能演示 |
| **B. 新 UI 升级为主 UI** | 给新 store 补 `version` + `actions` 账本，`endTurn` 走 adapter（6 错误码 + 幂等 + 草稿保留），接教练三态面板 | 约 1～1.5 天 | 想用新 UI 打 Demo 主路径 |
| **C. 只取新 UI 视觉** | 把新 UI 的黑金视觉体系（token/字体/卡片）迁回旧主站，逻辑不动 | 约半天 | 旧主站逻辑已验收、不想动 |

**建议：B 或 C 二选一，不要两头都改。** 手册里程碑 M3（第 8 天功能完整）之前必须定，否则教练与错误码会同时散在两套 UI 里，联调翻倍。

## 五、无论选哪条都必须补的（新 UI 当前缺的硬验收项）

1. `version` 三处一致（顶栏 / 报价区 / 协议抽屉）——新 UI 没有版本号。
2. 失败保留用户选择（策略卡选中态就是"草稿"，请求失败不能清空）。
3. 重试幂等：同一意图一个 `action_id`，改选策略即作废。
4. 教练默认折叠、不阻塞下一轮（第 6 天三条硬约束）。
5. 加载骨架、空态、失败提示（新 UI 目前无网络层，天然没有这些状态）。

## 六、路径 B 完成记录（11.11）

已选定 **路径 B** 并完成对接 + 构建验证。改动都在 `Diplomat-components(1)/`：

**新增文件**
- `vite.config.js`（`base:'./'`，产物相对路径）
- `build-single.mjs`（esbuild IIFE + 图片内联 → `Diplomat-单文件版.html`，双击即开不白屏）
- `src/services/adapter.js`（mock/http 双模式，六错误码 + `Idempotency-Key`）
- `src/services/idempotency.js`（`action_id` 随选卡签名变化作废重生成）
- `src/services/coach.js`（六态教练 + 双重断言过滤）
- `src/components/CoachPanel.js`、`src/components/ErrorBanner.js`

**改造要点**
- `NegotiationStore`：新增 `version/actions/phase/error/coach*`，`prepareTurn/applyTurn/failSubmit` 三段式提交。
- `main.js`：`submitTurn()` 异步链路（失败按错误码分支：SESSION_BUSY 倒计时自动重试、VERSION_CONFLICT 换基线重演、MODEL_UNAVAILABLE 规则引擎降级）；`requestCoach()` 带 `coachSeq` 防串轮。
- 版本号三处一致（顶栏 / 策略卡区 / 谈判树抽屉）；失败只记错误不清 `selectedIds`（草稿保留）。
- `window.__diplomat` 联调探针（store/submitTurn/injectError/stopBusyCountdown 等）。

**验证结论（无头 Chrome 实测，证据在 `docs/evidence/t7/`）**
- 正常提交：v1→2，`actions` 账本 1 条，教练 ready 返回 stage+alternative 两条。
- SESSION_BUSY 注入：横幅显示错误码 + action_id + 「已选 3 张卡已保留」；重试后 v2→3、账本 2 条（幂等，不重复提交）。
- 教练 leak 注入：命中禁用词的整条被过滤，只剩 1 条。
- 版本三处一致（v4/v4/v4）；1440×900 与 1920×1080 均无横向滚动；`file://` 双击打开不白屏。

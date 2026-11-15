# DIPLOMAT 前端（ui/）

黑金战情室前端，三层结构：状态层 / 数据适配层 / 渲染层。
零构建、零依赖，clone 后一条命令即可启动。

仓库根 `README.md` 是后端与队友交付物说明；前端入口与启动方式以本文件为准。

## 启动

任选一种，30 秒内可跑（命令均在 `ui/` 目录执行）：

| 方式 | 命令 | 说明 |
|---|---|---|
| 推荐 | `py serve.py` | 自动打开 `http://127.0.0.1:8000/`，Ctrl+C 停止 |
| Windows 双击 | `start.bat` | 自动选择 `py` / `python`；都没有时直接打开 `index.html` |
| 备选 | `py -m http.server 8000` | 手动访问 `http://127.0.0.1:8000/` |
| 最简 | 双击 `index.html` | 普通 `<script>`（非 ES module），file:// 可直接运行 |

端口被占用：`set PORT=8100` 后再执行 `py serve.py`。

## 目录

```
ui/
  index.html                  入口壳（只负责挂载与脚本顺序）
  serve.py  start.bat         启动脚本
  README.md                   本文件
  core/dom.js  core/util.js   DOM 工具与幂等键/评级映射
  store.js                    唯一 store：字段集中定义，读/订阅/提交
  adapters/
    mockAdapter.js            默认实现（第 1 天全部行为）
    httpAdapter.js            真实接口实现（A 冻结请求骨架）
    index.js                  唯一切换点 D.adapters.use('mock' | 'http')
  components/                 九个区域，纯只读渲染
  styles/app.css              设计 token + 区域样式
  legacy/index-v1.html        第 1 天单文件原型（改前证据，不参与运行）
  docs/state-contract.md      字段契约 v2（A/C 回签与 K1–K8）
  docs/acceptance-checklist.md 双断点与交互态核对表
  action_schema.json          行动契约的机器可读版本（A 的 action_schema 同步副本）
```

## 三层与“第 5 天只换实现”

- **状态层** `store.js`：唯一 `S`，`get()` / `subscribe()` / `commit()`；草稿、选中卡、提交流程都在这里。
- **适配层** `adapters/`：`mockAdapter` 与 `httpAdapter` 实现同一签名
  `createState / openSession / rehearsal / submit / merge / accept / summary / nextTopic / randomCheck / reset`。
- **渲染层** `components/`：只读 `state`，只做字符串拼接；金额、比例、加权分一律不在这里算。

切换真实接口只改一处（不改任何组件或调用点）：

```html
<script>
  window.DIPLOMAT_CONFIG = { adapter: "http", httpBase: "https://<host>" };
</script>
```

`httpBase` / 各路径留空时 `httpAdapter` 不发请求。**页面内不存在任何真实域名、Token 或密钥。**

## 三档启动（A 答复 2026-11-15）

| 档位 | 配置 | 行为 |
|---|---|---|
| 默认 mock | 不注入 `DIPLOMAT_CONFIG` | 双击 `index.html` 即可；全部第 1 天行为 |
| 本地后端 | `{ adapter:"http", httpBase:"http://127.0.0.1:<port>" }` | 启动即 `POST /session` 开局，成功后整棵替换全量投影 |
| 远程后端 | `{ adapter:"http", httpBase:"https://<host>" }` | 同上；地址由 A 提供，本文件不写死 |

注入方式（在 `index.html` 的脚本前加一行，或构建期注入）：

```html
<script>
  window.DIPLOMAT_CONFIG = { adapter: "http", httpBase: "https://<host>" };
</script>
```

- **未配置 `httpBase`**：不发请求；页面渲染空框架，连接灯「服务不可用」，不白屏、不抛未捕获异常。
- **会话标识**：A 答复 `session_id` 在 **path**，形如 `/session/{id}/action`；开局 `POST /session` 返回 `session_id` + 全量投影。前端不手工拼 session。
- **错误**：统一 `{error, detail}`，文案由服务端定；409 `VERSION_CONFLICT` 额外带 `current_state`；409 `SESSION_BUSY` 自动重试 1 次同键；503 `MODEL_UNAVAILABLE` 只降级左栏/情报。
- **404 `SESSION_NOT_FOUND`**：顶部提示「会话不存在或服务已重启」+「重新开局」。
- **无 reset / topic / summary 接口**：`reset` = 重新 `POST /session`；`summary` = `POST /session/{id}/debrief`（202 受理，不返回内容）；切题 = 重开一局。
- **鉴权**：当前无；前端不注入任何密钥（`DEEPSEEK_API_KEY` 只在服务端）。CORS 由 `api.py` 的 `allow_origins=["*"]` 处理，前端无需配置。

### 演示 10 秒软提示（G8）

默认 mock 的 900ms 不会触发软提示。临时注入（刷新后生效）：

```html
<script>window.DIPLOMAT_CONFIG = { adapter: "mock", mockDelayMs: 12000 };</script>
```

提交后 10 秒出现「上游仍在处理，已等待 Ns…」+「取消等待」；点取消立即清等待、草稿保留。验证完删除这行。

### 第二轮答复口径（2026-11-15）

| 项 | 结论 | 前端处理 |
|---|---|---|
| 接受协议 | `POST /session/{id}/action`，`action_type:"accept"`，`offer_patch:{}`，`expected_effect/public_message` 必填 | `httpAdapter.accept()`；成功后按投影 `status:"ended"` 进终局 |
| 条款可选值 | 投影 9 字段暂无 options；计划第 5 天补 `clauses[{name,type,options,initial}]` | 优先 `payload.clauses`；过渡用 `DIPLOMAT_CONFIG.clauseOptions` |
| 行动点 | 投影未暴露；计划 `{current,max}`；未补入前每轮 3 点、每行动 1 点 | 已裁决 K4=3：mock/空态 `3/3`；投影存在时以 max 覆盖 |
| speakerScore | 服务端未实现；终局 null 态 | 不本地算分；`null` 显示不计分 |
| debrief | 202 纯受理，无复盘/教练内容 | 提示「已受理，内容本轮不返回」 |
| 开局 | `{scenario_id:"ai_governance", agent:"us", scenario_path:null}`；agent 只能 `us` | `openSession` 默认，可配置覆盖 |
| offers | 只含 `option` + `note` | 只读；选项来自 `clauses`/`clauseOptions` |
| 500 | `INTERNAL_ERROR` 按服务不可用、不重试、保留草稿 | 走 G2 通道 |

### 第三轮答复口径（2026-11-15）

| 项 | 结论 | 前端处理 |
|---|---|---|
| clauses | enum + numeric（`unit`/`range{min,max,step}`/`initial`），11-16 上午联调前补入 | 已支持 numeric 数值输入；enum 仍用下拉 |
| action_points | `{current,max}`；每行动扣 1；**D 已裁决 `max=3`（2026-11-15）** | mock/空态 `3/3`；投影存在时以 `max` 覆盖 |
| speakerScore | 产出方 C＋B，A 透传，**不由 D**；外层 camelCase | 只读 `payload.speakerScore`；只展示 |
| C 单复数 | C 已澄清：B 契约单数、引擎复数，适配层双读，不是 bug | 前端不读该字段 |
| 对方可信度 | C 回 D（2026-11-15）：百分比改为定性分级 | 高 ≥70／中 40–69／低 1–39／未知；规则写 tooltip，不显示百分比 |

### 第四轮确认（2026-11-15）

- **K4 落章**：D 裁决 **3**；A 改 `load_scenario_bridge.py` 的 5→3，与投影同一次提交；mock/空态已 `3/3`。
- **投影**：`clauses`＋`action_points` 仍未落地，承诺 11-16 上午联调前；前端已兼容 enum/numeric 与 `{current,max}`。
- **speakerScore**：外层 camelCase 定稿；前端只读 `payload.speakerScore`，终局 null 态。
- **C 单复数**：C 已澄清、适配层双读；A 第四轮附项不再阻塞，建议 A 撤回。

## 控制台快照与双断点测量

打开页面后控制台自动打印一次完整状态快照。随时手动执行：

```js
DIPLOMAT.print()             // 打印完整 S
DIPLOMAT.snapshot()          // 返回对象
DIPLOMAT.measure()           // 双断点四项同屏 + 横向滚动检测
DIPLOMAT.adapters.current.id // "mock" 或 "http"
```

## 功能对照

| # | 行为 | 操作 |
|---|---|---|
| 1 | 三视图切换 | 报价板 / 对话 / 情报 |
| 2 | 报价板编辑 | 改任意条款下拉 → 草稿徽标 + 版本不变 |
| 3 | 卡牌选择 | 点手牌 → 预演四格联动 |
| 4 | 提交与幂等 | 提交 → 入账 1 笔；同键重复拦截 |
| 5 | 6 个错误码 | DEMO 面板逐个注入 |
| 6 | 模型降级 | `MODEL_UNAVAILABLE` → 左栏/情报空态，报价板照常 |
| 7 | 版本冲突合并 | `VERSION_CONFLICT` → 红条 + 草稿保留 → 合并 → 同键重提 |
| 8 | 未决条款禁用 | 查看协议 → 接受按钮禁用 + 原因 |
| 9 | 终局四维 | 顶栏「终局 / 复盘」→ 评级 + 四维 + feedback |
| 10 | 版本四处一致 | 顶栏 / 报价板底部 / 抽屉 / 终局 |
| 11 | 骨架 | 刷新后 1.1s 骨架退场 |
| 12 | 提交本轮总结 | 只记录、不推进轮次（K3=B） |

## 已裁决

| 编号 | 结论 |
|---|---|
| K3 | **B**：按钮为「提交本轮总结」，不推进轮次；轮次仅由报价提交推进 |
| K5 | **C＋B**：C 口径/落库、B 模型分/feedback、A 透传；D 不生成（2026-11-15 裁决） |
| K1/K2/K4/K6/K7/K8 | 按 `docs/state-contract.md` §0.3 默认值执行，代码内留 K/P 注释 |

## 不提交

`.codeartsdoer/`、`.arts/`、`node_modules/`、`demo/raw/`、`*.mp4`、真实密钥。
本项目无 `node_modules`；密钥用 `.env.example` 占位。
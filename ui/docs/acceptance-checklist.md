# T3 验收核对表（双断点 · 交互态）

> 对应：`docs/ia-design.md` §8 十五条第 1–6、8–12、14 项；`docs/state-contract.md` v2；`docs/demo-storyboard.md` 镜头 09。
> 用法：每项按「操作路径 → 预期 → 截图点」执行，通过就在表格打勾。任一项失败按最后一节返工。
> 证据目录建议：`docs/evidence/t3/`，文件名按本文命名，**只放截图，不放录屏原片**。

## 0. 前置（每次开拍前）

| # | 项 | 标准 |
|---|---|---|
| 1 | 浏览器 | Chrome / Edge 最新稳定版，缩放 **100%** |
| 2 | 窗口 | 先用 **1440×900**，再用 **1920×1080**；用系统窗口，不用 F12 设备模拟 |
| 3 | 页面 | 强刷一次（Ctrl+Shift+R），等骨架退场 |
| 4 | 初始态 | `v12`、`R3/6`、行动点 `3/5`、未决 2 条；若被上一轮改动，点 DEMO → 复位场景 |
| 5 | 工具栏 | 书签栏、扩展栏隐藏；系统通知关闭 |
| 6 | Console | 打开 DevTools Console，保留输出用于截图 |

## 1. 双断点四项同屏（ia-design §8 #1–#6）

| # | 检查项 | 操作路径 | 预期 | 截图点 |
|---|---|---|---|---|
| 1 | 1440×900 主报价板可见 | 窗口拉到 1440×900 → 强刷 → 看中央 | 5 条条款行完整可见；报价板底部「版本 v12」可见 | 中央 `报价板` 整块 |
| 2 | 1440×900 行动预演可见 | 看中央底部 | 预演四格（对方反应 / 行动点 / 风险 / 依据）全部可见，不是弹层 | `#rehearsal` 整条 |
| 3 | 1440×900 手牌可见 | 看页面底部 | 3 张策略卡 + 行动点 `3 / 5` + 「提交本轮总结」同屏 | `#hand` 整条 |
| 4 | 1440×900 终局入口可见 | 看顶栏右侧 | 「终局 / 复盘」按钮完整可见，不被遮挡 | 顶栏右侧 |
| 5 | 1920×1080 同上四项 | 窗口拉到 1920×1080 → 不刷新 | 四项仍同屏；左右栏加宽，中央更宽 | 全景一张 |
| 6 | 无横向滚动 | 两档分别看页面底部 | 无横向滚动条；`window.scrollX` 恒为 0 | 页面底部右侧 |

## 2. Console 一键测量（截图证据）

在两个断点分别执行：

```js
DIPLOMAT.measure()
```

预期输出（数值允许 ±1px）：

| 断点 | `viewport.w/h` | `noHorizontalScroll` | `stage/rehearsal/hand/finaleBtn` 的 `inViewport` |
|---|---|---|---|
| 1440×900 | `1440 / 900` | `true` | 全部 `true` |
| 1920×1080 | `1920 / 1080` | `true` | 全部 `true` |

截图：`console.table` + 紧随其后的 JSON。若抽屉已打开，`drVer` 也应 `inViewport:true`；未打开时该项可能为 `false`，属正常。

> 测量项：`stage`、`rehearsal`、`hand`、`finaleBtn`、`bdScroll`、`mVer`、`bdVer`、`drVer`。

## 3. 十五条自检逐条（#7–#15 补充）

| # | 条款 | 操作路径 | 预期 | 截图点 |
|---|---|---|---|---|
| 7 | 数字同源 | Console `DIPLOMAT.snapshot()` → 对比右栏与手牌 | 筹码 72、让步 2、行动点 3/5 与快照一致；改条款后版本不变、草稿 +1 | Console JSON + 右栏同框 |
| 8 | 版本三处一致 | 顶栏 `#mVer`、报价板 `#bdVer`、打开抽屉 `#drVer` | 三处文本完全相等（`v12`） | 三处版本同框（可拼接） |
| 9 | 加载骨架 | 强刷 → 1.1s 内截图 | 报价板 5 行骨架、左栏 4 行骨架；手牌与提交禁用 | 骨架瞬间 |
| 10 | 失败保留草稿 | 改 2 条条款 → DEMO 选 `TIMEOUT` → 提交 | 草稿徽标仍「2 处改动」；按钮变「重试提交（同一笔）」 | 草稿徽标 + toast |
| 11 | 重试不双记账 | DEMO 选 `SESSION_BUSY` → 提交 → 等自动重试 | 顶栏「处理中」→ 成功；「已记账行动 1 笔」；同一键再点被拦截，仍 1 笔 | 计数 + 拦截 toast |
| 12 | 未决条款解释 | 查看协议 → 看接受按钮上方 | 按钮禁用；列出「第 04、05 条」+「尚未被任一方报价覆盖」 | 抽屉底部 |
| 13 | 不显示对方底牌 | 右栏 BATNA + 全页搜索 | 对方恒「未知」；无对方 BATNA 真值、无 `net_gain` | 右栏 BATNA |
| 14 | 估计值 + 可信度 | 右栏对方态势 + 报价板对方列 | 有「估计值」横幅；每个数值带「估计」标签 + `%` | 右栏整块 |
| 15 | 错误码不自造 | DEMO 逐个注入 6 码 | 展示 JSON 只有 `error` + `detail`；6 码外统一行内红条 + 原文 detail，不静默 | toast / 行内红条 |

## 4. 七类交互态

| # | 交互态 | 操作路径 | 预期 |
|---|---|---|---|
| 1 | 加载骨架 | 强刷 | 骨架只覆盖取数区；报价板/左栏有骨架，手牌禁用 |
| 2 | 空场景 | Console：`D.store.get().clauses=[]; D.store.get().cards=[]; D.store.get().intelCards=[]; D.store.get().facts=[]; D.store.get().timeline=[]; D.store.notify()` | 报价板「本场暂无条款」、手牌「暂无可用策略卡」、情报/事实/纪要各自空态；不是白屏 |
| 3 | 失败 | DEMO 选 `INVALID_ACTION` → 提交 | 报价板顶部行内红条 + 错误码；草稿保留 |
| 4 | 超时 | DEMO 选 `TIMEOUT` → 提交 | toast 含 `{"error":"TIMEOUT","detail":...}`；按钮「重试提交（同一笔）」；再点成功 |
| 5 | 重复点击 | 提交按钮快速点 3 次 | 只有一笔入账；其余点击被 `inflight` / 幂等键拦截并有提示 |
| 6 | 版本冲突 | DEMO 选 `VERSION_CONFLICT` → 提交 → 合并 → 重提 | 红条显示本地/服务端版本；草稿计数保留；合并后同键重提成功 |
| 7 | 终局只读 | 打开「终局 / 复盘」→ 尝试点背景条款/手牌 → Console 调 `D.store.commit()` | 覆盖层挡住背景；`commit()` 不新增账本；终局内按钮仍可用 |

## 5. 截图命名

| 文件名 | 内容 |
|---|---|
| `t3-1440-four.png` | 1440 全景（四项同屏） |
| `t3-1920-four.png` | 1920 全景 |
| `t3-measure-1440.png` | Console `DIPLOMAT.measure()` |
| `t3-measure-1920.png` | 同上 |
| `t3-skeleton.png` | 骨架瞬间 |
| `t3-empty.png` | 空场景 |
| `t3-timeout.png` | 超时 + 重试按钮 |
| `t3-idempotent.png` | 重试后仍 1 笔 |
| `t3-conflict.png` | 冲突条 + 草稿计数 |
| `t3-finale-readonly.png` | 终局只读 |

## 6. 失败判定与返工

| 失败现象 | 先查 | 返工点 |
|---|---|---|
| 任一项 `inViewport:false` | 窗口是否 100% / 系统缩放；对应固定高度 | `app.css` 的 `--h-topbar/topicbar/tabs/rehearsal/hand` |
| `noHorizontalScroll:false` | 是否有 `min-width` 撑开；`html,body overflow` | `#body` 栅格与 `.col` 的 `min-width:0` |
| 三处版本不一致 | 组件是否各自存了副本 | 渲染层只读 `state.version` |
| 空态仍是白块 | 组件是否漏空态分支 | `stage/hand/leftColumn/drawer` 的 `length ? ... : empty` |
| 点击无反馈 | 按钮是否 disabled 且无提示 | 加 `title` 或 toast；禁用必须有原因 |
| 终局仍可提交 | `store` 守卫是否被绕过 | `commit/endRoundSummary/setDraft/selectCard` 的 `finaleOpen` 守卫 |
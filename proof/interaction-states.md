# T3 异常状态截图清单（proof/）

> 每条按「触发方式 → 屏幕表现 → 截图点 → 建议文件名」执行。
> 环境：Chrome/Edge 最新版，缩放 100%，窗口 1440×900；默认 mock；真实模式按 `ui/README.md` 注入 `DIPLOMAT_CONFIG`。
> 本机 headless 浏览器被系统策略拒绝，截图需人工采集；**截图只放本目录，不放录屏原片**。

## 1. 加载骨架

| 项 | 内容 |
|---|---|
| 触发 | 强刷 `ui/index.html`（或 `py serve.py` 后刷新），1.1s 内截屏 |
| 屏幕表现 | 报价板 5 行骨架、左栏解说 4 行骨架；手牌与「提交本轮总结」禁用；顶栏正常 |
| 截图点 | 中央报价板 + 左栏 + 手牌 |
| 文件名 | `state-01-skeleton.png` |

## 2. 空场景（条款为空数组）

| 项 | 内容 |
|---|---|
| 触发 | Console：`D.store.get().clauses=[]; D.store.get().cards=[]; D.store.get().intelCards=[]; D.store.get().facts=[]; D.store.get().timeline=[]; D.store.notify()` |
| 屏幕表现 | 报价板「本场暂无条款」；手牌「暂无可用策略卡」；情报/事实/纪要各自空态；无白屏 |
| 截图点 | 中央 + 手牌 + 左栏 + 情报视图 |
| 文件名 | `state-02-empty.png` |

## 3. 业务失败（6 码）

| 项 | 内容 |
|---|---|
| 触发 | DEMO 面板选 `INVALID_ACTION` → 提交（先改一条条款） |
| 屏幕表现 | 报价板顶部行内红条：`INVALID_ACTION` + 中文 `detail`；草稿徽标仍在 |
| 截图点 | 行内红条 + 草稿徽标 + toast |
| 文件名 | `state-03-invalid.png` |

## 4. 服务不可用（G2 新通道）

| 项 | 内容 |
|---|---|
| 触发（真实模式） | 注入 `{adapter:"http", httpBase:"http://127.0.0.1:9999"}` → 提交 |
| 触发（远程停服） | 后端停止后提交；或把 `httpBase` 指向返回 HTML 的地址 |
| 触发（500） | 后端未捕获异常返回 `{"error":"INTERNAL_ERROR","detail":"服务内部错误，请稍后重试。"}` → 走服务不可用通道，不自动重试 |
| 屏幕表现 | 连接灯「服务不可用」；行内红条「服务暂不可用，草稿已保留 · status … · 片段」；toast 同文案 + JSON；**只有 1 次请求，不自动重试**；草稿与选中卡保留 |
| 截图点 | 顶栏连接灯 + 行内红条 + Network 请求数 + 草稿徽标 |
| 文件名 | `state-04-service-down.png` / `state-04-network.png` |

## 5. 超时软提示（G8）

| 项 | 内容 |
|---|---|
| 触发（真实模式） | 后端故意挂起；提交后等 10 秒 |
| 触发（mock 演示） | 注入 `{adapter:"mock", mockDelayMs:12000}` → 提交 → 等 10 秒 |
| 屏幕表现 | 提交按钮旁出现「上游仍在处理，已等待 12s…」+「取消等待」；150 秒硬超时不变；草稿保留 |
| 取消后 | 点「取消等待」→ toast「已取消等待，草稿保留」；请求中止；不产生记账 |
| 截图点 | 软提示条 + 取消后的 toast |
| 文件名 | `state-05-slow-hint.png` / `state-05-cancel.png` |

## 6. 重复点击 / 幂等

| 项 | 内容 |
|---|---|
| 触发 | DEMO 选 `SESSION_BUSY` → 提交 → 自动重试成功；同一键再点提交 |
| 屏幕表现 | 「已记账行动 1 笔」；第二次点击 toast「该行动已记账，未重复提交」；计数仍 1 |
| 截图点 | 计数 chip + 拦截 toast |
| 文件名 | `state-06-idempotent.png` |

## 7. 版本冲突

| 项 | 内容 |
|---|---|
| 触发 | DEMO 选 `VERSION_CONFLICT` → 提交（草稿先留 2 处） |
| 屏幕表现 | 顶部红条「版本冲突：本地 vX，服务端 vY。草稿 2 处改动已保留。」+「拉取最新并合并」；提交按钮禁用 |
| 合并后 | 版本更新、草稿保留、同键重提成功 |
| 截图点 | 冲突条 + 草稿计数 + 合并后 toast |
| 文件名 | `state-07-conflict.png` |

## 8. 终局只读

| 项 | 内容 |
|---|---|
| 触发 | 点顶栏「终局 / 复盘」 |
| 屏幕表现 | 覆盖层全屏；背景条款/手牌不可点；`D.store.commit()` 不新增账本；终局内返回/新一场/导出可用 |
| 截图点 | 终局四维 + 背景被遮挡 |
| 文件名 | `state-08-finale-readonly.png` |

## 9. 后端未就绪降级（不白屏）

| 项 | 内容 |
|---|---|
| 触发 | 注入 `{adapter:"http"}`（不填 `httpBase`）或填错端口；刷新 |
| 屏幕表现 | 八区域框架完整渲染；顶栏 `R? / 6`、`v0`、连接灯「服务不可用」；报价板空态；无 uncaught 异常刷屏 |
| 恢复 | 配好 `httpBase` 后刷新，或点「重新开局」 |
| 截图点 | 顶栏 + 空框架 + Console 无红色异常 |
| 文件名 | `state-09-backend-not-ready.png` |

## 10. 会话失效（404 SESSION_NOT_FOUND）

| 项 | 内容 |
|---|---|
| 触发 | 服务重启后，用旧 `session_id` 提交 |
| 屏幕表现 | 提示「会话不存在或服务已重启」+「重新开局」按钮；不白屏 |
| 截图点 | 失效提示条 + 重新开局按钮 |
| 文件名 | `state-10-session-lost.png` |

## 11. 接受协议（A 第二轮 Q1）

| 项 | 内容 |
|---|---|
| 触发 | 查看协议 → 接受协议（未决条款先清零；若仍有未决，引擎 400 `INVALID_ACTION`） |
| 请求 | `POST /session/{id}/action`，`action_type:"accept"`、`offer_patch:{}`、`expected_effect/public_message` 非空 |
| 屏幕表现 | 成功后 `status:"ended"` → 终局；`speaker_score` 为 null 时按 null 态，不填零分 |
| 截图点 | Network 请求体 + 终局覆盖层 |
| 文件名 | `state-11-accept.png` |

## 12. 数值型条款输入（A 第三轮 Q1）

| 项 | 内容 |
|---|---|
| 触发 | 真实模式投影含 numeric 条款（如 `芯片算力门槛` 100–5000 / step 100 / 初始 800） |
| 屏幕表现 | 该行显示 number 输入 + 单位，min/max/step 生效；改动后草稿计数 +1；提交的 `offer_patch.option` 为数值 |
| 截图点 | 数值输入行 + 草稿徽标 + Network 请求体 |
| 文件名 | `state-12-numeric-clause.png` |

## 采集顺序建议

1 → 2 → 3 → 6 → 7 → 8（mock 一次拍完）
4 → 5 → 9 → 10（真实模式/停服，需 A 的端口）
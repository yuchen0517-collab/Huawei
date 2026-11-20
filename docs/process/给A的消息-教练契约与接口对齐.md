# 给 A 的消息 · 教练契约 + 接口对齐（T7 · 2026-11-16）

> 背景变化：路径 B 已完成——`Diplomat-components(1)` 新 UI 升级为主 UI，六错误码 / 幂等 / 草稿保留 / 教练三态全部按 mock 实现并通过验收（见 `验收记录-教练P1补证.md`）。前端已经**就绪**，只差 A 的接口回签即可从 mock 切 http。
> 用法：下面「转发正文」直接复制给 A，不需要其他上下文；「附录」是给 A 对照的字段表，可以一起发或他问再发。

---

## 转发正文

A，前端这边（新 UI 主路径）已经把教练和错误处理全部做完并验收通过，现在卡在你这边三件事，需要你本周表态：

**1. 教练建议的取回方案，选 A 还是 B（二选一）**
- 方案 A（我倾向）：你的 `project_snapshot()` 投影从 9 个字段扩到 10 个，加一个**可缺省**的 `coach_advice`。不加端点、不加轮询，version 和建议天然同源。缺省 = 前端显示「未生成」，不报错。
- 方案 B：新增 `GET /session/{id}/coach`，我这边退避轮询（3s→6s→12s，最多 3 次）。你要多维护一个端点，我要多管一个轮询生命周期。
- 字段结构、`evidence` 可溯源规则、禁用词表都写在 `coach-contract.md` §1，两方案的请求/响应示例也在里面（§1.4），你选一个就行，不用再讨论。

**2. `debrief` 的结果什么时候能取、失败怎么报**
现在 `POST /session/{id}/debrief` 只回 `202 {"status":"accepted"}`，我不知道生成要多久、失败了你怎么告诉我。不管你选上面哪个方案，请给我两样东西：
- ready / failed 的**判定信号**（是靠轮询 status 字段，还是事件通知）；
- 失败时的 `fail_reason`（≤30 字、面向用户的短句，不是堆栈）。

**3. 两个顺带确认（都是前端已经在读、真实接口下拿不到的字段）**
- `speaker_score` 和 `action_points` 什么时候补？前端在 `httpAdapter.js:100/:112` 已经在读，接真接口后终局四维和手牌行动点必然是空/0。
- 统一错误格式请按 `{"error":"错误码","detail":"说明"}` 返回，错误码就用这六个：`INVALID_ACTION / SESSION_BUSY / MODEL_UNAVAILABLE / ROUND_LOCKED / VERSION_CONFLICT / TIMEOUT`。另外两个约定：`SESSION_BUSY` 请带 `retry_after`（秒）；`VERSION_CONFLICT` 请带服务端最新 `version`（前端要拿它做换基线重演）；写操作请认 `Idempotency-Key` 请求头（我发的是 `action_id`，格式对齐你的 `a` + 6 位数字）。

补充一句底线：**你不回签也不阻塞演示**——前端 mock 下六错误码、幂等、教练六态都已验收通过；切 http 时如果 `httpBase` 为空，前端会诚实降级为 `MODEL_UNAVAILABLE`，不做假成功。但你越晚定，第 8 天联调窗口越窄。

—— D

---

## 附录：前端已实现的对接面（供 A 对照）

### A 需要提供的字段

| 位置 | 字段 | 说明 |
|---|---|---|
| 投影 / coach 端点 | `coach_advice` | 结构见 `coach-contract.md` §1.1–1.3；`status ∈ pending/ready/failed`；`items[]` 必带 `id/kind/title/text/evidence` |
| `evidence[]` | `action_id` | 必须能在我方行动账本查到（`state.actions`），查不到整条 item 被前端过滤 |
| `coach_advice` | `basis_version` | 过期判定只看它：`basis_version < state.version` → 显示「基于 vX 的建议」 |
| 错误响应 | `{error, detail}` | 六错误码；`SESSION_BUSY` 附 `retry_after`；`VERSION_CONFLICT` 附 `version` |
| 写接口 | `Idempotency-Key` 头 | 同一意图同一 `action_id`，选卡一变即换 |

### 前端已验收的行为（mock 实测）

- 六错误码各自独立 UI 分支：定位选卡 / 倒计时自动重试 / 规则引擎降级 / 查看协议树 / 换基线重演 / 沿用同一 action_id 重试。
- 失败保留草稿：错误横幅显示「已选 N 张卡已保留」+ `action_id`，重试不重复提交（账本验证 actions 数不虚增）。
- 教练：提交成功后异步触发、失败分支不触发、每轮一次、pending 不阻塞不遮罩、建议到达不改 `round/version/ap`、证据与禁用词双重断言过滤。
- 版本号三处一致（顶栏 / 策略卡区 / 谈判树）；1440×900 与 1920×1080 无横向滚动。

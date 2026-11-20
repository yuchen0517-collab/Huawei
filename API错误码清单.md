# API 错误码清单（来源：C 规则引擎 engine/validator.py，共 18 个）

> 11/17 收敛：对外只出六个码，原始引擎码放进响应体的 `engine_error`。
> 映射表以 `C 11.12 三指数/engine/validator.py::ERRORS` 逐条核对。

## 1. 引擎内部码（18 个，全部映射到六码之一）

| 错误码 | 含义 | 对外码 |
|---|---|---|
| `SCHEMA_VIOLATION` | 行动结构不符合 schema。 | `INVALID_ACTION` |
| `UNKNOWN_ACTION_TYPE` | action_type 不在允许的枚举值内。 | `INVALID_ACTION` |
| `PATCH_NOT_ALLOWED` | 非报价类行动不得携带非空 offer_patch。 | `INVALID_ACTION` |
| `PHASE_CLOSED` | 谈判已结束，不能再提交行动。 | `ROUND_LOCKED` |
| `DUPLICATE_ACTION` | action_id 已生效过。 | `INVALID_ACTION`（表外兜底；API 层 action_id 由服务端生成，正常不可达） |
| `VERSION_CONFLICT` | 引擎内部版本不一致。 | `VERSION_CONFLICT` |
| `AGREEMENT_HAS_OPEN_ISSUES` | 还有未决条款，不能接受协议。 | `INVALID_ACTION` |
| `NO_COUNTERPART_OFFER` | 对方还没有报价，不能接受。 | `INVALID_ACTION` |
| `ACTION_POINTS_INSUFFICIENT` | 本轮行动点已用完。 | `ROUND_LOCKED` |
| `UNKNOWN_CLAUSE` | 引用了不存在的条款。 | `INVALID_ACTION` |
| `UNKNOWN_OPTION` | 枚举型条款给了不在 options 里的取值。 | `INVALID_ACTION` |
| `TERM_LOCKED` | 条款已锁定，不能再改。 | `ROUND_LOCKED` |
| `VALUE_OUT_OF_RANGE` | 数值型条款超出 range。 | `INVALID_ACTION` |
| `REDLINE_VIOLATION` | 方案触碰红线。 | `INVALID_ACTION` |
| `FINAL_OFFER_ALREADY_DECLARED` | 已声明过最后报价，不得再次声明。 | `ROUND_LOCKED` |
| `FINAL_OFFER_LOCKED` | 已声明最后报价，不能再修改条款。 | `ROUND_LOCKED` |
| `FINAL_OFFER_EMPTY` | 最后报价没有带任何条款。 | `INVALID_ACTION` |
| `WALK_AWAY_FORBIDDEN` | 本场景不允许退出谈判。 | `INVALID_ACTION` |

> 映射表没覆盖到的引擎码（当前只有 `DUPLICATE_ACTION`）一律归 `INVALID_ACTION`，
> 不发明第七个对外码；原始码仍写进 `engine_error`。

## 2. 对外六码 ← 内部码

| 对外 `error` | HTTP | 收纳的内部码 |
|---|---:|---|
| `INVALID_ACTION` | 400 | `SCHEMA_VIOLATION` / `UNKNOWN_ACTION_TYPE` / `PATCH_NOT_ALLOWED` / `UNKNOWN_CLAUSE` / `UNKNOWN_OPTION` / `VALUE_OUT_OF_RANGE` / `REDLINE_VIOLATION` / `AGREEMENT_HAS_OPEN_ISSUES` / `NO_COUNTERPART_OFFER` / `FINAL_OFFER_EMPTY` / `WALK_AWAY_FORBIDDEN`（+ 表外引擎码兜底） |
| `ROUND_LOCKED` | 409 | `PHASE_CLOSED` / `ACTION_POINTS_INSUFFICIENT` / `TERM_LOCKED` / `FINAL_OFFER_ALREADY_DECLARED` / `FINAL_OFFER_LOCKED` |
| `VERSION_CONFLICT` | 409 | `VERSION_CONFLICT`（重复意图走幂等回放，不报错）；响应带顶层 `version` 与 `current_state` |
| `SESSION_BUSY` | 409 | `SESSION_BUSY` + `retry_after`（秒，当前 1） |
| `MODEL_UNAVAILABLE` | 503 | 模型 5xx / 无 Key / 连续失败 / 输出不合规（不是引擎码） |
| `TIMEOUT` | 504 | 模型连接或读超时；`engine_error: "MODEL_TIMEOUT"`，文案「对手模型响应超时，本次未提交，可原样重试。」 |

## 3. 六码之外保持原名的 API 码

| 错误码 | HTTP | 说明 |
|---|---:|---|
| `SESSION_NOT_FOUND` | 404 | 会话不存在或服务已重启。 |
| `INVALID_AGENT` | 400 | 临时场景只支持对手 `us`。 |
| `INVALID_SCENARIO` | 400 | 场景文件或 scenario_id 不合法。 |
| `INVALID_REQUEST` | 400 / 422 | 传输字段、请求体、意图号冲突等。 |
| `DEBRIEF_NOT_AVAILABLE` | 409 | 未终局；带 `fail_reason`（面向用户）与 `detail`（技术原因）。 |
| `INVALID_JSON` | 400 | 请求体不是合法 JSON。 |
| `NOT_FOUND` / `METHOD_NOT_ALLOWED` / `HTTP_ERROR` | 404 / 405 / 其他 | 路由层。 |
| `INTERNAL_ERROR` | 500 | 未捕获异常 / 持久化失败。 |
| `AUTO_STATUS_ERROR` | 409 | 自动推演状态机不可安全恢复（`/auto_step` 专有）。 |

## 4. 错误响应形状

```json
// INVALID_ACTION（400）
{"error": "INVALID_ACTION", "detail": "条款 'x' 不存在。", "engine_error": "UNKNOWN_CLAUSE"}

// ROUND_LOCKED（409）
{"error": "ROUND_LOCKED", "detail": "谈判已结束，不能再继续自动推进。", "engine_error": "PHASE_CLOSED"}

// VERSION_CONFLICT（409）
{"error": "VERSION_CONFLICT", "detail": "客户端基线版本与服务端当前版本不一致……", "version": 7, "current_state": {"...": "18 字段投影（含 speaker_score）"}}

// SESSION_BUSY（409）
{"error": "SESSION_BUSY", "detail": "本会话有另一轮正在处理，请稍后重试；本次未推进。", "retry_after": 1}

// MODEL_UNAVAILABLE（503）
{"error": "MODEL_UNAVAILABLE", "detail": "AI 对手暂时不可用或返回内容不合规，本轮未推进，请稍后重试。"}

// TIMEOUT（504）
{"error": "TIMEOUT", "detail": "对手模型响应超时，本次未提交，可原样重试。", "engine_error": "MODEL_TIMEOUT"}

// DEBRIEF_NOT_AVAILABLE（409）
{"error": "DEBRIEF_NOT_AVAILABLE", "detail": "复盘态仅在终局后开放：当前 status='active'……", "fail_reason": "谈判尚未结束，复盘暂不可用"}
```

统一结构为 `{error, detail}`，按需附加 `engine_error` / `retry_after` / `version` / `current_state` / `fail_reason`。
`base_version` 与顶层 `version` 同口径：**已提交行动数**（我方 + 对手），不是报价版本 `my_offer.version`。

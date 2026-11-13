# API 错误码清单（来源：C 规则引擎 engine/validator.py，共 17 个）

| 错误码 | 含义 |
|---|---|
| `SCHEMA_VIOLATION` | 行动结构不符合 schema。 |
| `UNKNOWN_ACTION_TYPE` | action_type 不在允许的 9 个枚举值内。 |
| `PATCH_NOT_ALLOWED` | 非报价类行动不得携带非空 offer_patch。 |
| `PHASE_CLOSED` | 谈判已结束，不能再提交行动。 |
| `DUPLICATE_ACTION` | action_id 已生效过。 |
| `VERSION_CONFLICT` | 行动与当前版本不一致。 |
| `AGREEMENT_HAS_OPEN_ISSUES` | 还有未决条款，不能接受协议。 |
| `NO_COUNTERPART_OFFER` | 对方还没有报价，不能接受。 |
| `ACTION_POINTS_INSUFFICIENT` | 本轮行动点已用完。 |
| `UNKNOWN_CLAUSE` | 引用了不存在的条款。 |
| `UNKNOWN_OPTION` | 枚举型条款给了不在 options 里的取值。 |
| `TERM_LOCKED` | 条款已锁定，不能再改。 |
| `VALUE_OUT_OF_RANGE` | 数值型条款超出 range。 |
| `REDLINE_VIOLATION` | 方案触碰红线。 |
| `FINAL_OFFER_ALREADY_DECLARED` | 已声明过最后报价，不得再次声明。 |
| `FINAL_OFFER_LOCKED` | 已声明最后报价，不能再修改条款。 |
| `FINAL_OFFER_EMPTY` | 最后报价没有带任何条款。 |

| `SESSION_BUSY` | 本会话有另一轮正在处理，请稍后重试；本次未推进。（HTTP 409，API 层） |
| `MODEL_UNAVAILABLE` | 模型连续失败/超时，未伪造行动，可重试。（HTTP 503，API 层） |

> 其余 HTTP 状态码约定（如 SESSION_BUSY、MODEL_UNAVAILABLE、会话不存在等）见 api.py 的 ApiError 定义；HTTP 400=参数校验失败，404=会话不存在，405=方法不允许，422=请求体校验失败，500=未捕获异常；错误响应统一为 {code, message} 结构。
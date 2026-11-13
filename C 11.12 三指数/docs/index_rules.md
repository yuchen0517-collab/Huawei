# 三指数实现口径

## 1. 总原则

模型只输出离散标签（`action_type`、`magnitude`、可选的 `effect_labels`），
所有数值由引擎查表或计算得出。任何直接给数值的字段（`interest_delta`、
`image_delta`、`trust_delta`、`delta`）在 schema 层就会被 `SCHEMA_VIOLATION`
拒绝，且整批不生效。

## 2. Interest：由条款效用计算

```
score(条款, option, 某方) ∈ [0, 1]
utility(方案, 某方) = Σ 条款权重 × score
interest = round_half_up(utility × 100)
```

- 数值型条款：`score = 1 - |option - ideal| / (range[1] - range[0])`，
  理想点为 1.0，区间端点为 0.0。
- 枚举型条款：直接查 `options[].score[party]`，未知 option 返回 0.0 并由
  校验层报 `UNKNOWN_OPTION`。
- 每次提交报价，双方 Interest 各重算一次，写入 `index_change` 事件。

**为什么不由发言查表：** 口头让步不改变条款，就不该改变利益值。利益是在
条款里拿到的，不是嘴上说的。由效用计算天然挡住“嘴上让步刷 interest”。

**Interest 是双向的：** 条款是双方共同的谈判对象。同一 option 对一方是收益，
对另一方可能是损失。`test_interest_is_bidirectional` 验证了 cn 把算力分配
从“自愿分享”推向“附带可核查机制”时，cn 的 interest 从 68 跌到 50，
us 从 35 涨到 60。

## 3. Image / Trust：只影响发言方

```
最终数值 = round_half_up(查表基准值 × 该方敏感度)
```

- 查表：`index_rules.image_actions[label][magnitude]`、
  `index_rules.trust_actions[label][magnitude]`。
- 敏感度：`index_rules.sensitivity[party][index]`。
- 同一条 `personal_attack/major`：cn 敏感度 0.9 → image -9；
  us 敏感度 1.1 → image -11。差异来自系数，不来自随机数。

**为什么不做反向：** 形象和信任是“别人怎么看我”，只能由我自己的行为决定。
让对手的模型决定我的形象，等于把评分权交给对手。

## 4. 两条标签路径

### 路径 1（推荐）：`effect_labels`

成员A 的 schema 只有 `expected_effect` 和 `public_message` 两个自由文本字段，
从中做自然语言分类不可复现。因此建议在 schema 中增加可选的
`effect_labels`：模型只给 `label`、`magnitude`、可选的 `clause` / `reason`。
有该字段时直接查表。

### 路径 2（兜底）：`action_type` 映射 + patch 幅度推导

没有 `effect_labels` 时，按固定表把 `action_type` 映射为 image / trust 标签：

| action_type | image 标签 | trust 标签 |
|---|---|---|
| offer / counter_offer / conditional_exchange | constructive_proposal | conditional_concession |
| final_offer | hardline_stance | hardline_stance |
| accept | diplomatic_reframe | keep_promise |
| reject | hardline_stance | vague_stance |
| walk_away | hardline_stance | betray_ally |
| probe / statement | procedural | procedural |

档位由 patch 的实际变化幅度决定：

```
ratio = |新值 - 旧值| / 条款可谈跨度
数值型跨度 = range[1] - range[0]
枚举型跨度 = options 数量 - 1
final_offer 选到离本方理想点最远的选项时 ratio = 1.0
ratio < 0.15 → slight；< 0.45 → moderate；否则 major
空 patch → slight
```

**绝不允许第三条路径：** 用 `public_message` 或 `expected_effect` 做关键词匹配 /
情感分析来猜标签。同一句话两次可能得到不同分类，无法复现、无法测试。

## 5. clamp 留痕

指数限制在 0~100，但截断必须记录：

```json
{
  "before": 98, "after": 100, "delta": 2,
  "requested_delta": 10, "clamped": true,
  "reason": "发言标签：constructive_proposal:major",
  "source": "cn-offer-0001"
}
```

否则复盘时看到“加了 10 分只涨 2 分”却查不到原因。

## 6. 可回放

模型输出 → 校验 → 查表/计算 → 写 `index_change` 事件。回放只重放事件流，
`replay_indices(events, indices)` 是纯函数：不修改入参、只消费
`type=index_change` 的事件、按 `requested_delta` 重新 clamp。
`RulesEngine.replay()` 从场景初始指数重放，结果必须与当前 `indices` 完全一致。
# 报价版本机制

## 1. 版本号只增不减

- `current_version` 从 0 开始；只有报价类行动
  （`offer` / `counter_offer` / `conditional_exchange` / `final_offer`）
  会让它 +1。
- `accept` / `reject` / `walk_away` / `probe` / `statement` 不产生新版本。
- 版本号永不复用。

## 2. 存全量，不存 patch

`Offer.clauses` 是该行动方**已经明确表态过的条款集合**的全量，
形如：

```json
{
  "全球算力资源分配": {"option": "附带可核查机制", "note": "..."},
  "数据跨境流动": {"option": "白名单互认", "note": "..."}
}
```

合并规则：本方上一版 `clauses` + 本次 `offer_patch`。不保存 patch 历史，
也不保存“仅本次改动”。计算效用时，未表态条款回落到场景 `initial`。

`clauses` 里存的是 `{option, note}` 结构，不是裸数值；算效用时取 `.option`。

## 3. 版本冲突怎么判

成员A 当前 schema 没有 `base_version` / `target_version` 字段，且
`additionalProperties: false` 不允许客户端额外传。因此 v2 的
`VERSION_CONFLICT` 退化为**状态内部一致性检查**：

```python
expected = offers[-1].version if offers else 0
if current_version != expected:
    return VERSION_CONFLICT
```

正常流程不可触发；它的作用是在状态被外部错误修改时阻止继续结算。
建议 A 后续在 schema 增加可选 `base_version`（见 README「待 A 确认」）。

## 4. accept 的四个检查

按固定顺序执行：

1. **schema / 阶段 / 幂等**：结构合法、谈判未结束、`action_id` 未用过。
2. **NO_COUNTERPART_OFFER**：对方必须至少提交过一版报价。
3. **AGREEMENT_HAS_OPEN_ISSUES**：`open_issues` 必须为空。  
   条款处于以下任一情况即为未决：
   - 双方均未在各自最新报价中表态；
   - 双方最新报价都包含该条款，但取值不一致（取值冲突）。
   只有一方表态的条款视为对方暂未反对，不列为未决。
4. **行动点 / 红线**：行动点足够；接受后的完整方案不触碰双方红线。

`open_issues` 在每次报价后刷新：

```python
open_issues = [
    条款 for 条款 in 全部条款
    if 双方均未表态 or (双方均已表态 and 取值不一致)
]
```

由于取值冲突的条款必然留在 `open_issues` 里，`accept` 放行时双方对全部
条款的取值必然一致（或未反对），协议合并不存在二选一问题。接受后协议
覆盖全部条款，`open_issues` 清空。

## 5. 红线判定方向

红线不是笼统的“上限”或“下限”，方向由理想点决定：

| 情况 | 违规条件 |
|---|---|
| `ideal > redline`（希望越高越好） | `value < redline` |
| `ideal < redline`（希望越低越好） | `value > redline` |
| 枚举型 | `option in redlines[party]` |

报价时只检查本次 `offer_patch` 触及的条款；`accept` 时检查完整协议方案。
`probe` / `statement` / `reject` / `walk_away` 不提交方案，不做红线检查。
（场景初始方案允许是谈判起点，即使它触碰某一方红线；是否接受由后续报价与
`accept` 时的完整方案检查决定。）

## 6. 版本与终局

- 存在 `agreement`：按条款覆盖率分 `FULL_AGREEMENT`（无缺失）和
  `PARTIAL_AGREEMENT`（有缺失）。
- 协议版本引用 `current_version`（最新报价版本），审计会核对
  `agreement.version == state.current_version`。
- 完整 vs 部分只看条款覆盖率，不看情绪、不看分数。
- 版本推进本身不触发终局；终局由 `accept`、`walk_away`、僵局计数、
  轮次上限或 `finish()` 决定。
# final_offer 拦截规则

手册要求：“声明最后报价后不得无限撤销。”该规则由引擎硬拦截，不靠提示词。

## 1. 状态字段

```python
final_offer_declared_by: Dict[str, Optional[int]]   # party -> 声明时的 version
```

初始化为每方 `None`。声明后记录当时的版本号，并写入 `public_events`：

```json
{"type": "final_offer_declared", "party": "cn", "version": 3}
```

观战页据此标出“某方已锁定最后报价”。

## 2. 三条硬规则

### 规则 1：每方每局最多声明一次

```python
if action_type == "final_offer" and final_offer_declared_by[actor] is not None:
    return FINAL_OFFER_ALREADY_DECLARED
```

提示信息带上第一次声明的版本：“你已在 V3 声明过最后报价，不得再次声明。”

### 规则 2：声明后不得再修改条款

```python
if final_offer_declared_by[actor] is not None
   and action_type in ("offer", "counter_offer", "conditional_exchange"):
    return FINAL_OFFER_LOCKED
```

允许的后续行动：`accept` / `reject` / `walk_away` / `probe` / `statement`。
接受对方方案、拒绝、退出、追问、表态，都不算“撤销自己的最后报价”。

### 规则 3：最后报价必须带具体条款

```python
if action_type == "final_offer" and not offer_patch:
    return FINAL_OFFER_EMPTY
```

不能空喊“这是最后报价”却不给内容。

## 3. 对方不受限制

声明 final_offer 只约束提出方自己。对方仍可正常提
`offer` / `counter_offer` / `conditional_exchange`。
对方还价后，声明方只能 `accept` / `reject` / `walk_away`，不能再改自己的
最后报价 —— 这正是“不得无限撤销”的落地。

## 4. 错误示范

模型连续两次声明最后报价：

```python
engine.submit_action(final_offer_v1)   # ok=True，记录 V2
engine.submit_action(final_offer_v2)
# ok=False
# code="FINAL_OFFER_ALREADY_DECLARED"
# message="已声明过最后报价，不得再次声明。你已在 V2 声明过最后报价，不得再次声明。"
```

声明后再改条款：

```python
engine.submit_action(final_offer)      # 记录 V3
engine.submit_action(offer_with_new_patch)
# ok=False
# code="FINAL_OFFER_LOCKED"
# message="已声明最后报价，不能再修改条款。你已在 V3 声明过最后报价，不能再修改条款。"
```

两次调用都返回 `(False, code, message, [])`，`version`、`indices`、
`action_points`、`offers` 全部保持原样。`demo.py` 第 6 步会真实打印
`FINAL_OFFER_LOCKED`，证明拦截生效。

## 5. 与终局的关系

- 双方都声明 final_offer 但条款不一致 → 不会自动成交，需要一方 `accept`
  或进入 `DEADLOCK`。
- 一方声明 final_offer 后 `walk_away` → `WITHDRAWAL`，不算出尔反尔
  （退出不等于改口）。
- 声明后 `accept` → 按协议覆盖率判 `FULL_AGREEMENT` / `PARTIAL_AGREEMENT`。

## 6. 校验顺序

`final_offer` 三条规则位于“行动点检查”之前。理由是“你已经喊过最后报价了”
比“你没行动点了”更能解释问题。
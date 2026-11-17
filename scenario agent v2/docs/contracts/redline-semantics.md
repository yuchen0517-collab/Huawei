# Red Line 语义（hard / soft）

> 适用范围：`private_state_by_party.<party>.redlines[]` 的 `hard` 字段。
> 结论先行：引擎侧按 **hard 优先、无 hard 则取 soft** 处理。

## 1. `hard: true`

不可交换的边界。任何成交方案越过该值，直接判 `REDLINE_VIOLATION`，不进入效用比较。

## 2. `hard: false`

可交换的偏好边界。用于计算让步空间与效用，不产生硬拦截；引擎不得因它直接否决方案。

## 3. 数值型条款

取 `hard` 优先；没有 `hard` 时取 soft 作为边界。

理由：数值条款的“红线”本身就是边界值，soft 只是“更愿意让步到哪”，不是“绝不让”。

## 4. 枚举型条款

- 只有 `hard: true` 且 `op: "in"` 才产生禁用选项；
- `hard: false` 的 `op: "in"` 只影响打分偏好，不禁用选项。

## 5. 给 A 的补丁建议

在 `load_scenario.py` 增加 `_edge_redline()`，并让 `_convert_numeric` 用它替换 `_hard_redline` 调用：

```python
def _edge_redline(redlines, issue_id):
    matched = [r for r in redlines if r.get("issue_id") == issue_id]
    hard = [r for r in matched if r.get("hard") is True]
    return (hard or matched or [None])[0]
```

现在的 `_hard_redline` 只读 `hard: true`，无 hard 时返回 `None`，导致 soft 被静默跳过、边界退化为 ideal。
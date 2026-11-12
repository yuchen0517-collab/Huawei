# 三指数结算规则（A / D 对照版）

本文是 `engine/indices.py`、`scenarios/demo_scenario.json` 的口径说明。
**实现以本文件与代码为准，不以规则原文 2.1—2.3 的数值为准。**

## 一句话分工

| 指数 | 由什么决定 | 作用对象 |
| --- | --- | --- |
| Interest | 条款数值变化前后的效用差 | 双方各自计算（双向） |
| Image | 说话方的行为标签 | 只作用于说话方（单向） |
| Trust | 说话方的行为标签 | 只作用于说话方（单向） |

模型只输出 `action_type` + `magnitude`，**不输出任何数字增量**。数值由引擎计算。

## 1. 八类发言 → action_type → 三档固定值

`magnitude` 只允许 `slight` / `moderate` / `major`。下表中的三档值取自
`scenario.index_rules.image_actions` 与 `trust_actions`，并乘以说话方敏感度、
四舍五入后落账。

| A 原文发言类型 | 代码 action_type | Interest | Image（slight/mod/major） | Trust（slight/mod/major） |
| --- | --- | --- | --- | --- |
| 提出共赢方案，兼顾双方 | `constructive_proposal` | 不查表，见第 2 节 | +2 / +3 / +5 | 未定义，按 0 |
| 强硬坚持核心立场 | `hardline_stance` | 不查表，见第 2 节 | -1 / -2 / -3 | +2 / +3 / +4 |
| 有条件让步，换取利益 | `conditional_concession`（别名 `concession`） | 不查表，见第 2 节 | 未定义，按 0 | 0 / 0 / +1 |
| 程序性推进，无实质变化 | `procedural` | 不查表，见第 2 节 | 0 / 0 / +1 | 0 / 0 / +1 |
| 触及对方红线，引发对抗 | `redline_provoke` | 不查表，见第 2 节 | -3 / -4 / -5 | -1 / -2 / -2 |
| 妥协退让，损害己方利益 | `conditional_concession` + `major` | 不查表，见第 2 节 | 未定义，按 0 | 0 / 0 / +1 |
| 情绪化、指责对方 | `personal_attack` | 不查表，见第 2 节 | -5 / -7 / -10 | 未定义，按 0 |
| 巧妙运用外交辞令化解矛盾 | `diplomatic_reframe` | 不查表，见第 2 节 | +3 / +4 / +5 | 未定义，按 0 |

补充动作标签：

| action_type | Image | Trust | 用途 |
| --- | --- | --- | --- |
| `cite_rules` | +1 / +2 / +3 | 未定义 | 援引国际规则 |
| `broken_promise` | -5 / -6 / -8 | 未定义 | 出尔反尔 |
| `protect_ally` | 未定义 | +3 / +4 / +6 | 维护盟友利益 |
| `keep_promise` | 未定义 | +2 / +3 / +4 | 信守承诺 |
| `betray_ally` | 未定义 | -5 / -7 / -10 | 出卖盟友 |
| `vague_stance` | 未定义 | -2 / -3 / -4 | 立场摇摆 |

> “未定义，按 0”表示该动作在这一维没有配置值，引擎不会自行补一套。
> 如果希望“妥协退让”同时扣形象，请在场景的 `image_actions` 里补
> `conditional_concession` 条目，而不是在代码里写死第二套规则。

## 2. 为什么 Interest 走效用差

Interest 衡量的是“核心利益被满足的程度”，它必须跟**条款文本**绑定：

```text
closeness(x) = 1 - abs(x - ideal) / (hi - lo)
utility(offer, party) = Σ weight_c * closeness_c
interest_delta = round((utility_new - utility_old) * interest_scale)
```

因此：

- 只说“我愿意让步”，但条款数值没变 → `interest_delta = 0`；
- 对方提出远离我方 ideal 的方案 → 效用下降 → interest 自然下跌，不需要“红线”特殊分支；
- 同一份条款文本，对 CN 和 US 分别计算效用，所以 Interest 是双向的；
- 规则原文 2.4 表里的 `interest_delta` 列**不参与计算**，它只是教学参考。

`interest_scale` 默认 20，可在 `scenario.index_rules.interest_scale` 调整。

## 3. 为什么 Image / Trust 不反向

Image 和 Trust 回答的是“别人怎么看我”，由**我自己的行为**决定：

- 我对对方人身攻击，我的 Image 掉；
- 对方的 Image 不应该因为被我攻击而上涨；
- 同理，我出卖盟友，掉的是我的 Trust，不是盟友的。

所以引擎只把 Image / Trust 落在 `actor` 身上。规则原文里“对对方的影响是同一条目的
反向或衰减值”这一句**未实现**，这是有意为之。

例外只有一个：Interest 是双向的，因为条款是双方共同面对的客观文本。

## 4. 可回放与留痕

一次批量结算的顺序固定为：

1. 逐条 `validate_effect`，**有一条不合法就整批拒绝**，局面不变；
2. 合并条款变更，按双方效用差计算 Interest；
3. 按说话方计算 Image / Trust；
4. 每个 `(party, index)` 的变化写一条 `public_events`，带
   `before` / `after` / `delta` / `applied_delta` / `clamped` / `reason`；
   行为类事件额外带 `actor` / `action_type` / `magnitude`，标签与数值在同一条事件里，
   回放时不需要再去关联 `behavior_log`。

回放只重放 `type=index_change` 的事件，不再调用模型。代码里没有
`random`、`time.time()`、`uuid4()`，同一事件流重放结果逐位相同。

## 5. 给 D 的前端渲染建议

指数条不要只显示一个当前数字。建议每一条指数卡包含四层信息：

```text
Interest 50 → 47   ▼3
原因：专属经济区宽度 50→80，对 CN 效用下降
[事件 evt-0003] [被截断：否]
```

具体要求：

1. **显示 before → after**，不要只显示 after，否则玩家看不出这一轮做了什么；
2. **显示 reason**，直接使用事件里的 `reason` 字段，不要前端自己编解释；
3. **clamp 要可见**：`clamped=true` 时在指数条末端加“已触顶 / 已触底”标记，
   并把 `applied_delta` 与 `delta` 的差值说明白；
4. **按事件粒度展开**：一次批量结算可能产生多条事件，悬停某条指数变化时
   高亮对应的 `event_id`，方便复盘时定位到具体发言；
5. **不要用颜色单独承载正负**：同时给箭头和数字，照顾色觉障碍用户；
6. **三指数分开展示**：Interest 的变化来自条款，Image/Trust 的变化来自行为标签，
   混在一起画会让玩家误以为“说话就能涨利益”。
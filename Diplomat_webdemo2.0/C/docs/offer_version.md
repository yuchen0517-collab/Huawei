# 报价与版本伪代码（手册 5.1 第 1 行交付物）

## 一、一次报价怎么变成一个新版本

```
提交(action):
  1. 幂等检查      action_id 已在 seen_action_ids 里 → DUPLICATE_ACTION，状态不动
  2. 版本检查      action.base_version != state.current_version → VERSION_CONFLICT
  3. 合法性检查    行动点 / 条款是否锁定 / 数值范围 / 我方红线
  4. 生成新版本    新条款 = 上一版本 + offer_patch（patch 只覆盖被改的条款）
                   version = current_version + 1
  5. 落库          offers.append(offer)；current_version = version
  6. 重置僵局计数   rounds_without_offer = 0
  7. 返回          新版本 + 与上一版的差距 diff()
```

关键：**patch 是增量，不是整份替换**。否则对方上一轮谈好的条款会被悄悄冲掉。

## 二、三个"上一版"不要混

| 名字 | 含义 | 谁用 |
|---|---|---|
| 我方上一版 | 我方最近一次提交的版本 | 计算我方让步幅度 |
| 对方最新版 | 对方最近一次提交的版本 | 计算条款差距、决定能否接受 |
| 当前版本 | 全场最新版本号 | UI 显示、乐观锁 |

UI 上"当前版本 V4、协议抽屉显示 V3"这种矛盾，就是这三者没分清。

## 三、条款差距

```
diff(from_version, to_version):
  for 条款 in 并集(旧条款, 新条款):
      if 旧值 != 新值: 记入差距表 {条款: (旧值, 新值)}
  返回差距表
```

UI 只渲染差距表，不自己算。

## 四、锁定条款

- 双方都接受的条款 → `locked = True`，`locked_by = 版本号`
- 锁定的条款出现在后续 patch 里 → 直接 `TERM_LOCKED`，不进协商
- 锁定的意义：防止"谈好了又被重新打开"这种谈判里最招人恨的操作

## 五、接受的前置条件

```
accept():
  1. open_issues 非空 → AGREEMENT_HAS_OPEN_ISSUES（有未决条款不能签）
  2. 对方没有报价     → NO_COUNTERPART_OFFER
  3. agreement = 对方最新版
  4. 判终局：条款全覆盖 → 完整协议；有条款没覆盖 → 部分协议
```

注意：接受之后**不立即给分**。分数由 `evaluate()` 单独算，且必须能指出触碰了哪条红线。

## 六、反报价与最后报价

- 反报价：`kind = counter_offer`，必须基于对方最新版做增量修改
- 最后报价：`kind = final_offer`，进入 closing 阶段；之后不得无限撤销（手册 3.2）
- 基础报价不依赖抽卡；卡牌只改变行动点成本、信息获取或风险，不改条款数值

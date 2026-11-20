# C 组规则引擎修复 · 改动清单

> 日期：2026-11-12 ｜ 修改人：Kimi（经队长验证后修复）｜ 待复核人：C 组员
> 基线：`C 11.11 三指数`（v2，77 条测试全绿）；改后 79 条测试全绿 + demo 全通。
> 注意：该目录不是 git 仓库，本次为原地修改，无版本回退，建议复核后立即 `git init` 或并入团队仓库。

---

## 一、修复的问题

| # | 问题 | 严重度 | 状态 |
|---|---|---|---|
| 1 | 双方对同一条款取值冲突时仍被判"已决"，`accept` 放行且协议静默采用对方取值 | 🔴 阻塞联调 | ✅ 已修 |
| 2 | `next_round()` 把 phase 从 `bargaining` 打回 `opening` | 🟡 | ✅ 已修 |
| 3 | `FINAL_OFFER_LOCKED` / `FINAL_OFFER_ALREADY_DECLARED` 报错文案语义重复 | 🟢 | ✅ 已修 |
| 4 | demo 缺少 `AGREEMENT_HAS_OPEN_ISSUES` 拦截演示（C 的 Demo 证据链第一环缺失） | 🟡 | ✅ 已补 |
| 5 | 测试未覆盖取值冲突与 phase 转移 | 🟡 | ✅ 已补 2 条回归 |

## 二、逐文件改动

### 1. `engine/core.py` — `_refresh_open_issues()` 重写（问题 1）

**改前**：只看双方最新报价 clauses 的键**并集**，只要有一方提过就算已决。

**改后**：逐条款检查双方各自最新报价——

```python
stated = 双方最新报价中包含该条款的 option 列表
if 双方都未表态:        → 未决
elif 双方都表态但取值不一致: → 未决（取值冲突）
else（仅一方表态）:      → 视为对方暂未反对，不列为未决
```

⚠️ **设计决策（需 C 与 A 确认）**：采用「只有一方表态 = 对方暂未反对」语义，
保留了原 demo 主流程。若团队要求 accept 前双方必须对每个条款都明确表态，
把 `len(stated) == len(parties)` 改为 `len(stated) < len(parties) or 取值冲突`
即可，但 demo 流程需相应加长。

### 2. `engine/core.py` — `next_round()` phase 状态机（问题 2）

**改前**：`phase = "closing" if declared else "opening"`（bargaining 每轮被打回 opening）。

**改后**：`declared → closing`；否则 `有报价 → bargaining`；否则 `opening`。

### 3. `engine/validator.py` — 报错文案去重（问题 3）

两条 final_offer 错误的 detail 去掉句尾重复：
`f"你已在 V{declared} 声明过最后报价，不能再修改条款。"` → `f"你已在 V{declared} 声明过最后报价。"`
（`FINAL_OFFER_ALREADY_DECLARED` 同理）。完整输出示例：
「已声明最后报价，不能再修改条款。你已在 V3 声明过最后报价。」

### 4. `tests/test_rules.py` — 新增 2 条回归（21 → 23 条）

- `test_conflicting_values_keep_issue_open`：cn 报评测=50、us 报=30 →
  条款留在 open_issues，accept 被 `AGREEMENT_HAS_OPEN_ISSUES` 拦截；
  us 改口 50 后 open_issues 清空，accept 成功且协议取值=50。
- `test_phase_survives_round_advance`：offer 后 `bargaining` 跨回合保持；
  final_offer 后 `closing` 跨回合保持。

### 5. `demo.py` — 新增拦截演示（问题 4）

V2（us 还价）与 V3（cn 最后报价）之间插入：cn 在「数据跨境流动」未决时
抢发 `accept` → 被 `AGREEMENT_HAS_OPEN_ISSUES` 拦截，打印错误码并验证
状态未变；若被放行则 `SystemExit` 报错。

### 6. `docs/offer_version.md` — §4 语义同步

open_issues 定义与伪代码更新为新语义，并补充说明：取值冲突条款必然留在
open_issues，故 accept 放行时协议合并不存在二选一问题。

### 7. `README.md` — 数字与说明同步

测试总数 77 → 79；test_rules.py 21 → 23 条；demo 说明补充
`AGREEMENT_HAS_OPEN_ISSUES` 拦截。

## 三、验证证据（2026-11-12 复跑）

- `python -m unittest discover -s tests -t .` → **Ran 79 tests, OK**
- `python demo.py` → 新拦截正常触发；终局 FULL_AGREEMENT；coverage=1.0；
  双方 better_than_batna=true；审计 0 blocking 0 warning；replay 一致
- 对抗探针复测：冲突拦截 ✅ ｜ 收敛后 accept 且取值正确 ✅ ｜
  phase 跨回合保持 ✅ ｜ replay 对账 ✅

## 四、建议 commit message

```
fix(engine): 取值冲突条款计入 open_issues，修复 accept 误放行

- _refresh_open_issues: 双方表态但取值不一致的条款判为未决，
  accept 不再静默采用对方取值（保留"单方表态=对方暂未反对"语义）
- next_round: phase 不再从 bargaining 回退 opening
- validator: final_offer 两条错误码文案去重
- demo: 补 AGREEMENT_HAS_OPEN_ISSUES 真实拦截演示，补齐 Demo 证据链
- tests: +2 回归（取值冲突、phase 转移），77 → 79 全绿
- docs: offer_version.md §4 与 README 同步
```

## 五、已知未修项（不阻塞联调，排入 backlog）

1. `reject` 行动无结构化记录（不指明拒绝哪版报价），A 只能从事件流推断。
2. 场景 `index_rules.scale` 配置被忽略，clamp 上下限硬编码 0/100
   （state.py / indices.py）。
3. `docs/action_schema.md` 宣称与 A 的 schema 一条不改，但校验器实际
   放行 `effect_labels`（README §7 有说明，契约文档本身需同步）。
4. README §7 的三项「待 A 确认」（effect_labels 入 schema、conditions
   结构化、base_version）仍需联调会上对齐。

# B 契约 1.1 `index_rules` 的 `interest_delta` 落点分歧

> 版本：2026-11-17 · 仅调研与记录，**未改引擎结算逻辑**
> 相关代码：`engine/indices.py`、`adapter/scenario_adapter.py`、`docs/contracts/index_rules.v1.json`（B 侧）

## 1. 结论先行

- B 1.1 的 `index_rules.v1.json` 为每个行为标签的每一档都配了 `interest_delta`；
- C 引擎的 `interest` 是**效用驱动**的，`behaviour_delta()` 只返回 `image` / `trust`，
  **没有 `interest` 结算通道**，因此这些 `interest_delta` 目前**没有落点**；
- 这是设计层面的语义分歧，不是单侧能定的实现细节；
- 在 B 与队长裁决前，适配层已明确**忽略** `interest_delta` 并记结构化 warning
  `INTEREST_DELTA_UNSUPPORTED`，**不静默丢弃**（见 `_normalize_index_rules`）。

## 2. 两边的 interest 语义差异

| | B 契约 1.1 | C 引擎现状 |
|---|---|---|
| 数据来源 | 行为标签直接加减 | 条款效用计算 |
| 结算入口 | `index_rules.<label>.<magnitude>.interest_delta` | `engine/indices.py::utility()` → `interest_value()` |
| 计算方式 | `interest += interest_delta`（按标签查表） | `interest = round(sum(weight × score(option)) × 100)` |
| 与方案的关系 | 与具体条款取值无关 | 完全由方案里各条款的取值决定 |
| 复现性 | 只需行为日志 | 由 `replay_indices()` 重算 `index_change` 事件核对 |

C 侧现状证据：

- `engine/indices.py:88-98`：`utility()` 按条款权重 × 选项效用分求和，`interest_value()` 四舍五入 ×100；
- `engine/indices.py::behaviour_delta()`：返回结构固定为 `{"image": int, "trust": int}`；
- `engine/indices.py::apply_effects()`：interest 变化来自 `new_interest - before` 的条款效用重算，
  行为标签只写 image / trust；
- `engine/core.py::replay()`：用 `index_change` 事件逐条重放，要求与当前指数完全一致。

## 3. 我方设计的依据

1. **interest 必须反映「方案本身对我方值多少」。** 谈判里利益来自条款分配，
   而不是发言姿态；把 interest 与方案解耦后，`BATNA 对比`、`agreement_quality.mean_utility`、
   终局评价都会失去统一口径。
2. **避免「说句强硬话就凭空涨利益」的非博弈论现象。** 若 `hardline_stance.major`
   直接加 6 点 interest，模型只要反复输出该标签就能刷高收益，与条款无关，
   会让博弈退化成标签套利。
3. **`replay()` 对账与 `batna_comparison` 的语义会复杂化。** `net_gain = achieved - batna`
   需要稳定的 interest 口径；行为通道叠加后，同一方案在不同发言路径下 interest 不同，
   复盘解释成本显著上升，且容易破坏「同一输入永远同一输出」的可复现性验收。

## 4. 三个可选方案与代价

### 方案 (a)：B 从 `index_rules.v1.json` 移除 `interest_delta`（或标注为 informational，引擎不读）

- **改动面**：B 侧契约与文档；C 侧保持现状（仅保留 `INTEREST_DELTA_UNSUPPORTED` warning）。
- **代价**：最小。B 的 13 标签表仍保留 image / trust 两列，语义完整。
- **风险**：若 B 的教练点评依赖 `interest_delta` 做展示，需要改为引用效用差。
- **C 侧推荐**：**推荐此方案**。

### 方案 (b)：C 引擎新增 interest 行为通道，与效用驱动叠加

- **改动面**：`engine/indices.py`（新增 interest 查表与结算）、`engine/terminal.py`
  （interest 口径解释）、`engine/core.py`（`replay` 事件类型）、适配层（保留 interest_delta），
  并重跑 218 条测试与 demo 四项指标。
- **代价**：大。需重新定义 interest 语义（方案效用 + 行为修正），
  会改变现有 `interest` 基线数字，可能影响 `demo.py` 与 A 的联调快照。
- **风险**：破坏可复现性设计，且「标签刷分」问题需要额外约束（例如每标签每轮上限）。
- **结论**：不建议在当前赛程内做。

### 方案 (c)：保留 `interest_delta`，但只在复盘 / 教练点评里做展示解释，不参与结算

- **改动面**：D 前端复盘面板读取 `interest_delta` 作为「行为影响提示」；
  C 侧不结算，仅在 `behavior_log` 里带原始标签与表值（需新增旁路字段）。
- **代价**：中等，需要 D 参与并确认展示口径；C 侧要保证旁路字段不进入 `replay`。
- **风险**：玩家可能误以为该值真的改变了 interest，产生「展示与结算不一致」的质疑。
- **结论**：折中方案，只有在 D 明确需要该展示时才采用。

## 5. 裁决前 C 侧的处理（已落地）

`adapter/scenario_adapter.py::_normalize_index_rules()`：

- 遇到任意标签任意档的 `interest_delta`，**不写入**引擎表；
- 汇总记一条 warning：

```json
{
  "code": "INTEREST_DELTA_UNSUPPORTED",
  "field": "$.index_rules.*.*.interest_delta",
  "message": "引擎的 interest 由条款效用计算，行为标签没有 interest 结算通道；已忽略 N 个 interest_delta（待与 B / 队长裁决，见 docs/INDEX_RULES_V1_GAP.md）。"
}
```

- 该 warning 不影响 image / trust 的无损转换，也不阻断场景加载。

## 6. 待对齐

1. **B**：确认是否接受方案 (a)，或给出 `interest_delta` 的使用场景（教学点评 / 复盘展示）。
2. **队长**：在 (a) / (b) / (c) 中裁决；若选 (b)，需要重新排期并重跑全部指数基线与 demo。
3. **D**：若选 (c)，确认复盘面板是否展示 `interest_delta`，以及展示文案如何避免误导。
# 成员C · 11-13 任务 Prompt（喂给华为云 AI 编程助手）

> 用法：把下面「====== PROMPT 开始 ======」到「====== PROMPT 结束 ======」之间的全部内容，整段复制粘贴给华为云 AI。
> 建议同时把 `C 11.12 三指数/engine/core.py`、`engine/indices.py`、`engine/state.py`、`scenarios/demo_scenario.json` 作为上下文附上。

---

====== PROMPT 开始 ======

## 角色

你是「外交谈判模拟器」项目（2026 火山杯 AI Agent 创新大赛）的资深 Python 工程师，负责**系统集成与多智能体编排**（成员C 的职责）。

## 任务

在现有规则引擎之上新增一个**场景契约适配层**，让成员B 产出的场景 JSON 能被我的规则引擎直接加载运行。这是单向只读适配：**不改 B 的契约，不改我的引擎核心逻辑**，中间加一层翻译。

## 背景：为什么必须做

我的引擎目前是"孤岛"：只能吃我自己写的 `scenarios/demo_scenario.json`。成员B 已经在 `feat/scenario-b` 分支交付了正式的**场景编译 Agent**，其输出契约 `urn:diplomat:schema:scenario:1.0` 是全项目冻结标准，字段名和结构与我的完全不同。不适配，B 生成的所有真实场景都进不了引擎，整条链路从源头就是断的。

## 一、我的引擎现状（已验证可用，禁止推倒重写）

目录 `C 11.12 三指数/`，纯标准库，79 条单元测试全绿，`demo.py` 可跑通完整一局（V1→V5，终局 FULL_AGREEMENT，coverage=1.0，replay 一致）。

```
engine/
  __init__.py   暴露 RulesEngine / load_scenario / TERMINAL_TYPES / TERMINAL_LABELS
  core.py       RulesEngine 门面（401 行）：submit_action / next_round / finish /
                public_state(viewer) / evaluate() / replay()
  state.py      NegotiationState、Offer、指数唯一写入口 apply_index_changes()（145 行）
  validator.py  JSON Schema 校验、17 类错误码、final_offer 规则、红线判定（409 行）
  indices.py    score / closeness / utility / interest / 查表 / clamp / replay（351 行）
  terminal.py   五类终局 + 六字段评价（172 行）
agent/audit/auditor.py   协议审计五项检查（只出意见，不改协议）
scenarios/demo_scenario.json
tests/  test_schema.py(14) test_final_offer.py(13) test_rules.py(23)
        test_indices.py(19) test_audit.py(10)
docs/   index_rules.md action_schema.md final_offer.md offer_version.md
```

调用方式（已对成员A 公布，不可变更签名）：

```python
from engine import RulesEngine, load_scenario
engine = RulesEngine(load_scenario("scenarios/demo_scenario.json"), session_id=sid)
ok, code, message, events = engine.submit_action(action)
view = engine.public_state(viewer="cn")   # 按观察者过滤私有底牌
evaluation = engine.evaluate()
```

### 我的引擎期望的场景结构（C 侧格式）

```json
{
  "scenario_id": "ai-governance-2026",
  "title": "全球人工智能治理框架谈判",
  "scenario_type": "assumption",
  "background": "……",
  "assumptions": ["字符串数组"],
  "max_rounds": 6,
  "deadlock_rounds": 2,
  "action_points_per_round": 3,
  "parties": [
    { "id": "cn", "name": "中国", "role": "……", "batna": 45,
      "private": { "bottom_line": "……", "notes": "……" } }
  ],
  "clauses": [
    { "name": "全球算力资源分配",
      "type": "enum",
      "options": [ {"id": "自愿分享", "score": {"cn": 0.90, "us": 0.15}} ],
      "initial": "自愿分享",
      "weights": {"cn": 0.40, "us": 0.35},
      "redlines": {"cn": ["市场主导"], "us": ["自愿分享"]} },
    { "name": "前沿模型评测门槛",
      "type": "numeric",
      "range": {"min": 0, "max": 100},
      "targets": {"cn": {"ideal": 100, "redline": 20}, "us": {"ideal": 10, "redline": 70}},
      "weights": {"cn": 0.35, "us": 0.40} }
  ],
  "index_rules": { "行为标签→三指数变化查表，含 redline_provoke": {"slight": -3, "moderate": -4, "major": -5} }
}
```

要点：
- `parties[].id` 统一小写（`cn` / `us`）
- 枚举条款 `type: "enum"`，`options[].id` 是中文选项名，`score` 是各方 0~1 的效用分
- 数值条款 `type: "numeric"`，有 `range` 和 `targets{ideal, redline}`
- `redlines` 对枚举条款是**选项黑名单**（该方绝不能接受的 option id 列表）
- `index_rules` 是引擎做三指数查表的依据，**B 的契约里完全没有这个字段**

## 二、成员B 的场景契约（输入侧，冻结不可改）

`$id: urn:diplomat:schema:scenario:1.0`，顶层 11 个业务字段为**冻结字段，不得改名、不得增减**，`additionalProperties: false`：

`scenario_id`, `title`, `scenario_type`, `background`, `assumptions`, `parties`, `issues`, `public_facts`, `private_state_by_party`, `max_rounds`, `terminal_rules`
（另有 `negotiability` 为编译器回填的只读审计字段，不属输入侧）

### B 的真实样例（节选，字段结构以此为准）

```json
{
  "scenario_id": "scn_chip_001",
  "title": "中美先进计算芯片出口管制与关键矿产交换",
  "scenario_type": "hypothesis",
  "background": "……",
  "assumptions": [
    {"assumption_id": "A1", "text": "……", "reason": "……", "affects": ["I1"]}
  ],
  "parties": [
    { "party_id": "cn", "name": "中华人民共和国",
      "role_label": "中国代表团团长", "public_position": "……" }
  ],
  "issues": [
    { "issue_id": "export_license_scope", "name": "受管制先进制程门槛",
      "type": "numeric", "unit": "nm", "range": {"min": 7, "max": 28, "step": 1} },
    { "issue_id": "license_validity_months", "name": "逐案许可有效期",
      "type": "numeric", "unit": "月", "range": {"min": 6, "max": 36, "step": 6} },
    { "issue_id": "dispute_forum", "name": "争端解决渠道",
      "type": "enumerated", "unit": "",
      "options": [
        {"option_id": "wto", "label": "世贸组织争端解决机制", "order": 1},
        {"option_id": "bilateral", "label": "双边磋商机制", "order": 2},
        {"option_id": "unilateral", "label": "单边国内法程序", "order": 3}
      ] }
  ],
  "public_facts": [ "……" ],
  "private_state_by_party": {
    "cn": {
      "goals": [
        {"issue_id": "export_license_scope", "target": 28, "weight": 0.5, "direction": "higher_better"},
        {"issue_id": "license_validity_months", "target": 24, "weight": 0.3, "direction": "higher_better"},
        {"issue_id": "dispute_forum", "target": "wto", "weight": 0.2, "direction": "ranked"}
      ],
      "redlines": [
        {"issue_id": "export_license_scope", "op": "min", "value": 14, "hard": true, "reason": "……"},
        {"issue_id": "dispute_forum", "op": "in", "value": ["wto", "bilateral"], "hard": false, "reason": "……"}
      ],
      "batna": {"utility": 40, "description": "……", "basis": "……"},
      "hidden_task": "在不公开承诺放弃反制的前提下，争取许可有效期不低于 24 个月。",
      "priority_ranking": ["export_license_scope", "license_validity_months", "dispute_forum"]
    },
    "us": { "goals": [ {"issue_id": "export_license_scope", "target": 14, "weight": 0.45, "direction": "lower_better"} ], "……": "……" }
  },
  "max_rounds": 8,
  "terminal_rules": {
    "allow_walk_away": false,
    "accept_requires_no_open_issue": true,
    "partial_agreement_allowed": true
  }
}
```

## 三、字段映射规格（请严格照此实现）

| # | B 侧 | C 侧 | 转换规则 |
|---|---|---|---|
| 1 | `parties[].party_id` | `parties[].id` | 直传，强制小写 |
| 2 | `parties[].name` / `role_label` / `public_position` | `parties[].name` / `role` | `role_label`→`role`；`public_position` 存入 `parties[].public_position`（引擎忽略但不丢弃） |
| 3 | `issues[]` | `clauses[]` | 逐条翻译 |
| 4 | `issues[].type` | `clauses[].type` | `enumerated`→`enum`；`numeric`→`numeric`；其他值抛 `ScenarioContractError` |
| 5 | `issues[].name` | `clauses[].name` | 直传（**引擎内部以 name 为条款键**）；另存 `issue_id` 到 `clauses[].issue_id` 备查 |
| 6 | `issues[].unit` | `clauses[].unit` | 直传，引擎忽略但保留 |
| 7 | `issues[].range{min,max,step}` | `clauses[].range{min,max}` | `step` 存入 `clauses[].step` |
| 8 | `issues[].options[].option_id` | `clauses[].options[].id` | 直传；`label` 存入 `clauses[].options[].label`；`order` 存入 `order` |
| 9 | `private_state_by_party[p].goals[].weight` | `clauses[].weights[p]` | 按 issue_id 回填到对应条款；**各方 weight 之和必须≈1.0，偏差>0.01 记 warning 并归一化** |
| 10 | `goals[].target` + `direction` | `clauses[].options[].score[p]`（枚举）或 `clauses[].targets[p].ideal`（数值） | 见下方【效用分推导】 |
| 11 | `redlines[{issue_id,op,value,hard}]` | 枚举→`clauses[].redlines[p]`（选项黑名单）；数值→`clauses[].targets[p].redline` | 见下方【红线映射】 |
| 12 | `private_state_by_party[p].batna.utility` | `parties[].batna` | 取 `utility` 数值；`description`/`basis` 存入 `parties[].private.batna_note` |
| 13 | `hidden_task` + `priority_ranking` | `parties[].private` | `hidden_task`→`private.bottom_line`；`priority_ranking`→`private.priority_ranking`；这些**必须只经 `public_state(viewer)` 分片可见** |
| 14 | `assumptions[].text` | `assumptions[]` | 对象数组→字符串数组，取 `text`（保留 `assumption_id` 前缀） |
| 15 | `max_rounds` | `max_rounds` | 直传 |
| 16 | `terminal_rules.accept_requires_no_open_issue` | — | `true` 时保持引擎现有 `AGREEMENT_HAS_OPEN_ISSUES` 拦截；`false` 时需在适配结果里置 `allow_accept_with_open_issues: true` 并让引擎跳过该检查 |
| 17 | `terminal_rules.allow_walk_away` | — | `false` 时置 `allow_walk_away: false`，引擎收到 `walk_away` 应返回错误码 `WALK_AWAY_FORBIDDEN`（新增） |
| 18 | `terminal_rules.partial_agreement_allowed` | — | 映射到引擎的 `PARTIAL_AGREEMENT` 终局判定开关 |
| 19 | `scenario_type` | `scenario_type` | B 枚举是 `documented`/`hypothesis`，**直传不改**。注意：我旧的 demo 场景写的是 `assumption`，不在 B 的枚举内——适配层遇到 `assumption` 应归一化为 `hypothesis` 并记 warning |
| 20 | `public_facts` | `public_facts` | 直传保留，引擎不用（供事实卡核对） |
| 21 | — | `deadlock_rounds` | B 无此字段，默认 `2` |
| 22 | — | `action_points_per_round` | B 无此字段，默认 `3` |
| 23 | — | `clauses[].initial` | B 无此字段。枚举取 `order` 最小的 option；数值取 `range.min`。**必须记 warning 提示"初始值由适配层推导，建议 B 补充"** |
| 24 | — | `index_rules` | B 无此字段。注入我的默认查表（从 `docs/index_rules.md` 的口径生成常量），并记 warning |

### 【效用分推导】goals → score / targets

`direction` 三种取值：

- **`higher_better`（数值条款）**：`score = (value - min) / (max - min)`，线性归一到 0~1
- **`lower_better`（数值条款）**：`score = (max - value) / (max - min)`
- **`ranked`（枚举条款）**：以 `target` 指向的 option 为 1.0，其余按 `order` 与 target 的 `order` 差值线性衰减，最小不低于 0.0。衰减步长 = `1 / (len(options) - 1)`（options 只有 1 个时全为 1.0）

数值条款同时把 `target` 写入 `clauses[].targets[p].ideal`。

### 【红线映射】

- **枚举条款 `op: "in"`**：`value` 是允许集合 → 该方红线 = **不在 value 里的所有 option_id**，写入 `clauses[].redlines[p]`
- **枚举条款 `op: "not_in"`**：`value` 直接就是红线选项列表
- **数值条款 `op: "min"`**：表示"不得低于 value" → `clauses[].targets[p].redline = value`，方向为 `below_is_violation`
- **数值条款 `op: "max"`**：表示"不得高于 value" → `clauses[].targets[p].redline = value`，方向为 `above_is_violation`
- `hard: false` 的红线：仍映射，但附加 `soft: true` 标记，引擎判定时返回 `REDLINE_VIOLATION` 的 warning 级而非 blocking 级

⚠️ **重点**：我现有引擎的数值条款红线只有单一 `redline` 数值字段，靠 `targets[p].ideal` 与 `redline` 的大小关系隐式判方向。请检查 `engine/indices.py` 与 `validator.py` 里的红线判定逻辑，**如果需要显式方向字段才能正确判定，请新增可选字段 `redline_direction`（`below_is_violation` / `above_is_violation`），并保证不传时行为与现在完全一致**（向后兼容，79 条测试必须继续全绿）。

## 四、交付物

1. **`adapter/scenario_adapter.py`**（新建 `adapter/` 目录）
   - `class ScenarioContractError(Exception)`：契约非法时抛出，消息写明字段路径与期望值
   - `def adapt_scenario(b_scenario: dict) -> dict`：B 格式 → C 格式，返回可直接喂给 `RulesEngine` 的 dict
   - `def load_and_adapt(path: str) -> tuple[dict, list]`：读文件（**必须用 `encoding="utf-8-sig"`**，B 的文件带 BOM）→ 适配 → 返回 `(scenario, warnings)`
   - `def validate_b_contract(b_scenario: dict) -> list[str]`：校验 B 侧必填字段与枚举合法性，返回错误列表（不抛异常）

2. **`adapter/__init__.py`**：暴露 `adapt_scenario` / `load_and_adapt` / `validate_b_contract` / `ScenarioContractError`

3. **`tests/test_adapter.py`**：≥12 条测试，必须覆盖
   - 枚举条款 ranked 效用分推导正确（3 选项、target 居中时分数应为 1.0 / 0.5 / 0.0）
   - 数值条款 higher_better 与 lower_better 两个方向
   - `op: "in"` 红线取反、`op: "min"` / `op: "max"` 方向映射
   - weight 之和≠1 时归一化 + warning
   - 缺 required 字段（如 `terminal_rules`）时抛 `ScenarioContractError`
   - `type` 非法值（如 `boolean`）时抛错
   - `scenario_type: "assumption"` 归一化为 `hypothesis` + warning
   - BOM 文件能正常读取
   - **端到端**：适配后的场景能被 `RulesEngine` 加载并跑完 `demo.py` 同等流程，终局非异常
   - `public_state(viewer="cn")` **不泄露** us 的 `hidden_task` / `goals` / `batna`（信息隔离回归）

4. **`scenarios/from_b_chip_controls.json`**：把上面 B 的真实样例补全成一份完整合法的场景文件（`public_facts` 可填 2~3 条、us 侧 `goals`/`redlines`/`batna` 补全，数值自拟但需保证存在可成交区间），作为适配层的测试夹具。

5. **`docs/scenario_adapter.md`**：映射表 + 三条使用示例 + 已知限制清单

6. **`README.md` 更新**：在「怎么接」一节新增「成员B（场景编译 Agent）」子节，说明如何从 B 的契约接入；测试总数 79 → 新数字

## 五、硬约束（违反即返工）

- **只用 Python 标准库**，禁止引入 `jsonschema`、`pydantic`、`pandas` 等任何第三方依赖（我的引擎刻意保持零依赖，B 侧用了 jsonschema 但那是 B 的事）
- **禁止修改 B 的契约文件**，禁止改字段名去迁就引擎
- **禁止推倒重写引擎**。`engine/` 下只允许在 `indices.py` / `validator.py` 为支持 `redline_direction`、`allow_walk_away`、`allow_accept_with_open_issues` 做**向后兼容的最小增量修改**；改动处必须逐条在最终回复里列出 diff 说明
- **现有 79 条测试必须继续全绿**，一条都不许改断言来"让它过"
- 结算路径**禁用随机、时间、UUID、网络、LLM 调用**（可复现是硬要求，`replay()` 必须仍能对账一致）
- actor 统一小写；条款在引擎内部以 `name`（中文）为键，适配层必须保证 `name` 在场景内唯一，重复时抛错
- 所有 warning 必须是结构化 dict（`{"code": "...", "field": "...", "message": "..."}`），不要只 print 字符串
- 中文注释与文档，代码风格与现有 `engine/` 保持一致（`from __future__ import annotations`、类型标注、dataclass）

## 六、完成后请自检并在回复中报告

1. `python -m unittest discover -s tests -t .` 的完整输出（应显示 `Ran N tests, OK`，N ≥ 91）
2. `python demo.py` 是否仍全通（终局、coverage、审计、replay 四项）
3. 新增 `python -c "from adapter import load_and_adapt; from engine import RulesEngine; s,w=load_and_adapt('scenarios/from_b_chip_controls.json'); e=RulesEngine(s, session_id='t1'); print(len(w), e.state.phase)"` 的输出
4. 对 `engine/` 的每一处改动，说明改了什么、为什么、如何保证向后兼容
5. 明确列出你**没有**解决但发现的问题（例如 B 契约缺少引擎必需字段的地方），我需要拿去和 B 对齐

不要输出与上述无关的解释性文字，直接给代码和自检结果。

====== PROMPT 结束 ======

---

## 附：这个 prompt 之外，你今天还需要人工做的两件事

AI 只能写代码，下面两件必须你自己去群里问，**今天就发，别等**：

**1. 找 A 确认 `effect_labels` 字段**（阻塞级）

现状矛盾：我的 `validator.py` 里 `ALLOWED_FIELDS = REQUIRED_FIELDS | {"effect_labels"}`，主动放行了这个可选字段；但 A 的 `action_schema.json` 是 `additionalProperties: false` 且 properties 里**没有** `effect_labels`。A 的 `api.py` 用 `Draft202012Validator` 在 `adapt_client_action` → `check_flat_schema` 里**先**校验，所以任何带 `effect_labels` 的行动会在 A 那层就被 400 `INVALID_ACTION` 挡掉，**根本到不了我的引擎**。

后果：`statement` 类发言无法区分"建设性表态"和"人身攻击"（两者 action_type 都是 statement），Image / Trust 只能走路径 2 兜底推导，表达力明显变弱。

给 A 的话术：
> A，`effect_labels` 这个可选字段需要你加进 `action_schema.json` 的 properties（不加进 required）。我引擎侧已经支持并校验了，但你的 `additionalProperties: false` 会先把它拒掉，行动到不了引擎。不加的话 statement 类发言区分不出建设性表态和人身攻击，Image/Trust 只能走兜底推导。

**2. 找 A 对齐 phase 归属**（阻塞级）

A 的 `api.py` 里有 `def phase_of(round_no)`，纯按回合数推导（`round<=3 → opening`，`<=8 → bargaining`）；我的引擎是**状态机**（有报价 → bargaining，声明 final_offer → closing），已修掉"bargaining 被打回 opening"的 bug。两套 phase 并存必然打架，前端会看到互相矛盾的 phase。

给 A 的话术：
> A，你 api.py 里的 `phase_of(round_no)` 和我的引擎 phase 状态机冲突。我是按谈判进展推的（opening→bargaining→closing），你是按回合数硬推的。建议以引擎为准，你的 `project_snapshot` 直接用 `engine.public_state()["phase"]`，`phase_of` 只作为引擎不可用时的降级兜底。

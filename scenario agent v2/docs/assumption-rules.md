# 事实与假设的判定规则

> 用途：D 做 UI 标签与提示文案、B 写场景时自查、评审问"这些数据是真的吗"时的依据。
> 版本：v1.0　　最后修改：2026-11-13
> 代码闸门：`agent/scenario/models.py` 的 `R10_facts_sourced`（事实必须有来源）、`R11_assumption_traceable`（假设必须可追溯）

---

## 一、判定线只有一句话

**能不能点开看到原文。** 能，就是事实；不能，一律进假设。没有第三种。

---

## 二、五种输入情况怎么落

| 输入情况 | 判定 | 落到哪个字段 | UI 表现 |
|---|---|---|---|
| 有可靠公开资料，链接能打开原文 | 事实 | `public_facts`，`confidence: A` | 依据面板可展开，点击跳原文 |
| 有来源但属转述 / 智库估算 | 事实（低置信） | `public_facts`，`confidence: B` 或 `C` | 标注「估算，来源为第三方机构」 |
| 无来源，但为了能谈必须给个值 | 假设 | `assumptions`，必须写 `reason` + `affects` | 常驻「教学假设」标签 |
| **我方对对方底线的估计** | **估计** | 只进 `private_state`，**绝不进 `public_facts`** | 标注「估计，可信度中」，不给原始数值 |
| 议题本身不可拆成条款 | 不可谈 | 不生成场景，返回 `unsupported` + 收窄建议 | 提示页，保留原场景不覆盖 |

### 第 4 行是信息隔离的隐形杀手

「我方认为对方底线是 3%」写进 `public_facts`，A 的谈判 Agent 在给对方生成发言时就能读到它——等于把对方底牌开给了他。

手册 11.1 的信息隔离测试会挂在这里，而且是从**场景文件**里挂的，不是从 A 的代码里。

---

## 三、可信度 A / B / C 的用法

| 级别 | 含义 | 能不能当发言依据 |
|---|---|---|
| `A` | 官方一手（政府、议会、国际组织原文） | 可以，且可以要求对方回应 |
| `B` | 权威媒体或专业机构 | 可以，但应说明是媒体报道口径 |
| `C` | 待核实 / 无法复核 | **不建议**作为发言依据；UI 标灰 |

`C` 级条目由 `factcard_loader` 单独归入 `low_confidence`，`facts_index_*.json` 里也有 `low_confidence` 列表可直接读。

主场景（芯片）目前的分布：A 级 34 条、B 级 10 条、C 级 3 条（`US-11`、`US-12`、`US-19`）。

---

## 四、事实卡字段怎么映射

| 事实卡列 | 映射到 | 说明 |
|---|---|---|
| 编号（如 `CN-05`） | `fact_id` | 原样保留，便于「要求依据」时精确引用 |
| 类型（立场/行动/数字/引用/智库） | `type` | 决定它适合出现在哪类发言里 |
| 内容（≤60 字） | `text` | 已是「能被 agent 直接说出口」的长度，**不要改写** |
| 数值 | **不进 `public_facts`** | 存进 `facts_index_*.json` 的 `value_by_fact` |
| 时间 | `source.published_at` | 保留 `YYYY-MM-DD`；只到月份的保留 `YYYY-MM` |
| 来源名称 / 链接 | `source.name` / `source.url` | `url` 不是 `http(s)` 开头的**整条丢弃**（进 `invalid`，附行号） |
| 可信度 A/B/C | `source.confidence` | 其他值按 `C` 处理并告警 |
| 备注里的 `P1`–`P6` | **不进 `public_facts`** | 存进 `facts_index_*.json` 的 `stage_by_fact` |

> 为什么阶段标签不进事实本体：`docs/contracts/scenario.schema.json` 里 `public_facts` 与 `source` 都是 `additionalProperties: false`，多一个字段整份场景就过不了校验。

---

## 五、给 D 的 UI 约定

| 场景字段 | UI 元素 | 文案要求 |
|---|---|---|
| `scenario_type: "hypothesis"` | 顶部常驻横幅 | 「本场景为教学假设，不代表现实预测」，**不可关闭** |
| `scenario_type: "documented"` | 顶部小标签 | 「资料驱动」，可点击展开来源清单 |
| `public_facts[]` | 左栏「事实依据」列表 | 每条显示 `source.name` + `published_at`；点击跳 `source.url` |
| `confidence == "C"` | 该条标灰 + 「待核实」角标 | 不参与「要求依据」的默认结果 |
| `assumptions[]` | 可折叠的「假设清单」 | 显示 `text`，展开显示 `reason` |
| `R10_facts_sourced` 报错 | 「该条缺少来源」 | 指向具体 `fact_id` |
| `R11_assumption_traceable` 报错 | 「该假设缺少理由」 | 指向具体 `assumption_id` |

### ⚠️ 外链可达性（必须处理）

实测：**美国 `.gov` 域名在国内网络下无法访问**（`bis.gov`、`commerce.gov`、`ustr.gov`、`federalregister.gov` 全部超时），而 `gov.cn`、`mofcom.gov.cn` 正常返回 200。

影响：主场景 8 条事实里，中方 4 条能点开，美方 4 条点不开。

D 侧的处理：

1. 外链一律**新窗口打开**，失败时不阻塞主流程
2. 「事实依据」卡片上增加本地证据入口：`proof/sources/<fact_id>.png`
3. 演示时不现场点外链，只展示「来源名称 + 日期 + 可信度」

---

## 六、写场景时的三条自查

1. 随机抽 3 条 `public_facts`，把 `source.url` 点开——能看到原文吗？看不到就降级。
2. 逐条读 `assumptions`，问自己「这条理由站得住吗，评审问起来我能答吗」。
3. 搜一遍场景文件里有没有「对方底线」「对方权重」「对方真实意图」这类字样——出现就是泄露。

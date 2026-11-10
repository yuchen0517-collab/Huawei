# 谈判对手 Agent · demo1.1

自包含的可运行版本：**Prompt + 代码 + 配置全在这个文件夹里**，拷走即可用。

> 版本：v1.1
> 上一版：`..\`（Agent 根目录，v1.0 原型，保留作对照，不必再改）

---

## 本版改了什么

| # | 改动 | 为什么 |
|---|---|---|
| 1 | **取消发言字数限制** | 真实谈判不限制字数。复杂议题要展开，简单表态两三句就够。Prompt、代码校验、体检报告三处的 80–200 字规则全部移除 |
| 2 | 谈判主题写进 Prompt | v1.0 只说"一场正式的国际谈判"，没说谈什么，模型在凭空谈 |
| 3 | 新增 `player_indexes_update` | v1.0 只记对手的三指数，你那一方没有数据来源 |
| 4 | 首轮 `speaker_score` 明确为 `null` | 否则模型会凭空编一个分数 |
| 5 | 修正 §2.3 编号重复 | 原文档有两个 2.3 |
| 6 | 明确 `indexes_update` 是**净值** | 避免和累计值混淆 |
| 7 | **自动拼合括号错位的 JSON** | 模型会把 `feedback` 写到 `speaker_score` 外面，还多打一个 `}` 提前闭合，导致 `mood`/`round_summary` 游离在对象外。现在能救回来，并告警 |

### 关于第 7 条

模型数大括号数错了，输出会变成这样（真实踩到的）：

```
{"response": "...", "speaker_score": {...}, "feedback": "..."}   ← 这里提前闭合了
, "mood": "陷入僵局", "round_summary": "..."}                     ← 后半截成了游离数据
```

`json.loads` 会报 `Extra data`。以前直接判失败、重试三次、整局中断。
现在 `extract_json()` 会先解析出第一个完整对象，再把后面那段残片单独解析、合并回来，
并把跑到外面的 `feedback` 挪回 `speaker_score` 里。**数据保住了，同时在告警里如实记一笔。**

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `谈判对手Agent_prompt.md` | **角色 Prompt（v1.1）**，改人设、话术、输出格式都改这个 |
| `agents.json` | 配置：`_scenario` 是谈判主题；含中、美、欧、印、巴、英、土七方 Agent |
| `neg_cli.py` | 主程序：读 Prompt → 填占位符 → 调模型 → 校验 → 结算三指数 → 打印 |
| `multi_agent.py` | 独立国家 Agent：公共会场记录、私有记忆、行动状态 |
| `report.py` | 体检报告：读最新一局，给「能不能进 UI」的结论 |
| `test_validate.py` | 边界测试（30 项），验证模型输出跑偏时兜底是否生效 |
| `test_multiagent.py` | 多智能体测试：记忆隔离、多方结算、三个知识库、三方及六国连续对局 |
| `run.bat` / `report.bat` | 双击启动，自动找 Python、自动切 UTF-8 |
| `logs/` | 每局完整记录（JSON），复盘报告的数据源 |

---

## 怎么跑

```powershell
cd "D:\RainbowKATE\大学研究生时\火山杯AI\Agent\demo1.1"

.\run.bat --check          # 只验配置，1 秒
.\run.bat                  # 没配 Key 时自动转离线自检
.\run.bat --rounds 5       # 真打 5 轮
.\report.bat               # 出体检报告
```

接真模型：

```powershell
$env:DEEPSEEK_API_KEY = "sk-你的key"
.\run.bat --rounds 5
```

> `$env:` 只对当前窗口有效，双击 bat 读不到。想双击也能用就 `setx DEEPSEEK_API_KEY "sk-..."`。

### 常用参数

```powershell
.\run.bat --agent eu           # 换欧盟
.\run.bat --interactive        # 手动输入中方发言
.\run.bat --offline            # 纯离线
.\report.bat logs\run-xxx.json # 分析指定某一局
```

---

## 改哪里

| 想改什么 | 改哪个文件 | 要不要动代码 |
|---|---|---|
| 对手说的话太软 / 太冲 | `agents.json` 的 `negotiation_style` | 不改 |
| 换谈判主题、议题 | `agents.json` 的 `_scenario` | 不改 |
| 新增一个国家 | `agents.json` 加一个条目 | 不改 |
| 输出格式加字段 | `谈判对手Agent_prompt.md` 的输出格式段 + `neg_cli.py` 的校验 | **要改** |
| 三指数的取值范围 | `neg_cli.py` 的 `DELTA_LIMIT` | 要改 |
| 评分权重 | `neg_cli.py` 的 `SCORE_WEIGHTS` | 要改 |

改完配置先跑 `.\run.bat --check`，它会把 JSON 语法错误精确到第几行第几列。

---

## 排错

| 症状 | 原因 | 办法 |
|---|---|---|
| 敲 `python` 没反应 | WindowsApps 里是 0 字节假壳 | 用 `.\run.bat`，它会绕过假壳找真 Python |
| `HTTP 401` | Key 错或已删 | 去 DeepSeek 控制台重建 |
| 第 2 轮起不吐 JSON | 历史里只存了纯文本 | 已在 v1.1 修复（存完整 JSON） |
| 三指数不动 | 模型没给 `player_indexes_update` | 报告里会列为提醒，看告警明细 |

---

## 下一步

1. **跑 5 轮真模型 + `.\report.bat`**，确认 Prompt 合格（报告给 ✓）。
2. 然后做**规则引擎**：回合上限、胜负五级判定、隐藏任务完成度、复盘报告数据。
3. 再套 Web 界面（`..\..\UI设计\` 里现有的 HTML）。

当前状态：命令行验证工具，不是产品。没有胜负判定、没有复盘生成、没有界面。

# Backlog

## 2026-11-13 场景对接遗留（待三人对齐）

| 编号 | 事项 | 现状 | 待办 |
| --- | --- | --- | --- |
| 1 | B 场景软红线（hard:false）在 C 引擎格式中无对应位 | 转换器只处理硬红线；main_chip_controls 中 5 条软红线（中方 I2/I3、美方 I1/I2/I4）被跳过 | 三人对齐软红线语义后再补转换，不擅自改 B 的数据 |
| 2 | index_rules（形象/信任指数规则）B 未提供 | 转换器暂借 `C 11.12 三指数/scenarios/demo_scenario.json` 的 index_rules | 等 B 提供场景级指数规则后替换 |
| 3 | api.py 的 System Prompt 与展示用 initial_indexes 仍来自 agents.json（AI 治理题材） | **11-20 已修**：新增 `prompt_context.py`，按运行时场景生成对手 System Prompt（主题/议题/各方立场/目标排序/红线/BATNA/隐藏任务/事实与假设），初始指数改取场景 `index_rules`；默认 `ai_governance` 仍用手写文案与 agents.json 数值 | 无。回归见 `test_scenario_prompt.py`（含「Prompt 不泄露对方私牌」） |
| 4 | B 场景 enumerated 的 score 公式（P1 用 (N-order+1)/N、P2 用 order/N） | **11-20 已统一并补数据**：适配层优先读 `options[].score_by_party`；三份场景的枚举选项已写入逐方分（按各自 target 位次推导，行为不变，R16 校验 0 问题）；缺省值也改为「逐方 target 位次」，不再用 order 反推 P2。`check_score_alignment.py` 已重写为 zopa↔引擎比对并由 `test_score_parity.py` 守护，当前 6/6 一致 | 无。B 若要调整偏好，直接改场景里的 `score_by_party` 即可，无需改代码 |
| 5 | test_validate.py 仍引用 v1.1 已删除符号 apply_player_indexes；test_multiagent.py 依赖未迁移的 server.py | 两文件在全量 pytest 收集阶段即 ImportError（既有遗留，非本次引入），已在 conftest.py 的 collect_ignore 中暂时排除 | test_validate.py 待重写为 v2.0 用例矩阵；server.py 迁移进仓库后恢复 test_multiagent.py |
| 6 | 外部交付目录（C 11.12 三指数、scenario agent v2、Diplomat_webdemo2.0）被仓库 pytest 误收集 | C 的 79 条测试只能在其自身目录下运行（仓库 rootdir 下收集会 ImportError），已在 conftest.py 的 collect_ignore 中排除 | 无，属既定约束；C 的测试一律 cd 到其目录后跑 `python -m pytest tests/ -q` |
| 7 | B 分支 feat/scenario-b 的 factcard_loader.py 带 6 处未解决合并冲突标记（<<<<<<< Updated upstream），test_factcard_loader.py 无法收集 | ✅ 11/13 已在本分支解决：按 B 自己 test_factcard_loader.py 的断言统一保留 Updated upstream 一侧，B 目录 77 条测试全绿 | B 的 feat/scenario-b 分支上仍是坏的，通知她同步修复，避免下次合并把冲突标记带回来 |
## 2026-11-19 引擎口径偏离 C 基线

| 编号 | 事项 | 现状 | 待办 |
| --- | --- | --- | --- |
| 8 | 行动契约 v2 与僵局口径偏离 C 的 6b076bb 基线 | ✅ 11-20 已按语义合并并验证：保留 A 的 `check_card_action` 与 `card_payload`，同时收编 C 的多方合并、accept 前置条件、`redline_check` 按 viewer 裁剪；C 引擎套件 245 条全绿 | 推回 `feat/rules-c` 时提醒 C 不要用旧基线整体覆盖 |

## 2026-11-20 评分口径双轨（已解决）

| 编号 | 事项 | 现状 | 待办 |
| --- | --- | --- | --- |
| 9 | B 的 `zopa.py` 与引擎 `engine/indices.py` 是两套打分：enumerated 一个按 order、一个按 target；numeric 一个按比例归一、一个按整段区间 closeness；部分协议一个跳过未谈成议题、一个按现状计入 | **11-20 已统一**：numeric 改「红线锚定」（红线 0、目标 1、超目标封顶）；enumerated 改「逐方 target 位次」；新增 `terminal.package_utility`，协议评价只计协议包内条款；适配层透传 `goals[].direction`（避免「越高越好 + 上限红线」被判反）；`suggest_deal` 由 order[0] 改为可行域 max-min 均衡点 | 无。`test_score_parity.py` 已守护口径，改动这两处必须同步跑 |
| 10 | 行动校验把「双方红线」都当禁令：`validate_action` 调 `redline_violations(touched, scenario)` 时未限定参与方 | **11-20 已修**：`redline_violations` 增加 `parties` 参数，行动校验只传 `(actor,)`，终局评价仍查全部。原因：替对方守红线既不合谈判语义（对方可提出我方不能接受的方案，由我方拒绝），也会泄露对方私牌（按被拒方案反推） | 推回 `feat/rules-c` 时说明：默认行为仍是查全部，只有行动校验用 actor 过滤，别改回全局 |

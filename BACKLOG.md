# Backlog

## 2026-11-13 场景对接遗留（待三人对齐）

| 编号 | 事项 | 现状 | 待办 |
| --- | --- | --- | --- |
| 1 | B 场景软红线（hard:false）在 C 引擎格式中无对应位 | 转换器只处理硬红线；main_chip_controls 中 5 条软红线（中方 I2/I3、美方 I1/I2/I4）被跳过 | 三人对齐软红线语义后再补转换，不擅自改 B 的数据 |
| 2 | index_rules（形象/信任指数规则）B 未提供 | 转换器暂借 `C 11.12 三指数/scenarios/demo_scenario.json` 的 index_rules | 等 B 提供场景级指数规则后替换 |
| 3 | api.py 的 System Prompt 与展示用 initial_indexes 仍来自 agents.json（AI 治理题材） | 传入 B 场景时仅引擎场景切换，Prompt 文案与初始指数展示未联动 | 三人对齐后决定 Prompt 是否随场景生成 |
| 4 | B 场景 enumerated 的 score 公式（P1 用 (N-order+1)/N、P2 用 order/N） | 按 negotiability.notes 口径实现，仅在双方偏好完全相反时成立 | 若后续场景双方偏好非完全相反，需 B 给出逐方 score |
| 5 | test_validate.py 仍引用 v1.1 已删除符号 apply_player_indexes；test_multiagent.py 依赖未迁移的 server.py | ✅ 11/14 test_validate.py 已重写为 v2.0 pytest 契约矩阵并恢复收集；test_multiagent.py 因 server.py 未迁移仍在 collect_ignore 中 | server.py 迁移进仓库后恢复 test_multiagent.py |
| 6 | 外部交付目录（C 11.12 三指数、scenario agent v2、Diplomat_webdemo2.0）被仓库 pytest 误收集 | C 的 79 条测试只能在其自身目录下运行（仓库 rootdir 下收集会 ImportError），已在 conftest.py 的 collect_ignore 中排除 | 无，属既定约束；C 的测试一律 cd 到其目录后跑 `python -m pytest tests/ -q` |
| 7 | B 分支 feat/scenario-b 的 factcard_loader.py 带 6 处未解决合并冲突标记（<<<<<<< Updated upstream），test_factcard_loader.py 无法收集 | ✅ 11/13 已在本分支解决：按 B 自己 test_factcard_loader.py 的断言统一保留 Updated upstream 一侧，B 目录 77 条测试全绿 | B 的 feat/scenario-b 分支上仍是坏的，通知她同步修复，避免下次合并把冲突标记带回来 |

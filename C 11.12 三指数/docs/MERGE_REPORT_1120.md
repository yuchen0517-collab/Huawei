# 合并报告 · 2026-11-20

## 1. 合并结论

| 项 | 值 |
|---|---|
| 集成分支 | `integrate/1120` |
| 合并提交 | `1b8a5c6`（parents：`96a84c3` feat/rules-c、`d48ceb4` origin/develop） |
| 合并方式 | `git merge origin/develop --no-commit --no-ff`，冲突逐项人工处理 |
| 远程状态 | `origin/integrate/1120` 指向 `1b8a5c6`；**未直接推 develop** |

今日先补完此前被 `index.lock` 阻塞的两个提交：
- `f29bec3` 11.19 收口：redline_check 按 viewer 裁剪 + 多方 accept 修复 + 预留字段
- `96a84c3` 11.20 工作流搭建：orchestrator 状态机 + 端到端入口 + 调度交接文档

## 2. 预演与冲突清单

`git fetch origin` 直连 443 失败；系统代理 `127.0.0.1:65532` 未监听。预演与正式合并均使用本地已有 `origin/develop = d48ceb4`（2026-11-11，落后 36 个提交）。

| 性质 | 数量 | 文件 / 范围 |
|---|---|---|
| 内容冲突 | 0 | — |
| 新增 | 165 | `Diplomat_webdemo2.0/` 下全部 develop 文件（含 `__pycache__/*.pyc`） |
| 删除 | 1 | 顶层 `README.md`（`origin/develop` 树中不存在该文件） |
| 重命名 | 0 | — |
| `C 11.12 三指数/` | 0 变更 | 与 develop 无交集 |

成员A 的六个文件（`api.py` / `load_scenario.py` / `test_e2e.py` / `action_schema.json` / `neg_cli.py` / `multi_agent.py`）在 `feat/rules-c` 与 `origin/develop` 两棵树的顶层及子目录中均不存在，本次无取版对象。

## 3. 冲突解决方式

| 文件 | 性质 | 解决 |
|---|---|---|
| `README.md` | develop 删除、本地保留 | **人工合并**：保留 feat/rules-c 的仓库标题，追加「子项目」索引（webdemo2.0 与 C 11.12 的入口），未使用 `-X ours` / `-X theirs` |
| `Diplomat_webdemo2.0/**` | develop 新增 | 保留 develop 版本 |
| `C 11.12 三指数/**` | 无冲突 | 保留 feat/rules-c 版本 |

## 4. 合并后验证实测

| 命令 | 结果 |
|---|---|
| `python -m unittest discover -s tests -t .` | `Ran 241 tests ... OK` |
| `python -m pytest tests/ -q` | `241 passed, 167 subtests passed` |
| `python demo.py` | `FULL_AGREEMENT`；coverage `1.0`；audit `{"blocking":0,"warning":0}`；replay `True` |
| `python run_workflow.py` | `终局=FULL_AGREEMENT coverage=1.0 轮数=2 审计blocking=0 trace=docs\workflow_trace.json` |

## 5. 四条红线

| 红线 | 结论 | 证据 |
|---|---|---|
| ① 无断言被改 | 通过 | `git diff 96a84c3 1b8a5c6 -- "C 11.12 三指数/tests"` 为空；assert 行变化 0 |
| ② 审计 blocking=0 | 通过 | demo 实测 `{"ok":true,"issues":[],"summary":{"blocking":0,"warning":0}}` |
| ③ replay 一致 True | 通过 | demo 实测 `replay 一致：True` |
| ④ `to_public_dict` 唯一 private 过滤点 | 通过 | `engine/state.py::to_public_dict` 是唯一按 viewer 裁剪 `private_state_by_party` 的实现；`terminal.batna_comparison` / `redline_check` 是**评价格局**裁剪，`load_scenario_bridge.evaluate_for` 复用 `public_state(viewer)`，均不产出第二份 private 状态 |

## 6. 遗留风险

1. **网络**：未能 fetch 最新 `origin/develop`；若远程在 `d48ceb4` 之后有新提交，本次合并清单需重新复核。
2. **合并提交信息**：`1b8a5c6` 为 git 默认 merge message，且已存在于远程，按规则未 amend / 未 force push。
3. **仓库卫生**：`~$README.md`、`Diplomat_webdemo2.0/C 11.12 引擎/Untitled-1.py`、已跟踪的 `__pycache__/*.pyc` 仍在树中；清理需先确认清单。
4. **R7 编号**：仓库内未检索到显式 `R7` 定义；验收表按「显式复盘闸门」测试证据勾选，编号来源需与 D 确认。
5. **历史目录**：`Diplomat_webdemo2.0/C 11.11 三指数/` 与 `C 11.12 引擎/` 保留，已补 DEPRECATED 说明，未删除。
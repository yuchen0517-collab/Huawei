# 分支合并指引（2026-11-16）

> 适用分支：`feat/negotiator-a`（成员A）合入 `feat/rules-c`（成员C，本分支为权威源）。
> 本文只给判定规则与核对清单，**不是自动化脚本**。所有 `git` 命令需队长人工确认后执行。

## 1. 统一解决规则

**`C 11.12 三指数/` 目录下的冲突，一律取 `feat/rules-c` 版本。**

原因：A 侧的 `C 11.12 三指数/` 是一份**旧副本**，分叉点在本分支第二轮改动之前；
本分支在该目录上是唯一权威源。

判定依据（已在工作区实测，不是推测）：

| 文件 | A 侧旧副本 | 本分支（feat/rules-c） | 差异性质 |
|---|---|---|---|
| `adapter/scenario_adapter.py` | 缺 `assumptions_detail`；`redline_direction` 仅 1 处引用 | `assumptions_detail` 已落地；`redline_direction` 3 处引用 | 本分支含第二轮适配修复 |
| `load_scenario_bridge.py` | 369 行，缺 `evaluate_for` / `AGENTS_FALLBACK_COPY` / `_verify_design_table` | 454 行起，三处均在 | 本分支是生产收口实现 |
| `INTEGRATION_NOTES.md` | 无此文件 | +176 行 | 本分支新增 |
| `agents.json` | 无此文件 | +80 行 | 本分支新增精简注册表副本 |
| `docs/scenario_adapter.md` | 无此文件 | +250 行 | 本分支新增 |
| `tests/test_bridge.py` | 无此文件 | +91 行 | 本分支新增 |
| `tests/test_adapter.py` | 旧断言 | +102 行 | 本分支含第二轮修复断言 |
| `README.md` | 旧版 | +125/-... | 本分支已同步第二轮口径 |
| `engine/core.py` | 旧版 | +2 行（本轮再叠加复盘闸门） | 本分支为最新 |

统计口径：9 个文件分叉，本分支侧多 1031 行（不含本轮新增的对抗测试与调度器）。

## 2. 两侧已一致、合并时无需特别处理的部分

A 在 2026-11-14 18:08 的 `c33959b`「接入 C 的 adapter/load_scenario_bridge」已经把
C 推送的第一轮补丁带入其分支，因此以下符号**两侧一致**：

- `_normalized_private_state`
- `INITIAL_DERIVED`
- `soft_redlines`
- `_alias_party_ids`
- `CLAUSE_NAMES`
- `_resolve_agents_path`

**不要在合并说明或冲突处理里把上述六项写成“差异”**，否则会误导人工逐行比对，
增加无意义的合并成本。

## 3. 唯一例外：A 的地盘取 A 版本

以下文件属于成员A 的职责范围，合并时**取 `feat/negotiator-a` 版本**，不要用本分支覆盖：

- `api.py`
- `load_scenario.py`
- `test_e2e.py`
- `action_schema.json`
- `neg_cli.py`
- `multi_agent.py`

C 侧只保证 `load_scenario_bridge.py` 提供同名同签名入口（`is_b_scenario` /
`convert_b_scenario` / `load_scenario` / `make_scenario` / `ENGINE_ROOT`），
并新增 `evaluate_for` / `submit_for` / `debrief_for` 三个编排收口。
A 侧对 `api.py` 的唯一必要改动是**把 `evaluate_for` 接入对外评价出口**
（见第 7 节“仍未解决事项”）。

## 4. 建议的取版命令（需人工确认后执行）

在仓库根 `Huawei/` 下、且已切到 `feat/negotiator-a` 合并分支后：

```powershell
# 仅示例：先 dry-run 看清楚将被覆盖的文件
git checkout --no-overlay feat/rules-c -- "C 11.12 三指数/" --dry-run

# 确认无误后，再执行真正取版
git checkout feat/rules-c -- "C 11.12 三指数/"

# 恢复 A 的地盘（第 3 节所列文件）
git checkout feat/negotiator-a -- "C 11.12 三指数/api.py" `
    "C 11.12 三指数/load_scenario.py" `
    "C 11.12 三指数/test_e2e.py" `
    "C 11.12 三指数/action_schema.json" `
    "C 11.12 三指数/neg_cli.py" `
    "C 11.12 三指数/multi_agent.py"
```

注意事项：

- 上面第一条 `--dry-run` 只是**建议的预演方式**；不同 git 版本对 `checkout --dry-run`
  支持不一致，若报错就跳过预演，改用 `git diff --name-only` 人工确认。
- 取版会覆盖工作区，**必须先提交或 stash 当前改动**。
- 不要对 `Diplomat_webdemo2.0/C 11.11 三指数/` 执行任何写操作，那是历史快照。
- Windows 上 git 不在 PATH，需要用 GitHub Desktop 自带的 `git.exe`。

## 5. 合并后必跑的验证命令序列

在 `C 11.12 三指数/` 目录下依次执行：

```powershell
# 1) unittest（C 侧主验证入口）
python -m unittest discover -s tests -t .

# 2) pytest（A 指定的跑法）
python -m pytest tests/ -q

# 3) 端到端演示，同时写出 docs/state.example.json / evaluation.example.json
python demo.py
```

预期基线（本轮 C 侧实测，2026-11-15）：

| 检查项 | 预期 |
|---|---|
| `unittest` | `Ran 178 tests ... OK`（142 原有 + 24 对抗隔离 + 12 调度） |
| `pytest` | `178 passed, 133 subtests passed` |
| `demo.py` 终局类型 | `FULL_AGREEMENT`（完整协议） |
| `demo.py` coverage | `1.0` |
| `demo.py` 审计 | `{"ok": true, "issues": [], "summary": {"blocking": 0, "warning": 0}}` |
| `demo.py` replay | `replay 一致：True` |

合并 A 的 `api.py` / `test_e2e.py` 之后，测试总数可能继续上升；
**以实跑结果为准**。若出现以下任一情况，视为合并没有真正完成：

1. 任何原有断言被修改（142 条基线的断言一条都不许改）；
2. `demo.py` 审计出现 blocking；
3. `replay 一致` 变成 `False`；
4. `engine/state.py::to_public_dict` 不再是唯一的 private 过滤点
   （出现第二处“按 viewer 裁剪”的实现）。

## 6. 与 A 的接口契约（合并时逐条核对）

| 出口 | C 侧提供 | A 侧应做的 |
|---|---|---|
| 对外评价 | `evaluate_for(engine, viewer)` | 替换所有 `engine.evaluate()` 直出 |
| 行动提交身份 | `submit_for(engine, viewer, action)` | 与 `adapt_client_action` 的 `flat["actor"] = rec.my_actor` 叠加使用，二者口径必须一致 |
| 复盘揭晓 | `debrief_for(engine, requester)` | 只在 `status == "ended"` 且主持人显式确认后调用 |
| 存档 | `engine.dump(path)` / `to_archive_dict()` | 只落盘，不返回给任何单方玩家 |
| 调度 | `engine.scheduler.TurnScheduler` | 替换 `multi_agent.py` 内部的顺序 / 次数逻辑 |

## 7. 仍未解决、需与 A 对齐的事项

1. **A 的 `api.py` 尚未 `import evaluate_for`**（R2 的最后一公里）。
   A 可能仍在直接无参调用 `engine.evaluate()`，这会把双方 BATNA 真值与
   `net_gain` 直接下发。合并后必须由 A 改成 `evaluate_for(engine, MY_ACTOR)`。
2. **`redline_check` 未按 viewer 裁剪**。当前 `evaluate()` / `evaluate_for()`
   返回的 `redline_check` 是按参与方逐条列出“是否触碰红线”的布尔表；
   终局有协议时，可据此反推对方红线位置。本轮**未改**（超出修复边界），
   需要与 A 确认：要么由 A 只在复盘态展示，要么 C 在下一轮给
   `redline_check` 加 viewer 裁剪并补测试。
3. **身份收口落点**。引擎没有“会话”概念，`submit_action` 只校验
   `actor ∈ parties`；真正的不可伪造依赖 A 的 `api.py` 或 C 的
   `submit_for`。合并后需确认调用链只保留一处覆盖，避免“双重覆盖顺序不一致”。
4. **`multi_agent.py` 改造范围**。本文档给出 `TurnScheduler` 的只读调用方式，
   但 A 侧实际改动需 A 自己排期；C 不改 A 文件。
## 8. 2026-11-17 更新：A/C 两份引擎目录再次分叉

11-16 交付时 A/C 两侧 `C 11.12 三指数/` 为零差异（39 文件 tree 哈希相同，
见 `docs/RECONCILE_A_C_1116.md`）。本轮对接 B 契约 1.1 后，**本分支
`feat/rules-c` 再次领先**，A 那份停在 11-16 快照。合并时请继续以
`feat/rules-c` 为准，并注意以下文件新增了 1.1 能力：

| 文件 | 11-17 新增内容 |
|---|---|
| `engine/indices.py` | `IndexRulesShapeError`；`behaviour_delta` 形状自检与可选 warnings；`initial_indices` 兼容全局 initial |
| `engine/core.py` | `finish(terminal_type="PARTIAL_AGREEMENT")` 在禁止部分协议时改判 `DEADLOCK` |
| `adapter/scenario_adapter.py` | `_normalize_index_rules`；`runtime` / `deadlock_rounds` 显式读取；三布尔必填；`step` 与 `initial_ref` 校验 |
| `load_scenario_bridge.py` | `make_scenario` 从 `agents._scenario.runtime` / `terminal_rules` 读运行参数 |
| `tests/test_index_rules_v1.py` | 新增 20 条 |
| `tests/test_contract_v1_1.py` | 新增 18 条 |
| `tests/fixtures/index_rules_v1.json` | B 原表夹具（从 `origin/feat/scenario-b` 复制） |
| `tests/fixtures/b_scenario_dst.json` | B 真实场景夹具 |
| `docs/INDEX_RULES_V1_GAP.md` | `interest_delta` 分歧说明（只出报告，未改结算） |

**合并后预期基线**：`pytest 218 passed / 145 subtests`、`unittest Ran 218 tests OK`、
`demo.py` 四项指标不变。若 A 侧同时带了新的 `test_e2e.py`，总数可能继续上升，
以实跑为准。
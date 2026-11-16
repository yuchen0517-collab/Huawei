# A/C 两份引擎目录差异核对 · 2026-11-16

> 只读比对，未切分支、未修改任何文件、未做 merge/rebase/push。
> 比对对象：`feat/rules-c`（HEAD `4c6e6d4`）与 `origin/feat/negotiator-a`（HEAD `542b196`）。
> 比对基线是**提交**；本轮交付日尚未提交的本地改动（K4 5→3、单复数证明测试）不在本次比对内。

## 1. 结论摘要（给队长）

**`C 11.12 三指数/` 目录两边逐字节完全一致，合并取谁都不会丢东西。**

硬证据：两分支该目录的 git tree 对象哈希相同：

```
feat/rules-c:C 11.12 三指数            → tree 25d9802ee12746630ac386a105190383de2b2aba
origin/feat/negotiator-a:C 11.12 三指数 → tree 25d9802ee12746630ac386a105190383de2b2aba
```

文件清单也完全相同（各 39 个文件，`Compare-Object` 双向为空）。
`git diff --name-status feat/rules-c origin/feat/negotiator-a` 全量 99 条中，
**没有任何一条落在 `C 11.12 三指数/` 下**。

**A 有没有在 C 的成果之上另做我方没有的修改？——没有。** A 的 `1f508b4` 是整批复制
（`git diff c33959b 1f508b4`：16 个 `C 11.12 三指数/` 文件 + `api.py`），
复制结果与 C 的 `4c6e6d4` 树哈希相同，不存在"仅 A 有"的引擎改动。

**合并建议**：`C 11.12 三指数/` 取本分支工作区（含 11-16 未提交改动）；
`C 11.12 三指数/` 之外一律取 A 分支（`api.py`、`neg_cli.py`、`multi_agent.py`、
`load_scenario.py`、`action_schema.json`、`agents.json`、`scenario agent v2/` 等）。
两者互不覆盖，可安全拼装。

## 2. 重点文件逐个核对

| 文件 | 结论 | 说明 |
|---|---|---|
| `engine/core.py` | **一致** | 同属 tree `25d9802`；A 的 `1f508b4` 有 `+47` 行改动，内容即 C 的 phase/终局判定/viewer 透传，无 A 独有逻辑 |
| `engine/state.py` | **一致** | 同上；A 的 `1f508b4` 有 `+21` 行，内容即 C 的 `god_view` / 序列化字段 |
| `engine/validator.py` | **一致** | `1f508b4` 的 stat 中**没有**此文件 → A 根本没动过 |
| `engine/terminal.py` | **一致** | `1f508b4` 的 stat 中**没有**此文件 → A 根本没动过 |
| `adapter/scenario_adapter.py` | **一致** | A 的 `1f508b4` 有 `+155` 行，内容即 C 的单复数双读 + initial 中点裁决 |
| `load_scenario_bridge.py` | **一致** | A 的 `1f508b4` 有 `+142` 行，内容即 C 的 `make_scenario_with_warnings` / `evaluate_for` |
| `tests/test_adapter.py` | **一致** | 同 tree |
| `tests/test_bridge.py` | **一致** | 同 tree（本轮新增的 K4 回归与证明测试在本分支工作区，未提交，A 侧没有） |
| `tests/test_rules.py` | **一致** | 同 tree |
| `tests/test_isolation_adversarial.py` | **一致** | 843 行，A 的 `1f508b4` 整文件新增（即复制 C 的成果） |
| `engine/scheduler.py` | **一致** | 93 行，同上整文件新增 |
| `tests/test_scheduler.py` | **一致** | 186 行，同上整文件新增 |

## 3. 差异性质分类（99 条全量）

> `C 11.12 三指数/` 下**零差异**，因此不存在需要"按文件归到 A 侧/C 侧/等价"的条目。
> 下面只列目录**外**的差异，供合并时决策。

### 3.1 A 侧新增（合并必须保留 A 的）

顶层 `api.py`、`neg_cli.py`、`multi_agent.py`、`load_scenario.py`、`action_schema.json`、
`agents.json`、`openapi.json`、`conftest.py`、`pytest.ini`、`requirements.txt`、
`run.bat`、`report.py`、`report.bat`、`manual_api_check.py`、根级 `test_*.py`、
`scenario agent v2/`（B 的场景编译目录）、`_e2e_effect_labels.py`、
`_tmp_test_validate.py`、`_verify_engine_api.py`、`谈判对手Agent_prompt.md`、
`.arts/settings.json`、`.gitignore`、`API错误码清单.md`、`BACKLOG.md`、`_待移交_评分标准.md`、`README.md`（顶层已改）。

### 3.2 A 侧删除（合并时需队长确认，不建议照单全收）

| 被 A 删掉的内容 | 性质 | 建议 |
|---|---|---|
| `Diplomat_webdemo2.0/C 11.11 三指数/`（整目录 32 文件） | 历史快照 | **保留**（C 侧硬约束"不删历史快照，删前先问队友"） |
| `成员C_场景适配层_华为云Prompt.md`、`C组代码修复_改动清单.md` | C 的工作记录 | 队长决定；不影响运行时 |
| `~$README.md` | Office 临时文件 | **删除是对的**，可不保留 |
| `Diplomat_webdemo2.0/C 11.12 引擎/Untitled-1.py` | 无效草稿 | **删除是对的**（C 分支仍留着，建议顺手清掉） |

### 3.3 内容等价

`C 11.12 三指数/` 全部 39 文件属于此类（tree 哈希相同，逐字节等价）。

## 4. 特别确认：`1f508b4` 是否动过我方引擎核心

`git show --stat 1f508b4`（17 个文件）：

```
C 11.12 三指数/INTEGRATION_NOTES.md                | 176 +
C 11.12 三指数/README.md                           | 125 +-
C 11.12 三指数/adapter/scenario_adapter.py         | 155 +-
C 11.12 三指数/agents.json                         |  80 +
C 11.12 三指数/docs/MERGE_GUIDE_1116.md            | 148 +
C 11.12 三指数/docs/scenario_adapter.md            | 300 +
C 11.12 三指数/docs/state.example.json             |   3 +-
C 11.12 三指数/engine/__init__.py                  |   6 +-
C 11.12 三指数/engine/core.py                      |  47 +
C 11.12 三指数/engine/scheduler.py                 |  93 +
C 11.12 三指数/engine/state.py                     |  21 +
C 11.12 三指数/load_scenario_bridge.py             | 142 +-
C 11.12 三指数/tests/test_adapter.py               | 102 +-
C 11.12 三指数/tests/test_bridge.py                |  91 +
C 11.12 三指数/tests/test_isolation_adversarial.py | 843 +
C 11.12 三指数/tests/test_scheduler.py             | 186 +
api.py                                             |  37 +-
```

- 动过：`engine/core.py`(+47)、`engine/state.py`(+21) —— 但结果与 C 的 `4c6e6d4` 一致，
  属"复制 C 的改动"，**不含 A 独有引擎逻辑**。
- 没动过：`engine/validator.py`、`engine/terminal.py`、`engine/indices.py`。
- 唯一 A 独有的改动在**目录外**：`api.py`(+37)，即接通 debrief/evaluate 复盘链路。

> 与任务书描述的一处偏差（如实报告）：任务书说 `1f508b4` 的 stat 显示
> `engine/core.py / state.py / validator.py / terminal.py` 四个都有改动；
> 实测只有 `core.py`、`state.py` 两个，`validator.py`、`terminal.py` 未出现在该提交中。

## 5. 合并动作建议（只给建议，不执行）

1. `C 11.12 三指数/`：以本分支工作区为准（先提交 11-16 的 K4 修正 + 证明测试）。
2. 目录外：以 `origin/feat/negotiator-a` 为准，尤其 `api.py` 的复盘链路不要回退。
3. `Diplomat_webdemo2.0/C 11.11 三指数/`：不要采用 A 的整目录删除，先四方确认。
4. 顶层 `README.md` 有冲突（两边都改过），需人工合并，不要直接 `-X ours/theirs`。
5. 合并后必须重跑：`python -m pytest tests/ -q`、`python -m unittest discover -s tests -t .`、
   `python demo.py`（在 `C 11.12 三指数/` 内），并确认 `api.py` 能 import 到
   `C 11.12 三指数/engine`（`ENGINE_DIR_NAME` 不变）。
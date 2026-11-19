# 说明书口径补丁 · 成员C（2026-11-20）

> 给成员D 直接抄入说明书，不改动 docx 原文件。

## 1. 第八章「当前进展」：R1–R7 逐项状态

| 编号 | 状态 | 内容 | 对应 commit / 文件 |
|---|---|---|---|
| R1 | 已完成 | 存档视图带 `_visibility="god_view"` 危险标记，禁止当普通状态下发 | `1b8a5c6`；`C 11.12 三指数/engine/state.py::to_archive_dict`；`tests/test_isolation_adversarial.py::test_archive_dict_is_explicitly_marked_god_view` |
| R2 | 已完成 | 对外评价按 viewer 裁剪 BATNA / net_gain / better_than_batna 与 redline_check | `f29bec3`、`1b8a5c6`；`engine/terminal.py::batna_comparison` / `redline_check`；`load_scenario_bridge.py::evaluate_for`；`tests/test_terminal.py` |
| R3 | 已完成 | 行为日志只保留白名单字段与公开条款变动，不夹带私有底牌 | `1b8a5c6`；`engine/indices.py::apply_effects`；`tests/test_isolation_adversarial.py::test_behavior_log_exposes_no_private_values` |
| R4 | 已完成 | `public_events` 五类事件键集合固定，不出现 private 字段 | `1b8a5c6`；`engine/core.py::submit_action`；`tests/test_isolation_adversarial.py::test_public_events_payload_has_no_private` |
| R5 | 已完成 | `viewer=""` / 未知 viewer（`root` / `*` 等）返回空 private，不退化为上帝视角 | `1b8a5c6`；`engine/state.py::to_public_dict`；`tests/test_isolation_adversarial.py::test_unknown_viewer_gets_nothing_not_everything`、`test_public_dict_private_still_single_viewer` |
| R6 | 已完成 | 终局只表示对局结束，不自动放开双方 private | `1b8a5c6`；`engine/core.py::debrief_state`；`tests/test_isolation_adversarial.py::test_terminal_state_still_isolated_before_debrief` |
| R7 | 已完成（编号需 D 确认） | 复盘必须显式调用 `debrief_state(requester=...)`，未终局或空 requester 一律 `IllegalDebriefAccess` | `1b8a5c6`；`engine/core.py::debrief_state`；`engine/terminal.py`；`tests/test_isolation_adversarial.py::test_debrief_gate_is_explicit`、`tests/test_orchestrator.py::DebriefGateTest` |

> 说明：仓库内未检索到 `R7` 的显式编号，上表按「显式复盘闸门」测试证据映射；请 D 在说明书中确认 R7 的原文定义。

## 2. 表 5「复盘 / 学习教练」

本轮只做**字段预留**：

- `NegotiationState.speaker_score`：恒为 `None`。四维发言评分由 D 侧推导，C 不产出数值。
- `NegotiationState.est_confidence`：恒为 `None`。定性分级（`high / mid / low / unknown`）由 D 前端推导。
- `to_public_dict()` 与 `to_archive_dict()` 均包含这两个键，值均为 `None`。
- 前端按 `null` 渲染，不得据此展示任何数值或默认分。

## 3. 表 18「成员C 分工」

| 职责 | 交付物（文件路径） |
|---|---|
| 规则引擎 | `C 11.12 三指数/engine/core.py`、`validator.py`、`terminal.py`、`indices.py`、`state.py`；测试 `tests/test_rules.py`、`test_indices.py`、`test_final_offer.py`、`test_terminal.py` |
| 协议审计 | `C 11.12 三指数/agent/audit/auditor.py`；测试 `tests/test_audit.py` |
| 场景适配层 | `C 11.12 三指数/adapter/scenario_adapter.py`、`load_scenario_bridge.py`；文档 `docs/scenario_adapter.md`；测试 `tests/test_adapter.py`、`test_bridge.py` |
| 工作流搭建 | `C 11.12 三指数/engine/orchestrator.py`、`run_workflow.py`；文档 `docs/SCHEDULER_HANDOFF.md`、`docs/workflow_trace.json`；测试 `tests/test_orchestrator.py` |

## 4. §8.3「待改进」

1. **多边场景仍缺利益结算通道**：当前 `interest` 只由条款效用重算，三方及以上没有“转移支付 / 补偿 / 侧支付”通道，无法表达“A 在条款上让步、B 在另一议题补偿 A”的多边交易。
2. **行为标签 `interest_delta` 未落地**：B 契约 1.1 中的 `interest_delta` 在适配层被忽略并记 `INTEREST_DELTA_UNSUPPORTED` warning；引擎目前只有 `image / trust` 行为通道，`interest` 仍只走条款效用。
# 交付前自查（Day 10 · M4 候选）

> **素材状态更新附注（2026-11-20 18:34）**：本文表格/结论多为当时历史快照。此后已补齐：版本探针截图 `version-badges.png`（`{count:3, ok:true}`）、9/9 段 mp4（同输入预录片段，ffprobe 实测 210.17s）、ffmpeg 9.1 + libass（`D://ffmpeg//bin`），闸门核对 6/6 复绿。**成片（`final/demo*`）仍未导出、A 会签仍待办——凡「成片未产出 / 不可交付」结论不变。**最新权威状态以 `docs/闸门核对-day10.md`、`docs/素材整理清单-day8.md`、`docs/导出前检查-day11.md` 为准。

> **性质：候选自查，不是最终验收通过。** 本轮只改 `docs/**` 与导出产物目录，未改源码。
> 结论先行：**未发现泄露（源码/产物/文本全扫 0 命中；画面抽检 3/17 无敏感）**；但成片、字幕、9 段视频、T7–T11 证据、A/C/B 会签仍缺，M4 只能作为「可运行版本候选」，不能称最终交付。

---

## 1. 五项扫描

| # | 面 | 扫描对象 | 方法 | 结果 | 证据 |
|---|---|---|---|---|---|
| 1 | 源码 | `src/**/*.js|*.css`、`index.html`、`build-single.mjs`、`package.json` | 关键词 `token/secret/api_key/authorization/bearer/password/https?://`（排除 `www.w3.org` 命名空间） | **0 命中** | 40 个文件扫描；无真实域名、Token、密钥 |
| 2 | 构建产物 | `Diplomat-单文件版.html`、`dist/assets/*.js|*.css` | 同上 | **0 命中** | 产物与源码同扫；单文件版无外部资源 |
| 3 | 画面 | `day8-*` 截图 | 图像抽检 3 张：`overview-loaded`、`busy-banner`、`finale-datasource` | **无控制台、无域名/IP/Token、无未实现功能；数据来源声明可见；评分 62/74 正常，无 0/NaN** | 图像分析结果（见下） |
| 4 | 控制台 | 视频/截图/源码 | 无成片、无控制台截图；源码 0 命中 | **无控制台画面证据；无 Token/密钥** | 因 0/9 视频，无法逐帧扫描 |
| 5 | 素材文件 | `docs/讲解词-day10.md`、`docs/视觉规范-day10.md`、剪辑脚本、补录包 | 文本关键词扫描 | **0 命中**（`127.0.0.1` 仅为本机预览命令，非真实域名） | 文档文本检查 |

**画面抽检明细**：
- `day8-overview-loaded.png`：无控制台/敏感内容/未实现功能。
- `day8-busy-banner.png`：SESSION_BUSY 状态提示，无敏感内容。
- `day8-finale-datasource.png`：数据来源声明「本页数字来自本局结构化状态；模型解说仅供参考，不构成事实。」可见且未裁切；评分 62/74 正常。

**未完成范围**：17 张截图中只抽检 3 张，剩余 14 张未逐张扫描；`0/9` 视频无逐帧扫描。均列入第 11 天待办，**不写「全量通过」**。

---

## 2. 正常 / 失败用例

| 类型 | 用例 | 证据 | 状态 |
|---|---|---|---|
| 正常 | 加载/骨架/报价板落位 | `day8-overview-loaded.png` | **有（截图级）** |
| 正常 | 选卡后行动点 5/5 → 4/5 | `day8-board-preflight.png` | **有（截图级）** |
| 正常 | 自动推演等待对方回应 | `day8-autoplay-running.png` | **有（截图级）** |
| 失败 | SESSION_BUSY 横幅 + 草稿保留 | `day8-busy-banner.png` | **有（截图级）** |
| 失败 | VERSION_CONFLICT 横幅 + 草稿保留 | `day8-conflict-banner.png` | **有（截图级）** |
| 未覆盖 | INVALID_ACTION / MODEL_UNAVAILABLE / ROUND_LOCKED / SESSION_ENDED | — | **无（2/6 错误码有截图）** |
| 未覆盖 | 完整视频级正常/失败用例 | — | **无（0/9 视频）** |

> 满足「至少一正常 + 一失败」的截图级要求；不能宣称六错误码全量覆盖或视频级用例通过。

---

## 3. 接口字段与契约一致性

| 项 | 契约 / 回签 | 当前实现 | 判定 |
|---|---|---|---|
| 六错误码 | `INVALID_ACTION / SESSION_BUSY / MODEL_UNAVAILABLE / ROUND_LOCKED / VERSION_CONFLICT / SESSION_ENDED` | `src/services/adapter.js` 六码 + 独立 UI 分支 | **一致** |
| 终局五态 | `ENDGAME_COPY`：full_agreement / partial / withdraw / stalemate / rounds_exhausted | `src/domain/endgame.js` 五态文案 + `judgeEnd` | **一致** |
| 教练证据 | A 1117：`evidence` 补 `kind/round/label`；`clause` 只在 `clauses[].name` 可查时填 | 前端 `evidenceOk` 校验 round/action_id/clause；`sanitizeCoach` | **一致** |
| 命名口径 | 契约 §1.6：T6 前端透传 snake_case | `basis_version / ap_cost / apply_hint` 直读 | **一致（现状已注明）** |
| `basis_round` | A 1117 已加 | 终局派生 `R{basis_round}` | **一致** |
| `base_version` | A 要求提交 body 必填 | `adapter.js` http body 仅有 `version` | **偏差（切 http 前必改）** |
| `clauses` 投影 | A 1117：3 条、`{name,type,unit,range,options,initial}` | 前端固定 5 条 mock；投影未接 | **偏差（真实模式需映射）** |
| `items[].kind` | A 1117：`risk / opportunity / next_move` | `CoachPanel` 仍 `stage / alternative` | **偏差（切 http 前映射）** |
| `action_points_left` | A：11/19 提供只读字段 | 未接入 | **偏差（11/19 后可选）** |

**结论**：mock 演示契约核心一致；切 http 前有 4 项偏差，需按 `docs/给A的消息-接口回签-1117.md` 处理，不阻断本轮可运行候选。

---

## 4. 泄露判定

- 未命中 `freeze-day9.md` 第 6 节第 5 条（密钥 / Token / 对方私有底牌）。
- 未发现真实域名、内网 IP、Token、账号密码。
- 画面抽检无对方私有底牌；对方态势只出现估计值与可信度（截图中「非正式沟通 本场景不开放」为场景机制，不是私密底牌）。
- **不登记** freeze 第 7 节；若后续逐张/逐帧扫描发现泄露，立即按第 5 条登记并停止演示。

---

## 5. 候选状态与会签

| 项 | 状态 |
|---|---|
| 可运行版本（单文件版 + dist） | **有** |
| Demo 成片 / 无字幕原片 / 9 段 / raw | **无** |
| 9 份 SRT + all.srt | **无** |
| 讲解词 / 视觉规范 / 封面 SVG | **有** |
| 封面 PNG | **无** |
| T7–T11 证据 | **无** |
| 三项回归（构建 / 版本探针 / 双档） | 构建通过；版本探针静态通过但缺截图；双档通过 |
| 六错误码用例 | 截图级 2/6（成功 + 2 失败） |
| 接口回签 | 有 |
| A 内容准确性 | **待确认** |
| C 规则与状态 | **待确认** |
| B 场景 | **待确认** |

> M4 = **可运行版本候选 + 部分素材候选**，不是最终验收，不是已提交。

---

## 6. 第 11 天阻断待办（只修阻断）

| # | 阻断项 | 当前 | 责任人 | 最晚 |
|---|---|---|---|---|
| 1 | 9 段 mp4 0/9 | 无 | D | 2026-11-21 18:00 |
| 2 | ffmpeg + libass 不在 PATH | 无 | D | 2026-11-20 23:00 |
| 3 | `version-badges.png` 缺 | 无 | D | 2026-11-20 23:00 |
| 4 | 成片/字幕/原片未产出 | 无 | D | 2026-11-21 22:00 |
| 5 | 画面 14 张未逐张扫描 | 未执行 | D | 2026-11-21 20:00 |
| 6 | A 内容确认 | 待确认 | A | 2026-11-21 18:00 |
| 7 | C 规则确认 | 待确认 | C | 2026-11-21 18:00 |
| 8 | B 场景确认 | 待确认 | B | 2026-11-21 18:00 |

> 第 11 天只处理上述阻断；不做文案润色、动效、配色、功能增补或重构。
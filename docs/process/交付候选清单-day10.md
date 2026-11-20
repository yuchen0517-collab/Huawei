# M4 交付候选清单（Day 10）

> **素材状态更新附注（2026-11-20 18:34）**：本文表格/结论多为当时历史快照。此后已补齐：版本探针截图 `version-badges.png`（`{count:3, ok:true}`）、9/9 段 mp4（同输入预录片段，ffprobe 实测 210.17s）、ffmpeg 9.1 + libass（`D://ffmpeg//bin`），闸门核对 6/6 复绿。**成片（`final/demo*`）仍未导出、A 会签仍待办——凡「成片未产出 / 不可交付」结论不变。**最新权威状态以 `docs/闸门核对-day10.md`、`docs/素材整理清单-day8.md`、`docs/导出前检查-day11.md` 为准。

> **性质：交付候选，不是最终验收通过，也不是已提交。** 第 11 天只修阻断问题。
> 基线：`docs/freeze-day9.md`（`diplomat-negotiation-ui@1.0.0`；条件冻结）。
> 状态口径：`有` = 文件实际存在并可指向路径；`无` = 文件不存在；`待确认` = 未取得对应角色确认。**不留空、不写「已完成」。**

---

## 1. 可运行版本

| 项 | 路径 | 大小 | 状态 | 备注 |
|---|---|---|---|---|
| 单文件版（双击可用） | `Diplomat-components(1)/Diplomat-单文件版.html` | 760,746 B | **有** | 2026-11-20 16:50:25 |
| dist HTML | `Diplomat-components(1)/dist/index.html` | 651 B | **有** | 引用 `./assets/index-T234zCtM.js` |
| dist JS | `Diplomat-components(1)/dist/assets/index-T234zCtM.js` | 89,797 B | **有** | 与 freeze 第 3 节逐字一致；未重新构建 |
| dist CSS | `Diplomat-components(1)/dist/assets/index-C-VXQy_A.css` | 70,007 B | **有** | — |
| dist 图片 | `Diplomat-components(1)/dist/assets/G01-COc-yrk7.jpg` | 123,145 B | **有** | — |

> 本轮未命中阻断第 2/3 条，**未重新构建**，产物名沿用 `index-T234zCtM.js`，不写预计名。

---

## 2. Demo 成片

| 项 | 目标路径 | 状态 | 说明 |
|---|---|---|---|
| 候选成片 | `docs/recording-day7/final/demo-v0.2.mp4` | **无** | 未生成；不填时长/分辨率/字幕轨 |
| 无字幕原片 | `docs/recording-day7/final/demo-v0.2_nosub.mp4` | **无** | 未生成 |
| 9 段分段视频 | `docs/recording-day7/segments/01–09.mp4` | **无（0/9）** | `segments/` 目录不存在 |
| 完整原片 | `docs/recording-day7/raw/full_*.mp4` | **无** | 目录不存在 |

> 闸门核对（`docs/闸门核对-day10.md`）：9 段 0/9、ffmpeg 缺、version-badges 截图缺，**禁止成片**。

---

## 3. 字幕与讲解词

| 项 | 路径 | 状态 | 说明 |
|---|---|---|---|
| 9 份 SRT | `docs/recording-day7/srt/01_overview.srt` … `09_autoplay.srt` | **无** | 目录不存在；无视频无法对齐时间轴 |
| 全片 SRT | `docs/recording-day7/srt/all.srt` | **无** | 未合并 |
| 三段讲解词 | `docs/讲解词-day10.md` | **有** | 3 段 + 时间码冲突说明 + 待 A 核对 |
| 视觉规范 | `docs/视觉规范-day10.md` | **有** | 1920×1080/30fps、字体字号、安全区 |

---

## 4. 测试记录

| 项 | 路径 / 证据 | 状态 | 说明 |
|---|---|---|---|
| T7–T11 证据 | `docs/evidence/t7` … `t11` | **无** | 目录不存在；不冒充已归档 |
| T6 历史证据 | `docs/evidence/t6/*.png`（10 张） | **有** | 第 6 天教练 P1，不是 T7–T11 |
| 构建回归 | `docs/freeze-day9.md` 第 4.1 节 | **通过（构建机）** | 产物存在；本机无 Node 未复跑 |
| 版本探针回归 | `docs/freeze-day9.md` 第 4.2 节 | **静态通过 / 运行时缺图** | 三处徽标与 `renderVersion` 存在；`version-badges.png` 无 |
| 双档回归 | `docs/evidence/day8-viewport-1440/1920.png` | **通过** | 两张已归档；图像复核无横向滚动、控件完整 |
| 接口回签 | `docs/给A的消息-接口回签-1117.md` | **有** | A 1117 四条回复已记录 |
| 六错误码用例 | `day8-busy-banner.png`、`day8-conflict-banner.png` | **部分** | 失败码覆盖 SESSION_BUSY / VERSION_CONFLICT；其余 4 码无截图；无完整视频用例 |
| 正常用例 | `day8-overview-loaded.png`、`day8-board-preflight.png`、`day8-autoplay-running.png` | **有** | 截图级，不是完整视频用例 |
| `versionBadges()` count===3 截图 | `docs/evidence/version-badges.png` | **无** | 硬闸门第 1 步未完成 |

---

## 5. 规则与内容确认

| 项 | 路径 / 证据 | 状态 | 说明 |
|---|---|---|---|
| C 规则口径文档 | `docs/state-contract.md`、`docs/acceptance-checklist.md`、`docs/coach-contract.md` | **有** | 文档存在，但**不是 C 的会签文件**；C 确认位待签 |
| A 内容准确性确认 | `docs/给A的消息-接口回签-1117.md` | **待确认** | 该文件是接口回签，不是讲解词内容确认；讲解词 5 个事实点待 A 核对 |
| B 场景截图 / 生成日志 | — | **无** | `docs/evidence` 无 B 场景材料；B 确认位待签 |

---

## 6. 封面与视觉规范

| 项 | 路径 | 状态 | 说明 |
|---|---|---|---|
| 封面源（SVG） | `docs/recording-day7/cover/cover_1920x1080.svg` | **有** | 1920×1080，黑金；无外部引用 |
| 封面 PNG | `docs/recording-day7/cover/cover_1920x1080.png` | **无** | 本机无 PIL/ffmpeg/浏览器导出工具，未生成 |
| 视觉规范 | `docs/视觉规范-day10.md` | **有** | 字体、字号、安全区、配色、片头片尾约束 |

---

## 7. 团队会签位（不代签）

| 角色 | 确认内容 | 确认位 | 状态 |
|---|---|---|---|
| **A** | 内容准确性（讲解词 5 个事实点、三段时间码裁定） | ________________ | **待确认** |
| **C** | 规则与状态（六错误码、五态文案、状态口径） | ________________ | **待确认** |
| **B** | 场景（场景截图、生成日志、条款 3 条口径） | ________________ | **待确认** |

> 未会签项一律「待确认」；本清单不代替任何成员签字，也不把候选写成「最终验收通过」。

---

## 8. 第 11 天约束

- 只修阻断：首帧黑屏、错误横幅不可读、版本徽标被遮、数据来源声明被裁、密钥泄露、走不到终局。
- 不做非阻断优化、文案润色、功能增补、重构。
- 任何源码改动必须先命中 `freeze-day9.md` 第 6 节六条之一，并登记第 7 节。
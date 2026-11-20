# 第 12 天备份执行清单（已实际执行）

> **素材状态更新附注（2026-11-20 18:34）**：本文表格/结论多为当时历史快照。此后已补齐：版本探针截图 `version-badges.png`（`{count:3, ok:true}`）、9/9 段 mp4（同输入预录片段，ffprobe 实测 210.17s）、ffmpeg 9.1 + libass（`D://ffmpeg//bin`），闸门核对 6/6 复绿。**成片（`final/demo*`）仍未导出、A 会签仍待办——凡「成片未产出 / 不可交付」结论不变。**最新权威状态以 `docs/闸门核对-day10.md`、`docs/素材整理清单-day8.md`、`docs/导出前检查-day11.md` 为准。

> 执行时间：2026-11-20 18:06
> 备份根：`11.11/docs/backup-final/`（实际创建）
> 执行方式：Python `shutil`/`open` 复制 + SHA-256 逐文件计算（前 16 位），完整机器可读清单见 `docs/backup-final/manifest.json`。
> **备份原则：只镜像真实存在的文件；视频 / 原片 / 成片 / 字幕当前为 0，标「阻塞」，不造占位文件、不建空内容。**

---

## 1. 执行结果总览

| 子目录 | 备份内容 | 文件数 | 状态 |
|---|---|---|---|
| `screenshots/` | 17 张 `day8-*.png` + 10 张 `t6/` 历史证据 | 27 | **已完成** |
| `deliverables/` | `Diplomat-单文件版.html` + `dist/` 全部文件（含 assets 与图片） | 9 | **已完成** |
| `docs/` | 第 7–12 天提示词 + 全部执行 / 交付文档 + 契约 / 验收文档 + 素材索引页 | 45 | **已完成** |
| `video/` | 9 段 mp4 + 成片 `demo*.mp4` | 0 | **阻塞（源不存在）** |
| `raw/` | 完整原片 | 0 | **阻塞（源不存在）** |
| `srt/` | 9 份 SRT + `all.srt` | 0 | **阻塞（源不存在）** |
| **合计** | — | **81 个文件 / 25,526,119 B（约 24.4 MB）** | 3 类完成、3 类阻塞 |

> 完整逐文件 sha256 见 `docs/backup-final/manifest.json`（81 条），本文件第 3 节列关键文件摘要。

---

## 2. 阻塞项（源不存在，未造占位）

| 项 | 应有路径 | 实测 | 补齐责任 | 补齐条件 |
|---|---|---|---|---|
| 9 段 mp4 | `Diplomat-components(1)/docs/recording-day7/segments/01–09.mp4` | 目录不存在，0/9 | D（录制机） | P0 第 1、3 项完成 |
| 完整原片 | `docs/recording-day7/raw/full_*.mp4` | 目录不存在 | D（录制机） | 同上 |
| 成片 `demo*.mp4` | `docs/recording-day7/final/` | 目录不存在，未导出 | D | 9 段 + ffmpeg + 试看全绿 |
| 字幕 SRT | `docs/recording-day7/srt/*.srt` | 目录不存在 | D | 视频录制完成 |

> 这四项补齐后，重跑备份脚本即可增量追加到对应子目录，并刷新 `manifest.json`；本清单只需追加新条目，不改已完成三类。

---

## 3. 关键文件 sha256 摘要（前 16 位）

### 3.1 可运行版本（deliverables/）

| 备份路径 | 大小 (B) | sha256 前 16 位 |
|---|---:|---|
| `deliverables/Diplomat-单文件版.html` | 760,746 | `9707e3c8d1223801` |
| `deliverables/dist/index.html` | 651 | `f919b2c1b5a79cee` |
| `deliverables/dist/assets/index-T234zCtM.js` | 89,797 | `3d1c896347e61d6a` |
| `deliverables/dist/assets/index-C-VXQy_A.css` | 70,007 | `5b60c3884d967bf3` |
| `deliverables/dist/assets/G01-COc-yrk7.jpg` | 123,145 | `69d5c43ceb89721d` |

> 产物名 `index-T234zCtM.js` 与 `freeze-day9.md` 第 3 节逐字一致；本轮未重新构建。

### 3.2 双档截图（screenshots/）

| 备份文件 | 大小 (B) | sha256 前 16 位 |
|---|---:|---|
| `day8-viewport-1440.png` | 1,245,489 | `c3c290cd7f2b4a70` |
| `day8-viewport-1920.png` | 1,828,911 | `97b3a1259e0bc090` |

### 3.3 17 张 day8 截图（screenshots/，全部已完成）

| 文件 | 大小 (B) | sha256 前 16 位 |
|---|---:|---|
| `day8-overview-loaded.png` | 1,245,533 | `23d02047ef71d1fe` |
| `day8-overview-versions.png` | 713,495 | `8c086335f3a60c77` |
| `day8-board-draft2.png` | 714,175 | `293bfc0351ecfab2` |
| `day8-board-preflight.png` | 1,247,055 | `23d07935a4ca6eb5` |
| `day8-protocol-unresolved.png` | 713,694 | `2e1cfd9f25b398d8` |
| `day8-busy-banner.png` | 1,212,302 | `747491c73242605c` |
| `day8-conflict-banner.png` | 1,212,497 | `ba87604e41c84a9d` |
| `day8-degraded-empty.png` | 713,591 | `e921f149649ea676` |
| `day8-viewport-1440.png` | 1,245,489 | `c3c290cd7f2b4a70` |
| `day8-viewport-1920.png` | 1,828,911 | `97b3a1259e0bc090` |
| `day8-finale-five.png` | 684,233 | `0abe3cd2c8846c36` |
| `day8-finale-evaluation.png` | 684,319 | `124b103ca2f0e86e` |
| `day8-finale-null.png` | 683,048 | `ecfef9d8691e5f09` |
| `day8-finale-evidence.png` | 687,630 | `93ef91220938eee1` |
| `day8-finale-datasource.png` | 681,551 | `fd7b0a9f7843154a` |
| `day8-autoplay-running.png` | 1,242,149 | `e65f5af59efc769d` |
| `day8-autoplay-log3.png` | 1,256,210 | `65c291f619ea00fd` |

> t6/ 历史证据 10 张完整 sha256 见 `manifest.json`。

---

## 4. 校验结果

| 检查 | 方法 | 结果 |
|---|---|---|
| 全量 sha256 | 81 个文件逐一计算并写入 `manifest.json` | **完成** |
| 抽样复核 | 随机抽 5 项与原件重算 sha256 比对 | **5/5 通过** |
| 抽样清单 | `day8-viewport-1440.png`、`day8-viewport-1920.png`、`Diplomat-单文件版.html`、`index-T234zCtM.js`、`讲解词-day10.md` | 全部一致 |
| 产物名一致性 | 备份的 dist JS 名 vs `freeze-day9.md` 第 3 节 | **一致**（index-T234zCtM.js） |
| 泄露复检 | 引用 `docs/泄露复检-day12.md` | 源码 / 产物 / 文档三面通过；画面 / 控制台待录制机补扫 |

---

## 5. 备份状态结论

- **三类可备份内容（截图 / 可运行版本 / 文档）已 100% 实际备份并校验通过。**
- **三类阻塞内容（视频 / 原片 / 字幕 + 成片）源不存在，未造占位文件**，待录制机补齐后增量追加。
- 备份本身不依赖成片，因此**即使当前不可交付，备份动作已完成**；成片到位后重跑即可，不需推倒重来。
- 从备份还原到可演示状态的步骤见 `docs/重新导出说明-day12.md`。
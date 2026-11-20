# 第 10 天闸门核对

> 核对时间：2026-11-20（18:34 复核）
> 基线：`docs/freeze-day9.md`
> 结论：**通过（6 项全通过）**——第 1/3/4 项已于 18:21–18:34 补齐：版本探针截图 `version-badges.png` 已归档（`{count:3, ok:true}`）、ffmpeg 9.1 + libass 已安装（PATH 与功能均验证）、9 段 mp4 已产出（同输入预录片段）。第 2/5/6 项原已通过。**本结论为可运行候选闸门复绿，不等于成片已完成**：预录片段无旁白音轨、非真人录屏，字幕定稿与成片导出仍待后续卡执行。`初剪验收记录-day9.md` 的「初剪未产出」结论暂不改，待成片产出后回填。

---

## 1. 六项核对

| # | 核对项 | 判定 | 证据路径 / 说明 |
|---|---|---|---|
| 1 | 9 段 mp4 | **通过（9/9，同输入预录片段）** | `docs/recording-day7/segments/` 下 9 个 mp4 均落盘；h264/yuv420p/1440×900/30fps，ffprobe 实测 210.17s；无头 Edge 驱动真实页面逐帧截取 + ffmpeg 编码，无旁白音轨、非真人录屏 |
| 2 | 17 张 day8 截图 | **通过（本机实测 17/17）** | `docs/evidence/day8-*.png`，17 个文件均存在；清单见第 2 节 |
| 3 | ffmpeg + libass | **通过** | ffmpeg 9.1 essentials 装于 `D:\ffmpeg\bin` 并写入用户 PATH；`--enable-libass` 编译、`subtitles`/`ass` 滤镜可用；SRT→libass→h264/yuv420p 端到端烧录冒烟通过 |
| 4 | 录制前版本探针留证 | **通过** | `docs/evidence/version-badges.png` 已归档（689,791 B），画面含报价板 `v1` 徽标与控制台浮层 `{count:3, texts:["v1","v1","v1"], expected:"v1", ok:true}` |
| 5 | 双档截图 | **通过** | `docs/evidence/day8-viewport-1440.png`、`day8-viewport-1920.png` 存在（2026-11-20 17:02）；人工目检：无横向滚动、无裁切，版本徽标/结束按钮/控制条/报价板按钮完整 |
| 6 | 产物名同步 | **通过** | 实际 `dist/assets/index-T234zCtM.js`（89,797 B）与 `freeze-day9.md` 第 3/4.1 节逐字一致；本轮未重新构建 |

**总判定：通过（6/6）。** 闸门复绿，但为「可运行候选」口径：第 1 项为同输入预录片段，字幕定稿与成片导出仍待后续卡执行；不得据此宣称「成片已完成」。

---

## 2. 17 张截图实测（与「3 张」提示的差异）

| # | 文件 | 大小 |
|---|---|---|
| 1 | `day8-overview-loaded.png` | 1,245,533 B |
| 2 | `day8-overview-versions.png` | 713,495 B |
| 3 | `day8-board-draft2.png` | 714,175 B |
| 4 | `day8-board-preflight.png` | 1,247,055 B |
| 5 | `day8-protocol-unresolved.png` | 713,694 B |
| 6 | `day8-busy-banner.png` | 1,212,302 B |
| 7 | `day8-conflict-banner.png` | 1,212,497 B |
| 8 | `day8-degraded-empty.png` | 713,591 B |
| 9 | `day8-viewport-1440.png` | 1,245,489 B |
| 10 | `day8-viewport-1920.png` | 1,828,911 B |
| 11 | `day8-finale-five.png` | 684,233 B |
| 12 | `day8-finale-evaluation.png` | 684,319 B |
| 13 | `day8-finale-null.png` | 683,048 B |
| 14 | `day8-finale-evidence.png` | 687,630 B |
| 15 | `day8-finale-datasource.png` | 681,551 B |
| 16 | `day8-autoplay-running.png` | 1,242,149 B |
| 17 | `day8-autoplay-log3.png` | 1,256,210 B |

> **差异说明**：任务上下文提示「登记 17/17，实测 3 张，待核实」。本机目录实测为 **17/17 全部存在**。若录制机同步目录只看到 3 张，属于目录同步差异，应以录制机实测为准；本记录不把实际存在的 17 张写成缺失，也不把未同步的目录写成「已归档」。任何「14 张未见」的结论都缺少本机证据。

---

## 3. 第 9 天四步硬闸门回填

| 步骤 | 状态 | 证据 |
|---|---|---|
| 1 版本探针 | **通过** | `docs/evidence/version-badges.png` 已归档；无头 Edge 打开报价板执行 `versionBadges()` 返回 `{count:3, texts:["v1","v1","v1"], expected:"v1", ok:true}`，截图含返回值与 `v1` 徽标 |
| 2 双档无横向滚动 | **通过** | 两张截图存在；人工目检无横向滚动、无裁切、关键控件完整 |
| 3 失败处置 | **未触发** | 第 1/2 步均通过，未命中阻断第 3 条；无代码改动，不登记 freeze 第 7 节 |
| 4 产物名同步 | **通过** | 实际 `index-T234zCtM.js` 与冻结记录一致；若构建机重构建，必须回填新哈希名 |

---

## 4. 处置

1. 闸门 6/6 + 四步全绿，允许进入第 10 天卡 A（字幕定稿 → demo-v0.2 → 试看）。
2. 已补齐：9 段 mp4（同输入预录片段）、`version-badges.png`、ffmpeg + libass。
3. 口径约束：预录片段无旁白音轨、非真人录屏；**字幕定稿、成片导出、试看验收仍待后续卡执行**，不得据本记录宣称「成片已完成」。
4. 若录制机复核发现预录片段画面与 `day8-*` 截图不一致，按 `recording-day7.md` 应急预案整段重录。
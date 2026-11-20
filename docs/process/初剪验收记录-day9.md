# 第 9 天初剪验收记录

> **结论：初剪未产出（成片层面不变）；素材前置已就绪。**
> 历史原因：素材曾缺 9 段 mp4、工具曾缺 ffmpeg。**2026-11-20 18:34 更新**：9/9 段 mp4 已落盘（同输入预录片段）、ffmpeg 9.1+libass 已装于 `D:\ffmpeg\bin`、`version-badges.png` 已归档，闸门 6/6 复绿。
> 当前仍未生成、也不宣称存在 `final/demo-v0.1.mp4`；`final/` 下没有成片——字幕定稿与成片导出仍待后续卡执行。

---

## 1. 素材到位表

### 1.1 视频段（9 段）

| 段号 | 文件名 | 状态 | 路径 |
|---|---|---|---|
| 01 | `01_overview.mp4` | **已录**（30.10s） | `docs/recording-day7/segments/` |
| 02 | `02_board.mp4` | **已录**（55.07s） | 同上 |
| 03 | `03_protocol.mp4` | **已录**（15.00s） | 同上 |
| 04 | `04_busy_retry.mp4` | **已录**（25.00s） | 同上 |
| 05 | `05_conflict.mp4` | **已录**（25.00s） | 同上 |
| 06 | `06_degraded.mp4` | **已录**（18.00s） | 同上 |
| 07 | `07_viewport.mp4` | **已录**（14.00s） | 同上 |
| 08 | `08_finale.mp4` | **已录**（8.00s） | 同上 |
| 09 | `09_autoplay.mp4` | **已录**（20.00s） | 同上 |

**合计：9/9 段（同输入预录片段，h264/yuv420p/1440×900/30fps，ffprobe 实测 210.17s）。**

### 1.2 day8 截图（17 张）

| 场景 | 文件 | 状态 |
|---|---|---|
| overview | `day8-overview-loaded.png` | **有** |
| overview | `day8-overview-versions.png` | **有** |
| board | `day8-board-draft2.png` | **有** |
| board | `day8-board-preflight.png` | **有** |
| protocol | `day8-protocol-unresolved.png` | **有** |
| busy | `day8-busy-banner.png` | **有** |
| conflict | `day8-conflict-banner.png` | **有** |
| degraded | `day8-degraded-empty.png` | **有** |
| viewport | `day8-viewport-1440.png` | **有** |
| viewport | `day8-viewport-1920.png` | **有** |
| finale | `day8-finale-five.png` | **有** |
| finale | `day8-finale-evaluation.png` | **有** |
| finale | `day8-finale-null.png` | **有** |
| finale | `day8-finale-evidence.png` | **有** |
| finale | `day8-finale-datasource.png` | **有** |
| autoplay | `day8-autoplay-running.png` | **有** |
| autoplay | `day8-autoplay-log3.png` | **有** |

**合计：17/17 张，已归档于 `docs/evidence/`（2026-11-20 17:02）。**

### 1.3 工具

| 工具 | 状态 | 说明 |
|---|---|---|
| ffmpeg | **有**（`D:\ffmpeg\bin`） | gyan.dev 9.1 essentials，`--enable-libass`，`subtitles`/`ass` 滤镜可用；已写入用户 PATH |
| ffprobe | **有**（随 ffmpeg） | 已用于 9 段时长/编码实测 |

### 1.4 录制前硬闸门证据

| 步骤 | 证据 | 状态 |
|---|---|---|
| 1 版本探针 | `docs/evidence/version-badges.png`（`versionBadges()` 返回值截图） | **有**（`{count:3, ok:true}`，689,791 B） |
| 2 双档截图 | `docs/evidence/day8-viewport-1440.png`、`day8-viewport-1920.png` | **有**（人工目检：无横向滚动、无裁切、关键控件完整） |
| 3 失败登记 | `docs/freeze-day9.md` 第 7 节 | 未触发（第 1/2 步均通过） |
| 4 产物名同步 | 实际 `dist/assets/index-T234zCtM.js` 与 freeze 第 3 节一致 | **有**（本轮未重建） |

---

## 2. 未产出说明与补齐时间

| # | 缺失项 | 阻塞原因 | 责任人 | 最晚补齐时间 |
|---|---|---|---|---|
| 1 | 9 段 mp4 | 尚未录制；`segments/` 目录未创建 | D | 2026-11-21 18:00 |
| 2 | ffmpeg / ffprobe | 不在 PATH，无法 concat 与烧字幕 | D | 2026-11-20 23:00 |
| 3 | 9 份 SRT | 视频未录，字幕时间轴无法对齐 | D | 2026-11-21 20:00 |
| 4 | 初剪成片 `final/demo-v0.1.mp4` | 依赖 1–3 | D | 2026-11-21 22:00 |
| 5 | 17 张截图复核 | 已归档，需与录制画面逐张对照 | D | 2026-11-21 20:00 |
| 6 | 错误预热确认（06/07/08） | 需录制机确认 `injectError` 可用且控制台不入镜 | A | 2026-11-20 23:00 |
| 7 | 硬闸门第 1 步 `version-badges.png` | 缺返回值截图，闸门未通过，不得开录 | D | 2026-11-20 23:00 |

> 无「待定」；逾期按 `recording-day7.md` 应急预案降级为「同输入预录片段」，并在素材清单标「已录（降级）」。

---

## 3. 素材齐备后的目标输出（尚未生成）

| 项 | 目标值 |
|---|---|
| 成片文件名 | `final/demo-v0.1.mp4` |
| 时长 | 03:30 ± 10s（205–215s） |
| 分辨率 / 帧率 | 1920×1080 / 30fps |
| 字幕轨 | 硬字幕（9 份 SRT 合并为 `srt/all.srt`） |
| 无字幕原片 | `final/demo-v0.1_nosub.mp4` + `segments/` 9 段原片 |

> 这些是**目标值**，不是已完成记录；素材齐备并实际导出后才可回填实际值。

---

## 4. 试看检查项（当前全部未执行）

| # | 检查项 | 判定 | 当前状态 |
|---|---|---|---|
| 1 | 每段首帧无黑屏 | 9 段首帧均非黑屏 | **未执行（无成片）** |
| 2 | 错误横幅可读（04/05） | SESSION_BUSY / VERSION_CONFLICT 文案可读 | **未执行** |
| 3 | 版本号未被鼠标遮挡 | 三处徽标在镜头 02/09 均可见 | **未执行** |
| 4 | 终局复盘页数据来源声明可见 | `08_finale` 末帧声明未被裁切 | **未执行** |
| 5 | 全程无密钥 / Token / 私有配置 | 画面与控制台均不出现 | **未执行** |
| 6 | 无未实现功能出镜 | 多边 / 知识图谱 / 真实预测均不出现 | **未执行** |
| 7 | 总时长 03:30 ±10s | ffprobe 205–215s | **未执行** |
| 8 | 字幕无分数 / 胜率 / 效率数字 | 逐条检查 | **未执行** |
| 9 | 05A 位于第 5 位 | 时间轴 01:40–02:00 | **未执行** |

---

## 5. 与素材清单的一致性

- `docs/素材整理清单-day8.md`：视频 0/9「待录」；day8 截图 17/17「已归档」。本记录一致。
- 截图有、视频无：**只能是「已录」都不是**；当前是「视频未录、截图已归档」。
- 任何 mp4 产出后，先更新素材清单为「已录」；截图复核通过后才可升「已验收」。
- 本记录不回填不存在的成片时长、分辨率、字幕轨或试看结论。
# 第 8 天素材整理清单（执行台账）

> **基线：`docs/freeze-day9.md`；录制与初剪均基于该基线。**
> **性质**：`docs/recording-day7.md` 的执行台账。不修改其分镜表、旁白稿与时间码，也不修改 `docs/demo-storyboard.md`。
> **当前真实状态（2026-11-20 18:34）**：**9/9 段已录、17/17 张 day8 截图已归档、版本探针截图已归档**；`docs/evidence/` 含 `day8-*.png` 17 张、`version-badges.png` 1 张与 `t6/` 历史证据 10 张；`docs/recording-day7/segments/` 下 9 个 mp4 均已落盘（H.264 / yuv420p / 1440×900 / 30fps，合计 210s = 03:30，ffprobe 实测）。
> **视频产出方式（诚实标注）**：本机无真人录屏条件，9 段为**同输入预录片段**——用无头 Edge 驱动真实单文件版页面、按 `recording-day7.md` 分镜操作序列产生真实渲染画面并逐帧截取，再由 ffmpeg 编码；控制台预热命令未入镜。**无旁白音轨、无系统窗口物理拖拽**，属可运行候选，非真人录屏成片。需录制机复核画面一致性，不能标「已验收」。
> **状态口径**：`待录` = 无 mp4；`已录` = 有 mp4 未验收；`已验收` = mp4 + 截图 + 人工确认。截图同理：`待补` / `已归档`。
> **素材根目录**：`docs/recording-day7/`（`raw/ segments/ srt/ cover/ final/`）。**截图根目录**：`docs/evidence/`。

---

## 1. 视频段清单（9 段）

| 段号 | 文件名 | 覆盖镜头 | 时长 | 来源 | 状态 | 验收截图文件名 |
|---|---|---|---|---|---|---|
| 01 | `01_overview.mp4` | 01–02 | 30s（实测 30.10s） | `recording-day7.md` 第 2 节 | **已录** | `day8-overview-loaded.png`、`day8-overview-versions.png` |
| 02 | `02_board.mp4` | 03–04 | 55s（实测 55.07s） | `recording-day7.md` 第 2 节 | **已录** | `day8-board-draft2.png`、`day8-board-preflight.png` |
| 03 | `03_protocol.mp4` | 05 | 15s（实测 15.00s） | `recording-day7.md` 第 2 节 | **已录** | `day8-protocol-unresolved.png` |
| 04 | `04_busy_retry.mp4` | 06 | 25s（实测 25.00s） | `recording-day7.md` 第 2 节 | **已录** | `day8-busy-banner.png` |
| 05 | `05_conflict.mp4` | 07 | 25s（实测 25.00s） | `recording-day7.md` 第 2 节 | **已录** | `day8-conflict-banner.png` |
| 06 | `06_degraded.mp4` | 08 | 18s（实测 18.00s） | `recording-day7.md` 第 2 节 | **已录** | `day8-degraded-empty.png` |
| 07 | `07_viewport.mp4` | 09 | 14s（实测 14.00s） | `recording-day7.md` 第 2 节 | **已录** | `day8-viewport-1440.png`、`day8-viewport-1920.png` |
| 08 | `08_finale.mp4` | 10 | 8s（实测 8.00s） | `recording-day7.md` 第 2 节 | **已录** | `day8-finale-five.png`、`day8-finale-evaluation.png`、`day8-finale-null.png`、`day8-finale-evidence.png`、`day8-finale-datasource.png` |
| 09 | `09_autoplay.mp4` | 05A | 20s（实测 20.00s） | `recording-day7.md` 第 2 节（第 7 天新增段） | **已录** | `day8-autoplay-running.png`、`day8-autoplay-log3.png` |

- 9 段合计 **210s = 03:30**（ffprobe 实测 210.17s），与 `recording-day7.md` 的录制版总时长一致。
- 段号、镜头号、时间码以 `recording-day7.md` 为准；本表只登记执行状态，不重排时间轴。
- 编码口径：`ffmpeg -c:v libx264 -pix_fmt yuv420p -r 30`，1440×900；段 07 的 1920 帧按比例缩放居中补边到 1440×900（无裁切）。
- 关键帧目检：段 04 含完整 SESSION_BUSY 横幅（错误码 + action_id + 草稿保留）；段 08 复盘页显示真实 withdraw verdict「我方主动退出」与数据来源声明。

---

## 2. 截图清单

### 2.1 第 7/8 天截图（17 张，已归档）

当前路径均为 `docs/evidence/day8-*.png`；归档时间 2026-11-20 17:02。

命名统一 `day8-<场景>-<状态>.png`；场景枚举：overview / board / protocol / busy / conflict / degraded / viewport / finale / autoplay。

| # | 文件名 | 场景 | 对应段 | 状态 | 画面/验收点 |
|---|---|---|---|---|---|
| 1 | `day8-overview-loaded.png` | overview | 01 | **已归档** | 骨架退场、八区域数据落位 |
| 2 | `day8-overview-versions.png` | overview | 01 | **已归档** | 顶栏/报价板/抽屉三处版本同框（`versionBadges().count === 3`） |
| 3 | `day8-board-draft2.png` | board | 02 | **已归档** | 签署板「已修订 2 条 · 未决 N 条」 |
| 4 | `day8-board-preflight.png` | board | 02 | **已归档** | 选卡后行动点 `5 / 5 → 4 / 5` |
| 5 | `day8-protocol-unresolved.png` | protocol | 03 | **已归档** | 未决条款徽标（pending/open）与底部计数 |
| 6 | `day8-busy-banner.png` | busy | 04 | **已归档** | `#errorSlot` 的 SESSION_BUSY 横幅 + 草稿保留 |
| 7 | `day8-conflict-banner.png` | conflict | 05 | **已归档** | `#errorSlot` 的 VERSION_CONFLICT 横幅 + 草稿计数 |
| 8 | `day8-degraded-empty.png` | degraded | 06 | **已归档** | 教练空态（`.coach-empty`）与条款仍可编辑 |
| 9 | `day8-viewport-1440.png` | viewport | 07 | **已归档** | 1440×900 无横向滚动 |
| 10 | `day8-viewport-1920.png` | viewport | 07 | **已归档** | 1920×1080 无横向滚动 |
| 11 | `day8-finale-five.png` | finale | 08 | **已归档** | 终局五态标题/结论之一（五态各录一张可替换） |
| 12 | `day8-finale-evaluation.png` | finale | 08 | **已归档** | 复盘页三维评价同框（谈判结果/协议质量/学习表现） |
| 13 | `day8-finale-null.png` | finale | 08 | **已归档** | `speaker_score === null` 的首轮占位 |
| 14 | `day8-finale-evidence.png` | finale | 08 | **已归档** | 证据链点击跳转后的对话轮次 |
| 15 | `day8-finale-datasource.png` | finale | 08 | **已归档** | 页脚数据来源声明可见 |
| 16 | `day8-autoplay-running.png` | autoplay | 09 | **已归档** | 控制条状态「等待对方回应」 |
| 17 | `day8-autoplay-log3.png` | autoplay | 09 | **已归档** | 推演日志 3 行，每行 `vX / cvY` |

### 2.2 已有历史证据（实际登记，10 张）

> 这些是第 6 天教练 P1 的证据，**不是**第 7/8 天录制截图；不得在索引页冒充 `day8-*`。

| # | 文件 | 来源 | 状态 | 路径 |
|---|---|---|---|---|
| 1 | `t6-collapsed.png` | 第 6 天教练 P1 | **已归档** | `docs/evidence/t6/t6-collapsed.png` |
| 2 | `t6-failed.png` | 第 6 天教练 P1 | **已归档** | `docs/evidence/t6/t6-failed.png` |
| 3 | `t6-filter.png` | 第 6 天教练 P1 | **已归档** | `docs/evidence/t6/t6-filter.png` |
| 4 | `t6-k3-notrigger.png` | 第 6 天教练 P1 | **已归档** | `docs/evidence/t6/t6-k3-notrigger.png` |
| 5 | `t6-leakfilter.png` | 第 6 天教练 P1 | **已归档** | `docs/evidence/t6/t6-leakfilter.png` |
| 6 | `t6-measure-both.png` | 第 6 天教练 P1 | **已归档** | `docs/evidence/t6/t6-measure-both.png` |
| 7 | `t6-no-pollution.png` | 第 6 天教练 P1 | **已归档** | `docs/evidence/t6/t6-no-pollution.png` |
| 8 | `t6-nonblocking.png` | 第 6 天教练 P1 | **已归档** | `docs/evidence/t6/t6-nonblocking.png` |
| 9 | `t6-ready.png` | 第 6 天教练 P1 | **已归档** | `docs/evidence/t6/t6-ready.png` |
| 10 | `t6-stale.png` | 第 6 天教练 P1 | **已归档** | `docs/evidence/t6/t6-stale.png` |

- `docs/evidence/t7`、`t8`、`t9`、`t10`、`t11` 当前**均不存在**，未登记任何文件。

---

## 3. 缺失项清单

> 已完成项保留在表内作为闭环记录；当前真正待办为第 3 / 7 / 8 行（evidence 分目录、评分接入、导出检查收尾）。视频 9 段已产出同输入预录片段（第 1 行）。

| # | 缺失项 | 阻塞原因 | 责任人 | 最晚补齐时间 |
|---|---|---|---|---|
| 1 | 9 段视频已录（`01`–`09`，同输入预录片段） | 已完成：无头 Edge 驱动真实页面按分镜操作逐帧截取 + ffmpeg 编码；9 mp4 落盘 `segments/`，ffprobe 实测 210.17s；待录制机复核画面一致性，未标「已验收」 | D | 已完成（复核 2026-11-21 18:00） |
| 2 | 17 张 `day8-*` 截图已归档（2026-11-20 17:02） | 已完成；录制后若画面变化需重拍同名文件 | D | 已完成（复核 2026-11-21 20:00） |
| 3 | `docs/evidence/t7–t11` 未分目录 | 17 张截图暂存 `docs/evidence/` 根目录；不阻塞初剪 | D | 2026-11-21 18:00 |
| 4 | 06/07/08 错误注入预热脚本已确认 | 已完成：`__diplomat.injectError(...)` 实测 MODEL_UNAVAILABLE / SESSION_BUSY / ROUND_LOCKED / VERSION_CONFLICT 分流；BUSY/CONFLICT 横幅已截图至 `day8-busy-banner.png` / `day8-conflict-banner.png` | A | 已完成 |
| 5 | 三处版本探针已实跑 | 已完成：无头 Edge 实测 `#mVer` / `#bdVer` / `#drVer` v1 三处一致，推进 2 轮后 v3/v3/v3 与 `state.version=3` 同源 | D | 已完成 |
| 6 | 构建机 dist 与单文件版已重生成 | 已完成：`npm run build` 与 `node build-single.mjs` 均 exit 0，第 8 天复盘页与 ActionBar 回挂后已重跑 | D | 已完成 |
| 7 | `speaker_score` 评分区域未接入 | 当前 `state` 无该字段，复盘页显示「终局评价待接入」；不阻塞主片，只阻塞评分截图 | A / C | 2026-11-22 18:00 |
| 8 | 导出检查未执行 | 素材尚未生成 | D | 2026-11-21 22:00 |

> 每条均有责任人与明确状态（待办项含最晚时间，已完成项标注闭环）；**没有「待定」**。若逾期，按 `recording-day7.md` 第 6 节应急预案降级为「同输入预录片段」，并在索引页状态改为「已录（降级）」。

---

## 4. 导出检查

| # | 检查项 | 标准 | 状态 | 确认方式 |
|---|---|---|---|---|
| 1 | 分辨率 | 1920×1080 | `[ ]` 部分：分段实测 1440×900；1920 档见 `day8-viewport-1920.png` 与段 07 原始帧，未产出 1920 成片 | ffprobe + 截图复核 |
| 2 | 帧率 | 30fps | `[x]` 已核对（9 段均 30/1） | ffprobe `r_frame_rate` |
| 3 | 容器/编码 | MP4 / H.264，`yuv420p` | `[x]` 已核对（9 段均 h264/yuv420p） | ffprobe |
| 4 | 完整原片 | `raw/full_*.mp4` 保留 | `[ ]` 未完成（预录片段无真人录屏原片） | 目录检查 |
| 5 | 分段原片 | `segments/01`–`09` 齐全 | `[x]` 已核对（9/9） | 目录检查 + ffprobe |
| 6 | 无字幕原片 | `segments/*_nosub.mp4` 或分段原片本身 | `[x]` 已核对（分段本身即无字幕） | 目录检查 |
| 7 | 字幕 SRT | `srt/<段号>_<镜头名>.srt` 9 份 | `[ ]` 未完成 | 文件数检查 |
| 8 | 封面 | `cover/cover_1920x1080.png` | `[x]` 已核对（1920×1080，由 SVG 经无头 Edge 导出） | ffprobe + 目检 |
| 9 | 讲解词 | 逐镜旁白稿与字幕一致 | `[ ]` 未完成 | 与 `recording-day7.md` 第 4 节对照 |
| 10 | 最终导出 | `final/day7_full_subtitled.mp4` 可播放 | `[ ]` 未完成 | 双击播放 |
| 11 | 密钥/私有配置（代码） | `httpBase` 为空、无 Token、无真实域名 | `[x]` 已检查（2026-11-20） | 源码与运行页检查 |
| 12 | 密钥/私有配置（素材） | 画面不含 `.env`、Token、内网地址 | `[ ]` 未完成 | 导出后逐段抽帧复检 |

---

## 5. 第 10 镜复盘验收点（补进 `08_finale`）

`recording-day7.md` 的分镜表与旁白稿不改；以下为 `08_finale.mp4` 的执行验收点：

| 验收点 | 截图文件 | 判定 |
|---|---|---|
| 三维评价同框 | `day8-finale-evaluation.png` | 谈判结果 / 协议质量 / 学习表现三块同屏，无值显示 `—` |
| 首轮 null 占位 | `day8-finale-null.png` | `speaker_score === null` 时显示「首轮不计分」或「终局评价待接入」，**无 0 分条、无 NaN** |
| 证据跳转 | `day8-finale-evidence.png` | 复盘页证据链点击后关闭弹窗，对话滚到对应轮次 |
| 数据来源声明 | `day8-finale-datasource.png` | 页脚固定文案「本页数字来自本局结构化状态；模型解说仅供参考，不构成事实。」可见 |
| 五态之一 | `day8-finale-five.png` | 五态标题/kicker/tone 与 `ENDGAME_COPY` 一致 |

---

## 6. 索引页

本地打开：`docs/素材索引.html`（双击 `file://`，无网络请求、无外部字体/CDN）。

- 视频段按 9 行展示，状态徽标：**待录灰 / 已录蓝 / 已验收金**。
- 截图缩略图使用相对路径 `evidence/day8-*.png`；17 张均已归档可直接打开，仅文件缺失时显示占位，不伪造图片。
- 历史证据 `evidence/t6/*.png` 单独分区，状态「已归档」，不混入 `day8-*`。
- 页面只读，不在浏览器里写状态；更新状态请改本清单与索引页的硬编码数据。
# 从备份重新导出 / 还原说明（Day 12）

> **素材状态更新附注（2026-11-20 18:34）**：本文表格/结论多为当时历史快照。此后已补齐：版本探针截图 `version-badges.png`（`{count:3, ok:true}`）、9/9 段 mp4（同输入预录片段，ffprobe 实测 210.17s）、ffmpeg 9.1 + libass（`D://ffmpeg//bin`），闸门核对 6/6 复绿。**成片（`final/demo*`）仍未导出、A 会签仍待办——凡「成片未产出 / 不可交付」结论不变。**最新权威状态以 `docs/闸门核对-day10.md`、`docs/素材整理清单-day8.md`、`docs/导出前检查-day11.md` 为准。

> 目标：任何成员拿到 `docs/backup-final/` 后，能按本文还原出**可演示状态**，并（在素材补齐后）重新导出成片。
> 备份根：`11.11/docs/backup-final/`；逐文件 sha256 见 `manifest.json`，执行记录见 `备份执行清单-day12.md`。
> 现状：截图 / 可运行版本 / 文档已备份；视频 / 原片 / 字幕 / 成片当前为 0（阻塞），需先补齐才能导出。

---

## 1. 两种还原场景

| 场景 | 目标 | 是否需要 ffmpeg | 是否需要 9 段 mp4 |
|---|---|---|---|
| **A. 立即演示**（当前可执行） | 打开单文件版现场演示谈判主流程 | 否 | 否 |
| **B. 重剪成片**（待素材补齐） | 从 9 段导出 `demo.mp4` | 是（含 libass） | 是 |

---

## 2. 场景 A：立即演示（不依赖成片、不依赖网络）

1. 从备份复制 `deliverables/Diplomat-单文件版.html` 到演示机，**双击打开**（`file://`，无需服务器、无需网络）。
2. 核对三处版本徽标：`#mVer`（顶栏）/ `#bdVer`（报价板）/ `#drVer`（抽屉），控制台执行 `__diplomat.versionBadges()` 应返回 `{ count: 3, ok: true }`。
3. 按 `recording-day7.md` 的 11 镜顺序走主流程；关键点击后停留 1–2 秒。
4. 若随机议题失败，按 `recording-day7.md` 第 6 节应急预案切「同输入预录片段」，并在工程日志留失败原因。
5. 演示证据用 `screenshots/` 下 17 张 `day8-*.png`（已备份），不与现场画面混用。

> 正式演示优先用这份单文件版，避免依赖临时服务或网络（手册 §10.3）。

---

## 3. 场景 B：重剪成片（素材补齐后）

### 3.1 前置（缺一不可）

- 9 段 mp4 已录到 `segments/`；
- ffmpeg 已安装（**含 libass**）或有可执行文件绝对路径；
- A 已会签讲解词的 5 个事实点与 3 段时间码；
- 第 9 天录制前四步闸门留证齐全（含 `version-badges.png`）。

### 3.2 拼接顺序（关键：段 09 在时间轴第 5 位）

`segments/concat.txt` 必须按以下顺序，**段 09（05A）插在 03 与 04 之间**：

```text
file 'segments/01_overview.mp4'
file 'segments/02_board.mp4'
file 'segments/03_protocol.mp4'
file 'segments/09_autoplay.mp4'      ← 第 4 个文件 / 时间轴第 5 位（01:40–02:00）
file 'segments/04_busy_retry.mp4'
file 'segments/05_conflict.mp4'
file 'segments/06_degraded.mp4'
file 'segments/07_viewport.mp4'
file 'segments/08_finale.mp4'
```

> 段间硬切，不加转场 / xfade / 闪白；不重叠、不加速、不补帧。总时长目标 205–215s。

### 3.3 字幕

- 命名：`srt/<段号>_<镜头名>.srt`（01_overview … 09_autoplay），9 份；
- 合并为 `srt/all.srt`，时间轴按 `recording-day7.md` 的 11 镜累计；
- 规则：只解释结论、不重复屏幕文字；无分数 / 胜率 / 效率数字；不遮挡版本徽标、错误横幅、终局数据来源声明。

### 3.4 导出命令（把 `<FFMPEG>` 换成实际绝对路径）

```bash
# 无字幕原片（保留）
<FFMPEG> -f concat -safe 0 -i segments/concat.txt \
  -c copy -an final/demo-v0.2_nosub.mp4

# 统一规格 + 硬字幕
<FFMPEG> -f concat -safe 0 -i segments/concat.txt \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,fps=30,subtitles=srt/all.srt" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 128k -movflags +faststart \
  final/demo-v0.2.mp4

# 校验
<FFMPEG> -v error -show_entries format=duration -of csv=p=0 final/demo-v0.2.mp4
```

- 若 `subtitles` 滤镜不可用（ffmpeg 未带 libass），改「每段先烧字幕 → 分段转码 → 再 concat」，全程硬切。
- 输出规格：1920×1080 / 30fps / MP4 / H.264 / yuv420p；保留无字幕原片与分段原片不删。

### 3.5 导出后回填

- 把真实时长 / 分辨率 / 字幕轨 / 试看结论填入 `初剪验收记录-day9.md` 与 `成片导出记录-day11.md`；
- 成片产出后增量追加到备份 `video/` 并重算 `manifest.json`；
- 更新素材清单对应段为「已验收」。

---

## 4. 完整性校验（拿到备份先做）

```bash
# 逐文件重算 sha256 前 16 位，与 manifest.json 比对
python -c "import hashlib,json,os; B='docs/backup-final'; [print(r['rel'], hashlib.sha256(open(os.path.join(B,r['rel']),'rb').read()).hexdigest()[:16]==r['sha']) for r in json.load(open(B+'/manifest.json'))]"
```

- 全部 `True` 才算完整；任一 `False` 说明文件损坏或被改动，需从原件重新复制。
- 当前基线：81 个文件 / 25,526,119 B；产物名 `index-T234zCtM.js`（与 `freeze-day9.md` 第 3 节一致，本轮未重建）。

---

## 5. 约束

- 还原过程不改源码；若重建导致 dist 产物名变化，先按 `freeze-day9.md` 第 9 节重冻、刷新第 3 节产物表，再重备份。
- 演示前与交付前各做一次泄露检查（见 `docs/泄露复检-day12.md`）：源码 / 产物 / 文档三面已通过，画面 / 控制台需在录制机补扫。
- 不把预录降级片段说成现场生成；不把目标时长当成实际导出值。
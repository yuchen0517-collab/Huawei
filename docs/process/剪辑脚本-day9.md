# 第 9 天剪辑脚本（Demo 初剪）

> **ffmpeg 已就绪（2026-11-20 17:38）**：gyan.dev ffmpeg 9.1 essentials 装于 **`D:\ffmpeg\bin`**（ffmpeg.exe / ffprobe.exe / ffplay.exe），已写入用户级 PATH，新终端可直接调用。编译含 `--enable-libass`，`subtitles` / `ass` 滤镜可用；端到端冒烟（SRT → libass → h264/yuv420p）通过。本脚本下方命令已统一绑定为 `D:\ffmpeg\bin\ffmpeg.exe`（或直接 `ffmpeg`）。
> **输入基线**：`docs/freeze-day9.md` + `docs/recording-day7.md`（11 镜、9 段、03:30）。
> **素材目录**：`docs/recording-day7/segments/`、`srt/`、`raw/`、`cover/`、`final/`。
> **当前状态（2026-11-20 18:34）**：9/9 段视频已落盘（同输入预录片段，h264/yuv420p/1440×900/30fps，ffprobe 实测 210.17s）；`version-badges.png` 已归档；硬闸门四步全绿。**字幕定稿与成片导出仍待执行**，本文即将进入可执行阶段。
> **硬闸门**：`docs/补录执行包-day9.md` 第 0 节四步已全绿（见 `docs/闸门核对-day10.md` 18:34 复核 6/6）。

---

## 1. 拼接顺序（11 镜 → 9 段文件）

**关键位置**：`09_autoplay.mp4`（镜头 05A）在时间轴第 **5** 位，插在 05 与 06 之间。

| 时间轴 # | 文件段号 | 文件名 | 覆盖镜头 | 时间码 | 时长 |
|---|---|---|---|---|---|
| 1 | 01 | `01_overview.mp4` | 01–02 | 00:00–00:30 | 30s |
| 2 | 02 | `02_board.mp4` | 03–04 | 00:30–01:25 | 55s |
| 3 | 03 | `03_protocol.mp4` | 05 | 01:25–01:40 | 15s |
| **4** | **09** | **`09_autoplay.mp4`** | **05A** | **01:40–02:00** | **20s** |
| 5 | 04 | `04_busy_retry.mp4` | 06 | 02:00–02:25 | 25s |
| 6 | 05 | `05_conflict.mp4` | 07 | 02:25–02:50 | 25s |
| 7 | 06 | `06_degraded.mp4` | 08 | 02:50–03:08 | 18s |
| 8 | 07 | `07_viewport.mp4` | 09 | 03:08–03:22 | 14s |
| 9 | 08 | `08_finale.mp4` | 10 | 03:22–03:30 | 8s |
| 合计 | 9 段 | — | 11 镜 | 00:00–03:30 | **210s** |

> **顺序说明**：任务文字里的「01→…→09」按镜头号理解；镜头 **10** 必须补齐，否则总时长变成 03:22、缺终局复盘。本脚本按 `recording-day7.md` 的 11 镜完整排序，段号 09 的 autoplay 位于第 4 个文件、时间轴第 5 位（05 之后、06 之前）。

**硬切**：全部段间直接拼接，**不加 xfade、转场、动画、闪白**；不重叠、不加速、不补帧。

---

## 2. 字幕

| 项 | 规则 |
|---|---|
| 命名 | `srt/<段号>_<镜头名>.srt`，9 份：`srt/01_overview.srt` … `srt/09_autoplay.srt` |
| 内容 | 只解释结论与判断依据，不重复屏幕文字；不写分数、胜率、效率提升 |
| 位置 | 底部安全区，不遮挡版本徽标、错误横幅、数据来源声明 |
| 数据来源帧 | `08_finale` 的页脚声明所在帧**不得裁切、不得被字幕遮挡** |
| 合并 | 若使用全片硬字幕，先把 9 份合并为 `srt/all.srt`，时间轴按上表累计 |
| 语言 | 简体中文；不出现未实现功能、真实预测、对方私有底牌 |

---

## 3. 输出规格

| 项 | 标准 |
|---|---|
| 分辨率 | 1920×1080 |
| 帧率 | 30fps |
| 容器/编码 | MP4 / H.264 / `yuv420p` |
| 音频 | AAC 128k（无人声时保留静音轨或 `-an` 版本） |
| 命名 | 初剪：`final/demo-v0.1.mp4`；无字幕原片：`final/demo-v0.1_nosub.mp4` |
| 保留 | `segments/` 9 段无字幕原片、`raw/` 完整原片不得删 |
| 时长 | **03:30 ± 10s（205–215s）** |

---

## 4. ffmpeg 命令模板

> 以下命令已绑定实际可执行文件绝对路径 `D:\ffmpeg\bin\ffmpeg.exe`（libass 就绪，可直接执行）；若换机，只需把路径替换为本机 ffmpeg 可执行文件位置。

### 4.1 concat 列表

`segments/concat.txt`：

```text
file 'segments/01_overview.mp4'
file 'segments/02_board.mp4'
file 'segments/03_protocol.mp4'
file 'segments/09_autoplay.mp4'
file 'segments/04_busy_retry.mp4'
file 'segments/05_conflict.mp4'
file 'segments/06_degraded.mp4'
file 'segments/07_viewport.mp4'
file 'segments/08_finale.mp4'
```

### 4.2 无字幕原片（保留）

```bash
D:\ffmpeg\bin\ffmpeg.exe -f concat -safe 0 -i segments/concat.txt \
  -c copy -an final/demo-v0.1_nosub.mp4
```

### 4.3 统一规格 + 硬字幕（初剪）

```bash
D:\ffmpeg\bin\ffmpeg.exe -f concat -safe 0 -i segments/concat.txt \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,fps=30,subtitles=srt/all.srt" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 128k -movflags +faststart \
  final/demo-v0.1.mp4
```

- `subtitles` 需要 ffmpeg 带 **libass**；若不可用，改为「每段先烧字幕 → 分段转码 → 再 concat」，全程硬切。
- 若源段分辨率/帧率不一，先统一转码到 1920×1080/30fps 再 concat，避免花屏。

### 4.4 时长与首帧校验

```bash
# 时长（秒）
D:\ffmpeg\bin\ffmpeg.exe -v error -show_entries format=duration -of csv=p=0 final/demo-v0.1.mp4

# 每段首帧（查黑屏）
D:\ffmpeg\bin\ffmpeg.exe -ss 0 -i segments/01_overview.mp4 -frames:v 1 -y cover/01_first.png
```

**通过标准**：时长 205–215s；9 段首帧均非黑屏；`08_finale` 末帧数据来源声明可见。

---

## 5. 试看前自查

1. 9 段拼接顺序与第 1 节一致，05A 在第 5 位。
2. 段间无转场、无动画、无闪白。
3. 总时长 03:30 ±10s。
4. 字幕无分数/胜率/效率数字；不重复屏幕文字。
5. `08_finale` 的数据来源声明未被裁切。
6. 无控制台画面、无未实现功能、无密钥/Token/私有底牌。
7. 错误横幅（04/05）可读，版本徽标未被鼠标遮挡。
8. 若任一项不通过，**不产出「已完成初剪」表述**；回到补录或重剪。
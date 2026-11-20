# 离线备份清单（Day 10）

> **素材状态更新附注（2026-11-20 18:34）**：本文表格/结论多为当时历史快照。此后已补齐：版本探针截图 `version-badges.png`（`{count:3, ok:true}`）、9/9 段 mp4（同输入预录片段，ffprobe 实测 210.17s）、ffmpeg 9.1 + libass（`D://ffmpeg//bin`），闸门核对 6/6 复绿。**成片（`final/demo*`）仍未导出、A 会签仍待办——凡「成片未产出 / 不可交付」结论不变。**最新权威状态以 `docs/闸门核对-day10.md`、`docs/素材整理清单-day8.md`、`docs/导出前检查-day11.md` 为准。

> **备份根**：`docs/backup-day10/`（尚未创建）。
> **备份策略**：镜像仓库根相对路径，例如 `Diplomat-components(1)/dist/...` → `docs/backup-day10/Diplomat-components(1)/dist/...`；`docs/evidence/...` → `docs/backup-day10/docs/evidence/...`。
> **正式演示优先**：`Diplomat-单文件版.html`（双击即开），不依赖网络、不依赖临时服务。
> **状态**：manifest 覆盖 47 个真实文件；视频 / 成片 / 字幕当前为 0，未列入 hash。

---

## 1. manifest（文件名 + 大小 + sha256 前 16 位）

| 原路径 | 大小 (B) | sha256 前 16 位 |
|---|---:|---|
| `Diplomat-components(1)/Diplomat-单文件版.html` | 760,746 | `9707e3c8d1223801` |
| `Diplomat-components(1)/dist/index.html` | 651 | `f919b2c1b5a79cee` |
| `Diplomat-components(1)/dist/assets/index-T234zCtM.js` | 89,797 | `3d1c896347e61d6a` |
| `Diplomat-components(1)/dist/assets/index-C-VXQy_A.css` | 70,007 | `5b60c3884d967bf3` |
| `Diplomat-components(1)/dist/assets/G01-COc-yrk7.jpg` | 123,145 | `69d5c43ceb89721d` |
| `docs/freeze-day9.md` | 9,890 | `888dccf31e98b8fe` |
| `docs/recording-day7.md` | 16,786 | `1677d68e496a12c8` |
| `docs/素材整理清单-day8.md` | 10,876 | `389f374f3be1b957` |
| `docs/讲解词-day10.md` | 4,816 | `e49d5bcb9749bcd7` |
| `docs/视觉规范-day10.md` | 3,169 | `b2c889a09b53fcb7` |
| `docs/剪辑脚本-day9.md` | 5,418 | `666f65ad1af39743` |
| `docs/补录执行包-day9.md` | 12,188 | `42d484afd8cfec5a` |
| `docs/初剪验收记录-day9.md` | 5,592 | `265e2a35d8883fd7` |
| `docs/闸门核对-day10.md` | 3,831 | `38f216e7f8545500` |
| `docs/试看修正台账-day10.md` | 2,564 | `80ea64a7d438b07a` |
| `docs/应急记录-day10.md` | 1,808 | `e64c7cb3071a1f20` |
| `docs/给A的消息-接口回签-1117.md` | 11,856 | `033319c881c87f18` |
| `docs/coach-contract.md` | 16,399 | `a892346816dfa381` |
| `docs/state-contract.md` | 36,861 | `1ae9a293ffe7e8d9` |
| `docs/acceptance-checklist.md` | 7,039 | `13146c8227598e4a` |
| `docs/recording-day7/cover/cover_1920x1080.svg` | 1,384 | `17b1b143fa67f5c4` |
| `docs/evidence/day8-autoplay-log3.png` | 1,256,210 | `65c291f619ea00fd` |
| `docs/evidence/day8-autoplay-running.png` | 1,242,149 | `e65f5af59efc769d` |
| `docs/evidence/day8-board-draft2.png` | 714,175 | `293bfc0351ecfab2` |
| `docs/evidence/day8-board-preflight.png` | 1,247,055 | `23d07935a4ca6eb5` |
| `docs/evidence/day8-busy-banner.png` | 1,212,302 | `747491c73242605c` |
| `docs/evidence/day8-conflict-banner.png` | 1,212,497 | `ba87604e41c84a9d` |
| `docs/evidence/day8-degraded-empty.png` | 713,591 | `e921f149649ea676` |
| `docs/evidence/day8-finale-datasource.png` | 681,551 | `fd7b0a9f7843154a` |
| `docs/evidence/day8-finale-evaluation.png` | 684,319 | `124b103ca2f0e86e` |
| `docs/evidence/day8-finale-evidence.png` | 687,630 | `93ef91220938eee1` |
| `docs/evidence/day8-finale-five.png` | 684,233 | `0abe3cd2c8846c36` |
| `docs/evidence/day8-finale-null.png` | 683,048 | `ecfef9d8691e5f09` |
| `docs/evidence/day8-overview-loaded.png` | 1,245,533 | `23d02047ef71d1fe` |
| `docs/evidence/day8-overview-versions.png` | 713,495 | `8c086335f3a60c77` |
| `docs/evidence/day8-protocol-unresolved.png` | 713,694 | `2e1cfd9f25b398d8` |
| `docs/evidence/day8-viewport-1440.png` | 1,245,489 | `c3c290cd7f2b4a70` |
| `docs/evidence/day8-viewport-1920.png` | 1,828,911 | `97b3a1259e0bc090` |
| `docs/evidence/t6/t6-collapsed.png` | 283,721 | `4bafc2aca4cb65a5` |
| `docs/evidence/t6/t6-failed.png` | 285,984 | `5323462ff933ba79` |
| `docs/evidence/t6/t6-filter.png` | 293,487 | `07f09c6906b03abc` |
| `docs/evidence/t6/t6-k3-notrigger.png` | 1,313,939 | `310dc2561ccdd02c` |
| `docs/evidence/t6/t6-leakfilter.png` | 284,153 | `f13f39e3330a81fd` |
| `docs/evidence/t6/t6-measure-both.png` | 908,429 | `d6c4666fdf432b5d` |
| `docs/evidence/t6/t6-no-pollution.png` | 1,359,404 | `1e3cb08adcd3be8c` |
| `docs/evidence/t6/t6-nonblocking.png` | 1,372,556 | `af2aa10374c3fb9d` |
| `docs/evidence/t6/t6-ready.png` | 301,314 | `440cbe7ef27fff49` |
| `docs/evidence/t6/t6-stale.png` | 301,366 | `a7dbb8a174e510a4` |

---

## 2. 随机抽检 2 项（可按 sha256 复核）

| 抽检文件 | 大小 | 完整 sha256 前 16 位 | 复核命令（PowerShell） |
|---|---:|---|---|
| `docs/evidence/day8-overview-loaded.png` | 1,245,533 | `23d02047ef71d1fe` | `(Get-FileHash -Algorithm SHA256 "docs\evidence\day8-overview-loaded.png").Hash.Substring(0,16)` |
| `docs/freeze-day9.md` | 9,890 | `888dccf31e98b8fe` | `(Get-FileHash -Algorithm SHA256 "docs\freeze-day9.md").Hash.Substring(0,16)` |

> 复核对上即通过；不一致说明备份文件被改动或复制不完整，不得用于正式演示。

---

## 3. 缺失项（未列入 manifest）

| 项 | 状态 | 说明 |
|---|---|---|
| `segments/` 9 段 mp4 | **无（0/9）** | 未录制 |
| `srt/` 9 份 + `all.srt` | **无** | 无视频，未生成 |
| `raw/` 完整原片 | **无** | 未录制 |
| `final/demo-v0.2.mp4` / `_nosub` | **无** | 闸门不通过，未生成 |
| `docs/evidence/version-badges.png` | **无** | 硬闸门第 1 步未完成 |
| `cover/cover_1920x1080.png` | **无** | 仅有 SVG 源；PNG 未导出 |
| `docs/evidence/t7–t11` | **无** | 目录不存在 |

> 缺失项不得写入「已完成」；待补齐后重新计算 manifest 并追加本表。

---

## 4. 备份与重导说明

1. 创建备份根：
   ```powershell
   New-Item -ItemType Directory -Force "docs\backup-day10"
   ```
2. 复制可运行版本与素材（保持相对结构）：
   ```powershell
   Copy-Item "Diplomat-components(1)\Diplomat-单文件版.html" "docs\backup-day10\" -Force
   Copy-Item "Diplomat-components(1)\dist" "docs\backup-day10\dist" -Recurse -Force
   Copy-Item "docs\evidence" "docs\backup-day10\evidence" -Recurse -Force
   Copy-Item "docs\recording-day7\cover" "docs\backup-day10\cover" -Recurse -Force
   ```
3. 复制文档：按 manifest 的 `docs/*.md` 逐项复制（不要递归复制 `docs\backup-day10` 自身）。
4. 复核：对 47 项逐一执行 `Get-FileHash -Algorithm SHA256`，前 16 位与 manifest 一致。
5. 重新打开：
   - 正式演示：双击 `Diplomat-单文件版.html`（离线可用）。
   - dist 预览：`py -m http.server 8000 --directory Diplomat-components(1)/dist`，访问本机 `127.0.0.1:8000`（仅本机，不写域名）。
6. 重新导出视频：当前无素材、无 ffmpeg；命令模板见 `docs/剪辑脚本-day9.md` 第 4 节，未就绪前不导出。
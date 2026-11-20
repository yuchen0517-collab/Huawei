# Demo 基线冻结记录（Day 9）

> **冻结时间**：2026-11-20（以构建产物时间 `16:50:19`、单文件版 `16:50:25` 为准）
> **基线版本**：`diplomat-negotiation-ui@1.0.0`
> **git**：当前目录**不是 git 仓库**，`git` 命令在本机不可用；无 commit 号，以第 2 节的 sha256 清单作为等效基线。
> **冻结状态**：**条件冻结**。构建产物与静态检查通过；运行时版本探针与双档截图原归卡 B，**已于 2026-11-20 18:21–18:34 用无头 Edge 复跑通过**（`version-badges.png` 归档、双档截图人工目检无滚动无裁切）。未命中第 6 节任一阻断项，允许进入录制与初剪；9 段同输入预录片段已产出。**冻结产物未变**（`index-T234zCtM.js`），本轮只改 docs，未重新构建。

---

## 1. 基线标识

| 项 | 值 |
|---|---|
| 项目 | Diplomat 外交谈判智能体 · 前端 Demo |
| 目录 | `11.11/Diplomat-components(1)` |
| package name / version | `diplomat-negotiation-ui` / `1.0.0` |
| 构建产物时间 | `dist/index.html` 2026-11-20 16:50:19；单文件版 2026-11-20 16:50:25 |
| 冻结范围 | `src/**`、`index.html`、`styles.css`、`build-single.mjs`、`package.json` |
| 不冻结范围 | `docs/**`（台账、索引页、冻结记录本身） |
| 录制母版 | `docs/recording-day7.md`（11 镜、9 段、03:30）；`docs/demo-storyboard.md` 只读 |

---

## 2. 关键源文件摘要（sha256 前 16 位）

| # | 文件 | sha256 前 16 位 |
|---|---|---|
| 1 | `src/main.js` | `eccf6d514d3463ff` |
| 2 | `src/stores/NegotiationStore.js` | `7b00d1970239115f` |
| 3 | `src/domain/negotiation.js` | `c172a83b2678df15` |
| 4 | `src/domain/clauses.js` | `839d785c99e1d6e7` |
| 5 | `src/domain/endgame.js` | `e09e2802a3876cbf` |
| 6 | `src/domain/debrief.js` | `295dd742f382bb89` |
| 7 | `src/components/DebriefPage.js` | `06e901e15aa8292d` |
| 8 | `src/components/ActionBar.js` | `d23639286fb935cd` |
| 9 | `src/components/AutoPlayPanel.js` | `e0e1251204faf132` |
| 10 | `src/components/ClauseBoard.js` | `fdd05451124032e8` |
| 11 | `src/components/StatusStrip.js` | `ba8fd162e78c50fb` |
| 12 | `src/components/Topbar.js` | `245df4b722864a19` |
| 13 | `src/components/StrategyPanel.js` | `d3a1a67430517323` |
| 14 | `src/components/content.js` | `8365492fdcfd388c` |
| 15 | `src/components/Drawer.js` | `69938435215bc5e9` |
| 16 | `src/components/Modal.js` | `f7c3bc40aee8c15d` |
| 17 | `src/services/adapter.js` | `4e3c7a0c1f5156a2` |
| 18 | `src/services/idempotency.js` | `a58fe94453f583d2` |
| 19 | `src/services/coach.js` | `eab1cae8e41f0e00` |
| 20 | `src/styles.css` | `7a65a7ad61f32dad` |
| 21 | `index.html` | `a43a2a9df12011f1` |
| 22 | `package.json` | `33fd917a5a9c07e0` |
| 23 | `build-single.mjs` | `d4be98aa03333ab6` |

> 摘要口径：对文件原始字节计算 SHA-256，取前 16 位；完整值可通过同一算法复核。

---

## 3. 构建产物（实际值）

| 产物 | 实际路径 | 大小 | 时间 |
|---|---|---|---|
| dist HTML | `Diplomat-components(1)/dist/index.html` | 651 B | 2026-11-20 16:50:19 |
| dist JS | `Diplomat-components(1)/dist/assets/index-T234zCtM.js`（当前实际文件，未重建） | **89,797 B** | 2026-11-20 16:50:19 |
| dist CSS | `Diplomat-components(1)/dist/assets/index-C-VXQy_A.css` | **70,007 B** | 2026-11-20 16:50:19 |
| dist 事件卡图 | `Diplomat-components(1)/dist/assets/G01-COc-yrk7.jpg` | 123,145 B | 2026-11-20 16:50:19 |
| 单文件版 | `Diplomat-components(1)/Diplomat-单文件版.html` | **760,746 B**（磁盘字节） | 2026-11-20 16:50:25 |

**单文件版标记核对**（minified IIFE 中仍保留的字符串）：

| 标记 | 出现次数 | 说明 |
|---|---|---|
| `autoplay-panel` | 2 | 自动推演控制条存在 |
| `debriefPage` | 1 | 复盘页根节点存在 |
| `debrief-page` | 2 | 复盘页样式/结构存在 |
| `version-chip` | 5 | 三处版本徽标样式与节点 |
| `debrief-source` | 2 | 数据来源声明存在 |

> **记录差异**：此前口头提到的 dist JS 名为 `index-CL6QEXd8.js`，**实际文件是 `index-T234zCtM.js`**。本记录以实际文件为准，不写预计值；若构建机再次构建，产物名会变化，届时必须重新冻结。

---

## 4. 三项回归

### 4.1 构建（①）

| 项 | 结果 | 证据 |
|---|---|---|
| `npm run build` | **构建机执行通过**（D 报告，2026-11-20 16:50） | `dist/index.html` 引用 `./assets/index-T234zCtM.js`，文件存在且大小 89,797 B |
| `node build-single.mjs` | **构建机执行通过**（D 报告，2026-11-20 16:50） | `Diplomat-单文件版.html` 存在，760,746 B，时间 16:50:25 |
| 单文件版包含 autoplay-panel / DebriefPage 标记 | **通过** | 见第 3 节标记表 |
| 本机复跑 | **未执行**：本机无 Node/npm | 不作为通过依据，也不伪造退出码 |

### 4.2 版本探针（②）

| 项 | 结果 | 证据 |
|---|---|---|
| 三处版本节点存在 | **静态通过** | `Topbar.js` 的 `#mVer`、`content.js` 的 `#bdVer`、`Drawer.js` 的 `#drVer` |
| 三处同源更新 | **静态通过** | `main.js` 的 `renderVersion()` 同时写 `#mVer / #bdVer / #drVer` |
| 探针函数存在 | **静态通过** | `__diplomat.versionBadges()` 返回 `{ count, texts, expected, ok }` |
| 运行时 `count === 3` | **通过（2026-11-20 18:21）** | `docs/evidence/version-badges.png` 已归档；无头 Edge 打开报价板执行 `__diplomat.versionBadges()` 返回 `{count:3, texts:["v1","v1","v1"], expected:"v1", ok:true}`，截图含返回值与 `v1` 徽标 |

> 运行时探针已通过，三处版本一致；第 6 节第 3 条未触发，无代码改动，第 7 节无需登记。

### 4.3 双档（③）

| 项 | 结果 | 说明 |
|---|---|---|
| 1440×900 无横向滚动 | **通过（图像复核）** | `docs/evidence/day8-viewport-1440.png` 已归档（2026-11-20 17:02）；图像复核：无横向滚动，版本徽标、结束本轮按钮、自动推演控制条完整 |
| 1920×1080 无横向滚动 | **通过（图像复核）** | `docs/evidence/day8-viewport-1920.png` 已归档（2026-11-20 17:02）；图像复核结论同上 |

> 图像复核为辅助证据，录制前仍建议人工目检一次；两张截图均无横向滚动、关键控件未被裁切。

---

## 5. 冻结前修复

**无。** 本卡只产出冻结记录与闸门规则，未修改任何源代码；未发现需要先修的阻断项。

---

## 6. 「阻断演示」定义（只有命中任一条才允许改代码）

1. **主闭环任一步点不动或走不到终局**：选卡、改条款、提交、对方回应、终局入口任一不可用。
2. **1440×900 或 1920×1080 出现横向滚动、关键控件被裁**：版本徽标、提交按钮、控制条、复盘页关键区块不可见。
3. **三处版本号不一致或探针 `count !== 3`**：`#mVer / #bdVer / #drVer` 文本不同，或探针 `ok === false`。
4. **`vite build` 或 `build-single.mjs` 失败、单文件版白屏**：构建退出码非 0，或 `file://` 打开无界面。
5. **出现密钥 / Token / 对方私有底牌**：源码、构建产物、画面、控制台、素材文件任一命中。
6. **终局复盘页无法打开，或首轮 `null` 显示成 0 / NaN**：`openDebrief()` 不可用、`#debriefPage` 缺失、`speaker_score` 空值被填 0。

**判定要求**：每条必须能指向上述六条之一，并附复现步骤/截图/控制台。不能指向的，一律不做。

---

## 7. 冻结后改动登记表（初始为空）

| 时间 | 文件 | 原因 | 命中阻断条 | 是否阻断 | 批准人 | 回归结果 |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

> 新增一行必须同时填写「命中阻断条」与「批准人」；空着即视为违规改动。批准人：D 自批仅限第 1/3/4 条且需留证；第 2/5/6 条需 A 或 C 会签。

---

## 8. 不做清单（未命中阻断，冻结期一律不做）

1. **动效 / 转场 / 粒子 / 精致动画**：冻结期不加。
2. **配色、阴影、字体、间距微调**：不影响主闭环，不做。
3. **文案润色与措辞优化**：除阻断外的文案不改。
4. **额外场景、随机议题、多边视图**：不新增场景与分支。
5. **卡池扩容、数值平衡**：不改策略卡与指数权重。
6. **P1/P2 功能**：知识图谱、关系矩阵、真实事件预测一律不做。
7. **目录重构 / 组件拆分 / 命名调整**：冻结期不做结构改造。
8. **依赖升级 / 新增依赖**：不引入任何 npm 包或 CDN。
9. **非阻断性能优化**：不为了「更快」改渲染链路。
10. **测试补全与非阻断重构**：不顺手扩大改动面。

---

## 9. 闸门流程

1. **发现**：复现问题，保留截图、控制台、操作步骤。
2. **对照**：逐条核对第 6 节六条；不能命中即写入第 8 节「不做清单」。
3. **登记**：在第 7 节写时间 / 文件 / 原因 / 命中条款 / 是否阻断 / 批准人。
4. **修复**：只改命中条款所需的最小范围，不顺手改 UI/文案/结构。
5. **回归**：至少复跑受影响项；构建类阻断必须重跑两条构建，并重新核对产物名与大小。
6. **更新基线**：若产物变化，追加「冻结后基线变更」记录；未记录不得进入录制/初剪。

---

## 10. 三份文档口径一致性

| 文档 | 口径 |
|---|---|
| `docs/demo-storyboard.md` | 母版 10 镜，只读，不修改 |
| `docs/recording-day7.md` | 11 镜（01–10 + 05A）、9 段、总时长 03:30；分镜与时间码不改 |
| `docs/素材整理清单-day8.md` | 9 段、17 张 day8 截图、10 张 t6 历史证据；本记录为基线引用 |
| 本记录 | 段号 01–09、镜头 01–10 + 05A、03:30；不新增段号、不改时间码 |

> 基线引用已加到 `docs/素材整理清单-day8.md` 顶部：  
> 「基线：`docs/freeze-day9.md`；录制与初剪均基于该基线。」
# Diplomat 前端领域文档

## 1. 文档目的与领域边界

本项目是“全球 AI 治理框架公约”双边谈判的单页交互原型。前端负责策略选择、行动点校验、轮次推进、对话展示、态势指标、谈判战报和辅助信息弹窗。

当前领域边界：

- **前端负责**：演示数据、交互状态、既定规则下的指标变化、界面渲染、主题与本地偏好。
- **前端不负责**：真实外交推演、AI 对手生成、账号与多人会话、服务端持久化、正式协议约束。
- **展示与规则分离**：组件只生成界面；业务状态只能由 `NegotiationStore` 修改；`main.js` 负责协调二者。
- **技术栈**：原生 JavaScript ES Modules、HTML、CSS、Vite。组件返回 HTML 字符串，不依赖 React 或虚拟 DOM。

## 2. 目录结构

```text
./
├── index.html                       # 轻量 HTML 入口，仅保留 #app
├── public/
│   └── report-logo.png              # 战报圆形图标
├── src/
│   ├── main.js                      # 应用协调器：渲染、事件分发、异步回应
│   ├── styles.css                   # 设计令牌、组件样式、主题与响应式
│   ├── domain/
│   │   └── negotiation.js           # 议题、策略目录、代表团、初始发言与状态
│   ├── stores/
│   │   └── NegotiationStore.js      # UI 无关的业务状态与规则
│   └── components/
│       ├── index.js                 # 组件统一出口
│       ├── ui.js                    # 通用渲染工具与基础 UI
│       ├── IconSprite.js            # SVG 图标定义
│       ├── Topbar.js                # 品牌、轮次和全局操作
│       ├── Topicbar.js              # 当前议题、事件与谈判树入口
│       ├── StrategyPanel.js         # 策略卡、手牌区与行动点
│       ├── DialogueStage.js         # 公开会场与发言
│       ├── SituationPanel.js        # 态势指标与折叠信息模块
│       ├── Modal.js                 # 弹窗结构、控制器与焦点管理
│       ├── Toast.js                 # 轻提示结构及控制器
│       ├── content.js               # 战报、事件、谈判树等弹窗内容
│       └── NegotiationApp.js        # 页面级组件组合
└── domain.md                        # 本文档
```

依赖方向保持单向：

```text
main.js → components → domain（仅读取展示所需的常量）
main.js → stores → domain
components 之间可复用基础 UI，但不得反向依赖 main.js 或 store 实例
```

## 3. 领域数据模型

### 3.1 议题 `topic`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `string` | 议题稳定标识 |
| `eyebrow` | `string` | 英文眉题 |
| `title` | `string` | 议题名称 |
| `mode` | `string` | 谈判模式 |
| `maxRounds` | `number` | 最大轮次，当前为 15 |

### 3.2 策略 `strategy`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `string` | 卡牌与规则共用的稳定标识 |
| `cost` | `number` | 行动点消耗 |
| `type` | `string` | 策略类型与战术标签 |
| `name` | `string` | 卡牌名称 |
| `description` | `string` | 行为说明 |
| `effect` | `string` | 面向用户的预期效果 |
| `recommended` | `boolean?` | 是否展示“顾问建议” |

`strategyCatalog` 是卡牌唯一数据源。卡牌 DOM 使用 `data-strategy-id` 关联目录，不再从 DOM 读取成本或名称作为业务依据。

### 3.3 代表团 `parties`

以 `us`、`cn` 为键，包含 `id`、`code`、`name`；我方另有 `self: true`，用于决定发言布局和视觉样式。

### 3.4 谈判状态 `NegotiationState`

```js
{
  round: 1,
  maxRounds: 15,
  actionPoints: 5,
  selectedIds: [],
  metrics: { interest: 62, image: 74, trust: 58 },
  log: [{ round: 1, text: '双方完成开场陈述，美方释放有限合作窗口。' }],
  ended: false,
  eventRead: false
}
```

- `round`：下一轮待提交的轮次；第 15 轮结算后内部值可变为 16，显示时封顶为 15。
- `selectedIds`：当前已选卡牌，不保存重复项。
- `metrics`：三项指标范围为 0～100；当前规则只增加且封顶 100。
- `log`：战报和谈判树共享的按发生顺序排列的记录。
- `ended`：结束后禁止继续出牌和结算。
- `eventRead`：控制突发事件未读数量；重置时恢复未读。

## 4. 状态仓库与业务规则

### 4.1 `NegotiationStore` API

| 成员 | 返回 | 职责 |
| --- | --- | --- |
| `state` | `NegotiationState` | 当前状态，供协调器读取和渲染 |
| `strategyMap` | `Map` | 按 id 获取策略定义 |
| `selectedStrategies` | `Strategy[]` | 当前已选策略完整对象 |
| `usedActionPoints` | `number` | 已选策略成本之和 |
| `canEndTurn` | `boolean` | 是否满足本轮结算条件 |
| `toggleStrategy(id)` | `{ ok, selected? , reason? }` | 选择或取消策略，并校验行动点 |
| `endTurn()` | `TurnResult \| null` | 结算指标、记录日志、清空选择并推进轮次 |
| `recordOpponentReply(round)` | `void` | 将对方回应写入战报 |
| `recordPrivateIntent()` | `void` | 将非正式意向写入战报 |
| `markEventRead()` | `void` | 标记突发事件已读 |
| `end()` | `void` | 结束本场谈判 |
| `reset()` | `void` | 替换为全新初始状态 |

`toggleStrategy` 的失败原因包括：`ended`、`points`、`unknown`。界面负责把原因翻译为提示文案。

### 4.2 行动点和轮次规则

1. 每轮共有 5 点行动点；同一卡牌最多选择一次。
2. 新卡牌成本与已用点数之和超过 5 时，选择失败，原选择不变。
3. 至少选择一张卡牌且谈判未结束、轮次未超限时，才能结束本轮。
4. 结算后立即清空选择并推进轮次，再异步追加对方回应。
5. 当前演示指标规则：`bundle` 或 `package` 使主体利益 +3（同时选择也只加一次）；`initiative` 使国际形象 +2；`concession` 或 `clarify` 使盟友信任 +1（同时选择也只加一次）。
6. 结束谈判会取消待执行的对方回应；重新谈判会恢复所有初始业务数据。

**约定**：事件处理函数不得直接改写 `store.state` 来绕过仓库。新增规则优先封装为仓库方法；纯展示偏好（例如主题、侧栏折叠）可以留在协调器或 DOM 中。

## 5. 组件契约

除控制器外，下列组件均为“输入参数 → HTML 字符串”的纯渲染函数，不自行绑定事件。

### 5.1 基础组件 `ui.js`

| 导出 | 参数 | 用途 |
| --- | --- | --- |
| `escapeHTML(value)` | 任意可字符串化值 | 转义动态文本，防止 HTML 注入 |
| `icon(name, className?)` | 图标名、附加类名 | 引用 `IconSprite` 中的 SVG symbol |
| `Avatar({ party, mini? })` | 代表团、是否小尺寸 | 代表团头像 |
| `PanelHeading({ kicker, title, collapseAction, direction?, collapseLabel })` | 标题及折叠行为 | 侧栏统一标题栏 |
| `FoldSection({ title, badge?, open?, content })` | 标题、徽标、初始开合、可信内容 | 原生 `details` 折叠模块 |
| `Metric({ id, label, value, delta, tone?, previous, negative? })` | 单项指标定义 | 数值、变化量和进度轨道 |
| `formatRound(round)` | 数字 | 格式化为两位轮次 |

### 5.2 页面与内容组件

| 组件 | 主要参数 | 职责 |
| --- | --- | --- |
| `NegotiationApp` | `{ state, usedActionPoints, canEndTurn }` | 组合完整应用；只在入口挂载时调用 |
| `Topbar` | `{ round, maxRounds }` | 品牌、当前轮次、主题及谈判全局操作 |
| `Topicbar` | `{ topic, unreadEvents }` | 议题与辅助入口 |
| `StrategyCard` | `{ strategy, selected? }` | 单张可选策略卡 |
| `StrategyCards` | `{ strategies, selectedIds? }` | 策略卡列表，用于局部刷新 |
| `HandFooterContent` | `{ used, total, canEndTurn }` | 行动点和本轮结算按钮 |
| `StrategyPanel` | `{ strategies, selectedIds, used, total, canEndTurn }` | 完整策略侧栏及恢复按钮 |
| `Speech` | `{ party, label, text?, html?, badge?, advisor? }` | 单条公开发言 |
| `DialogueMessages` | `{ speeches }` | 开场提示和消息列表，用于重置对话 |
| `DialogueStage` | `{ speeches }` | 公开会场和战报入口 |
| `MetricList` | `{ metrics }` | 三项态势指标，用于局部刷新 |
| `SituationPanel` | `{ metrics }` | 五个折叠模块及侧栏恢复按钮 |
| `ReportContent` | `{ topic, state }` | 当前轮次、指标和完整战报 |
| `EventContent` | `{ topic }` | 突发事件详情 |
| `TreeContent` | `{ log }` | 按日志生成谈判路径 |
| `OpponentIntelContent` | 无 | 对方态势的研判依据 |
| `ChannelContent` | 无 | 非正式沟通内容与规则 |

### 5.3 控制器

- `ModalController(root)`：`open(config)` 设置标题、内容、主/次操作并打开；`close()` 关闭并恢复此前焦点；`handleKeyboard(event)` 处理 Esc 和 Tab 焦点圈定。
- `ToastController(root, duration?)`：`show(message)` 展示文本并自动隐藏，连续调用会替换上一条提示。

弹窗内容已经由专用内容组件生成；`ModalController` 不拥有谈判业务状态。

## 6. 事件与 `data-action` 合约

`main.js` 使用文档级事件委托，通过 `closest('[data-action]')` 分发行为。局部重新渲染后无需重新绑定按钮事件。

| `data-action` | 行为 |
| --- | --- |
| `toggle-strategy` | 根据 `data-strategy-id` 选择或取消策略 |
| `end-turn` | 结算当前策略组合 |
| `show-report` | 打开最新战报 |
| `toggle-theme` | 切换明暗主题并保存偏好 |
| `restart` | 打开重新谈判确认框 |
| `end-negotiation` | 打开结束谈判确认框 |
| `back` | 打开返回大厅说明 |
| `show-event` | 标记事件已读并展示详情 |
| `show-tree` | 展示谈判树 |
| `show-opponent` | 展示对方态势研判 |
| `show-channel` | 展示非正式沟通 |
| `collapse-strategy` / `reopen-strategy` | 收起 / 恢复策略侧栏 |
| `collapse-situation` / `reopen-situation` | 收起 / 恢复态势侧栏 |
| `close-modal` | 关闭弹窗 |

新增交互按钮时，应同时提供稳定的 action 名称、可访问名称和协调器处理器；不要在组件内写内联 `onclick`。

## 7. 渲染与更新策略

- 首次加载：`NegotiationApp` 一次性渲染整个应用到 `#app`。
- 选牌 / 结算：仅替换 `#strategyCards` 和 `#handFooter`，避免重置右侧 `details` 的开合状态。
- 轮次 / 指标：分别更新 `#roundNumber` 和 `#metricList`。
- 新发言：使用 `Speech` 生成节点并追加到 `#dialogueScroll`，随后滚动到底部。
- 重置：恢复初始发言、策略、指标、轮次和事件徽标，但保留用户主题与侧栏开合偏好。
- 主题：通过 `<html data-theme="dark|light">` 切换，偏好键为 `localStorage['diplomat-theme']`。

## 8. 样式与设计令牌

`styles.css` 是组件类名和视觉样式的共享合约。重构组件时优先保留既有类名，避免复制样式或在组件中写内联视觉样式。

核心令牌：

- 背景与表面：`--bg`、`--bg-soft`、`--panel`、`--panel-solid`、`--card`、`--card-hover`。
- 文本：`--text`、`--text-soft`、`--muted`。
- 香槟金：`--gold`、`--gold-bright`、`--gold-dim`、`--gold-soft`。
- 边界：`--line`、`--line-strong`。
- 语义色：`--green`、`--red`、`--amber`、`--blue`、`--purple`。
- 阴影与发言表面：`--shadow`、`--speech-other`。

新增组件优先使用上述令牌，不新增近似色硬编码。业务状态类约定包括 `.selected`、`.recommended`、`.filled`、`.negative`、`.open`、`.show`、`.strategy-collapsed` 和 `.situation-collapsed`。

响应式约定：桌面为三栏；`≤ 900 px` 转为纵向布局并禁用侧栏折叠；`≤ 560 px` 策略卡和态势模块改为单列。`prefers-reduced-motion` 下关闭动画与平滑滚动。

## 9. 安全与可访问性

- 所有动态文本必须通过 `escapeHTML`；数值也应来自受控状态。
- `Speech({ html })`、`FoldSection({ content })` 和 `ModalController.open({ content })` 接收 HTML，只传入项目内可信模板或已完成转义的内容，禁止直接传入用户输入或远端未净化 HTML。
- 图标按钮必须具有 `aria-label`；选择卡通过 `aria-pressed` 暴露状态。
- 对话区域使用 `aria-live="polite"`；Toast 使用 `role="status"`。
- 弹窗使用 `role="dialog"`、`aria-modal="true"`，支持 Esc、背景关闭、焦点恢复与 Tab 圈定。
- 折叠模块使用原生 `details/summary`；键盘焦点具有明显轮廓。

## 10. 复用示例

### 在其他页面复用一张策略卡

```js
import { StrategyCard } from './components/index.js';
import { strategyCatalog } from './domain/negotiation.js';

container.innerHTML = StrategyCard({
  strategy: strategyCatalog[0],
  selected: false
});
```

父应用需要处理 `toggle-strategy`，并自行决定状态存储方式；卡片本身不会修改数据。

### 复用一条发言

```js
import { Speech } from './components/index.js';

messageList.insertAdjacentHTML('beforeend', Speech({
  party: 'cn',
  label: 'ROUND 02 · 策略出牌',
  text: '我方建议同步讨论配额与核查边界。'
}));
```

## 11. 扩展指南

### 新增一张策略卡

1. 在 `strategyCatalog` 添加稳定 id、成本、文案和效果说明。
2. 若影响指标，在 `NegotiationStore.endTurn()` 添加明确、可测试的结算规则；避免把业务规则写进按钮事件。
3. 复用 `StrategyCard`，确认行动点不足、取消选择、重置和战报文案均正确。
4. 如需新视觉类型，优先复用语义令牌，再补充最小样式。

### 新增一个态势模块

1. 准备纯文本数据或可信内容模板。
2. 使用 `FoldSection` 包装，并放入 `SituationPanel`。
3. 若有按钮，补充 `data-action` 和协调器处理器。
4. 验证局部更新不会重置模块开合状态，并检查窄屏布局。

### 新增一种弹窗

1. 在 `content.js` 新建纯内容组件，动态文本先转义。
2. 在协调器调用 `modal.open`，配置标题、内容和操作回调。
3. 业务状态变更通过仓库方法完成，并验证 Esc 与焦点恢复。

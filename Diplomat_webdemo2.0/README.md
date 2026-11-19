# Diplomat 2.0 · 外交谈判模拟器（webdemo 2.0）

多智能体外交谈判 Demo。三个谈判场（双边 / 多边 / 九方观战）跑在同一套 CountryAgent 引擎上。

## 启动

双击 **start.bat**，浏览器打开 <http://127.0.0.1:8010/>

（端口 8010，可与旧的 webdemo1.9（8002）同时运行）

## 页面结构

（以下页面均位于 `site/` 目录，由本地服务统一提供）

```
首页  site/index.html
 ├─ 学习模式  site/learn/index.html
 │    ├─ 第一关 lesson1.html      + notes.html
 │    ├─ 第二关 learning-level2.html + notes-level2.html
 │    └─ 第三关 learning-level3.html + notes-level3.html
 │         └─（右上角「学完了，去谈判 →」进入过渡页）
 ├─ 过渡页  site/select/start.html      双边
 │          site/select/start-1vn.html  多边
 │          site/select/start-watch.html 观战
 │    └─（确认后进入对局）
 ├─ 对局  site/duel.html / multi.html / observe.html
 │    └─（结束谈判 → 复盘）
 └─ 复盘  site/report/index.html   （读取 localStorage: neg-report / neg-v2-report）
```

## 与 Agent 引擎的接口

前端通过 `/api/v2/*` 与本地引擎通信：

| 接口 | 用途 |
|---|---|
| `POST /api/v2/session` | 开局（模式、议题、玩家、对手） |
| `GET  /api/v2/state` | 取最新视图（席位、手牌、阵营、情报账本） |
| `POST /api/v2/say` | 出牌 + 发言 |
| `POST /api/v2/deal` | 非正式沟通 |
| `POST /api/v2/intel` | 情报处置（放风/出售/揭穿） |
| `POST /api/v2/end` | 结束本局并返回复盘摘要 |
| `GET  /api/v2/meta` | 可用模式与议题 |

## 引擎文件

| 文件 | 作用 |
|---|---|
| `server_diplomat.py` | HTTP 服务 + v2 接口 |
| `server.py` | 旧版引擎核心（结算、手牌、事件卡） |
| `view_diplomat.py` | 视图构建（前端契约） |
| `diplomacy.py` / `bluff.py` / `deckgen.py` | 外交渠道、虚张声势、牌库生成 |
| `settlement.py` / `diplomacy_agent.py` | 结算与智能体 |
| `demo1.1/` | 各国 Agent 与提示词 |
| `knowledge/` | 议题知识库与事件卡 |

## 静态兜底

直接双击 HTML（file://）时无法连接引擎，页面会加载 `assets/sample-views.js` 里的快照样例并提示「静态预览 · 非实时」。

## 评审与设计材料

| 文件 | 内容 |
|---|---|
| `评委使用说明.md` | 启动方式、推荐评审路线、界面速查、常见问题、最小验收清单 |
| `智能体设计说明书_webdemo2.0.docx` | 智能体设计说明书（2.0 版，含架构、算法、接口与创新点） |
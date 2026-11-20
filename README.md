# Huawei

华为杯比赛共创仓库：协商推演 API（`api.py`）+ C 的规则引擎 + B 的场景编译器。

## 1. 环境要求

- Windows + Git Bash（命令以 Git Bash 为准）。
- Python 3.12 及以上；本机实测 `py -3` 为 **Python 3.15.0**，C 侧 218 条测试可全绿。
- 依赖见 `requirements.txt`（fastapi / uvicorn / pydantic / jsonschema / httpx / requests / pytest）。

## 2. 从零启动（离线模式，不需要 API Key）

在仓库根目录 `Huawei/` 执行：

```bash
py -3 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
NEG_OFFLINE=1 .venv/Scripts/python api.py
```

服务固定监听 `http://127.0.0.1:8765`。另开一个终端验证：

```bash
curl -s http://127.0.0.1:8765/
# {"status":"ok"}
```

`NEG_OFFLINE=1` 必须加在**启动服务的那条命令**上；不加且没有 Key 时，`api.detect_mode()` 也会自动降级为离线。可选 `NEG_SESSION_STORE_DIR=<目录>` 把会话落盘改到临时目录，避免污染 `runtime/sessions/`。

## 3. 在线模式与 Key 的位置

代码只读环境变量 `DEEPSEEK_API_KEY`，**不会自动读取 `key.txt`**。`key.txt` 在仓库的上一级目录（本机为 `D:\RainbowKATE\大学研究生时\华为杯\key.txt`），需要手工导出：

```bash
# Git Bash
export DEEPSEEK_API_KEY=$(cat ../key.txt)
# PowerShell
$env:DEEPSEEK_API_KEY = Get-Content ..\key.txt
```

未设置 Key 时，`/session` 仍可开局并进入离线模式；但离线 canned 对手的报价只覆盖默认 `ai_governance` 场景。切到 B 的芯片 / no-zopa / DST 场景时，离线对手会因条款名不匹配返回 `INVALID_ACTION / UNKNOWN_CLAUSE`，必须走在线模式（或使用测试里的 scripted opponent）。

## 4. 必演示场景的脚本化命令

所有写请求都必须带 `client_action_id`（或 `Idempotency-Key` 头）和 `base_version`，否则返回 `422 INVALID_REQUEST`。下面用 `.venv/Scripts/python` 从响应里取 `session_id`。

### 4.1 ai_governance：一手 + 3 步自动推演到终局（离线，无需 Key）

```bash
SID=$(curl -s -X POST http://127.0.0.1:8765/session \
  -H 'Content-Type: application/json' \
  -d '{"scenario_id":"ai_governance","agent":"us"}' \
  | .venv/Scripts/python -c "import sys,json;print(json.load(sys.stdin)['session_id'])")

curl -s -X POST http://127.0.0.1:8765/session/$SID/action \
  -H 'Content-Type: application/json' \
  -d '{
    "client_action_id": "demo-ai-1",
    "base_version": 0,
    "action_type": "offer",
    "card_id": null,
    "offer_patch": {
      "全球算力资源分配": {"option": "接受联合国框架下的技术性通报，但监督机制须具备实际约束力", "note": "给出可核查的对称安排。"},
      "前沿模型评测门槛": {"option": 55, "note": "维持场景初始门槛。"},
      "数据跨境流动": {"option": "在联合国框架下建立对称适用的数据跨境通报机制", "note": "以多边通报替代单边裁量。"}
    },
    "conditions": [],
    "expected_effect": "给出可讨论的具体方案，推动分歧收敛。",
    "public_message": "我方就相关条款提出具体方案，愿在相互尊重基础上继续磋商。"
  }'

for i in 1 2 3; do
  curl -s -X POST http://127.0.0.1:8765/session/$SID/auto_step
  echo
done

curl -s -X POST http://127.0.0.1:8765/session/$SID/debrief
```

实测：第 3 次 `auto_step` 返回 `status=ended`，`/auto_status` 的 `terminal_type=FULL_AGREEMENT`；`/debrief` 返回 `200 {"debrief","evaluation"}`。

### 4.2 main_chip_controls（B 芯片场景，需在线 Key）

```bash
SID=$(curl -s -X POST http://127.0.0.1:8765/session \
  -H 'Content-Type: application/json' \
  -d '{"scenario_id":"scn-chip-controls-0001","agent":"us","scenario_path":"scenario agent v2/data/scenarios/main_chip_controls.json"}' \
  | .venv/Scripts/python -c "import sys,json;print(json.load(sys.stdin)['session_id'])")

curl -s -X POST http://127.0.0.1:8765/session/$SID/action \
  -H 'Content-Type: application/json' \
  -d '{
    "client_action_id": "demo-chip-1",
    "base_version": 0,
    "action_type": "offer",
    "card_id": null,
    "offer_patch": {
      "芯片算力门槛": {"option": 1000, "note": "位于中方 800 以上、美方 1500 以下的安全区间。"},
      "许可审批时限": {"option": 75, "note": "位于美方 60 以上、中方 90 以下的安全区间。"},
      "第三国再出口限制": {"option": "O2", "note": "避开美方对 O1 的硬红线。"},
      "关键矿产出口安排": {"option": "O2", "note": "避开中方对 O3/O4 的硬红线。"}
    },
    "conditions": [],
    "expected_effect": "以可核查的交换条件推动四项条款收敛。",
    "public_message": "我方就四项条款提出具体方案，愿在相互尊重基础上继续磋商。"
  }'

for i in 1 2 3 4 5; do
  curl -s -X POST http://127.0.0.1:8765/session/$SID/auto_step
  echo
done
curl -s -X POST http://127.0.0.1:8765/session/$SID/debrief
```

脚本化回归里该场景第 5 步到达 `FULL_AGREEMENT`（见 `test_auto.py`）；在线演示时对手由模型生成，步数可能不同，以 `/auto_status` 的 `terminal_type` 为准。

### 4.3 no_zopa_variant（B 芯片场景变体，需在线 Key）

```bash
curl -s -X POST http://127.0.0.1:8765/session \
  -H 'Content-Type: application/json' \
  -d '{"scenario_id":"scn-chip-controls-nozopa-0001","agent":"us","scenario_path":"scenario agent v2/data/scenarios/no_zopa_variant.json"}'
```

拿到 `SID` 后，行动与 `4.2` 完全一致（同一组条款名），只是 `client_action_id` 换成 `demo-nozopa-1`。

### 4.4 backup_dst_bilateral（B 的 DST 双边场景，需在线 Key）

```bash
curl -s -X POST http://127.0.0.1:8765/session \
  -H 'Content-Type: application/json' \
  -d '{"scenario_id":"scn-dst-cn-us-0001","agent":"us","scenario_path":"scenario agent v2/data/scenarios/backup_dst_bilateral.json"}'
```

该场景条款为 `征税门槛` / `追溯适用期` / `加征关税去留` 等，第一条 offer 的 `offer_patch` 需按 `/session/{id}/state` 返回的 `clauses` 现取；不要直接复用芯片场景的条款名。

## 5. 测试三套

```bash
# 1) 仓库根：API / 契约 / 卡牌 / 分支 / 终局收口
py -3 -m pytest -q -p no:cacheprovider

# 2) C 的规则引擎（进入 C 目录）
cd "C 11.12 三指数" && py -3 -m pytest tests/ -q

# 3) B 的场景编译器（进入 B 目录；以 B 自己机器实测为准）
cd "scenario agent v2" && py -3 -m pytest -q
```

11/20 封板实测：根 **227 passed**、C **218 passed**、B **111 passed**。根与 C 任一红都不打 tag；B 侧如有红由 B 自己处理，A 不代修。

## 6. 场景覆盖层

`scenario_overrides.py` 在 `load_scenario` 之后统一补齐场景缺少的元数据：条款角色映射、我方每回合行动点（默认 4，子议题不少于 4 时为 5）和双方均无新版本才累计的僵局阈值（3 轮）。它只返回新字典，不修改 B 的场景 JSON，不改条款、选项或双方立场；B 已声明 `clause_roles` 时保留其原值。创建会话与存档恢复使用同一覆盖结果，投影中的 `available_cards[].target_clause` 也来自这份角色映射。

三个 B 场景的 `clause_roles` 注入：

- `scn-chip-controls-0001` / `scn-chip-controls-nozopa-0001`：condition=`第三国再出口限制`，performance=`许可审批时限`，exit=`关键矿产出口安排`；
- `scn-dst-cn-us-0001`：condition=`征税门槛`，performance=`追溯适用期`，exit=`加征关税去留`。

## 7. 隐私与 debrief

内部归档包含双方私有状态和行动 ID，只能用于候选事务与内部验收，不得写入 HTTP 响应或公开日志。服务重启后内存会话不会恢复（会话记录落盘在 `runtime/sessions/`，含行动账本与教练建议缓存）。

`/debrief` 是同步二态接口：终局后 `200 {"debrief", "evaluation"}`；未终局 `409 {"error": "DEBRIEF_NOT_AVAILABLE", "fail_reason": "谈判尚未结束，复盘暂不可用"}`，不存在 202 占位响应。终局后 `/action` 与 `/auto_step` 均返回 `409 ROUND_LOCKED`（`engine_error=PHASE_CLOSED`），不会继续推进。

评分字段：`GET /state` 的 `speaker_score` 与 `/debrief` 的 `evaluation.learning_performance` 同源，均为 A 侧规则启发式（`source="rule"`）；未评分时整块为 `null`，不是 0。开关见 `api.py` 的 `SPEAKER_SCORE_MODE`（`rule` / `passthrough` / `off`），默认 `rule`。

## 8. 队友交付物

- `C 11.12 三指数/`：C 的规则引擎源码交付（本分支已合入 `feat/rules-c` 的 218 条测试版本）。更新流程：C 群里发新版 → 整体覆盖该目录 → 单独 commit。C 的测试须在其自身目录下运行 `py -3 -m pytest tests/ -q`。
- `scenario agent v2/`：B 的场景编译器交付。api.py 只用其中 `docs/contracts/`（场景契约）和 `data/scenarios/`（场景文件）。

两个目录内的 `__pycache__/`、`.pyc` 等由嵌套 .gitignore 忽略，不入库；仓库根 pytest 通过 `conftest.py` 排除对这两个目录的收集。
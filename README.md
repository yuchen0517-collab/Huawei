# Huawei

华为杯比赛共创仓库

## 队友交付物

本仓库已收录以下队友交付物，克隆即可运行，无需另行取得：

- `C 11.12 三指数/`：C 的规则引擎源码交付（11/13 版本，自带 79 条 pytest）。更新流程：C 群里发新版 → 整体覆盖该目录 → 单独 commit。C 的测试须在其自身目录下运行 `python -m pytest tests/ -q`。
- `scenario agent v2/`：B 的场景编译器交付（11/13 改名自 Diplomat_webdemo2.0，内部结构不变）。api.py 目前只用其中 `docs/contracts/`（场景契约）和 `data/scenarios/`（场景文件，如 `main_chip_controls.json`）。

两个目录内的 `__pycache__/`、`.pyc` 等由嵌套 .gitignore 忽略，不入库；仓库根 pytest 通过 conftest.py 排除对这两个目录的收集。

## 规则引擎临时接入

当前规则引擎由队友 C 单独交付，运行依赖位于 `C 11.12 三指数/`。该目录与 `scenario agent v2/` 已收录进本仓库（见「队友交付物」），克隆即可运行。

只支持 CPython 3.12。本机验收固定使用：

```text
D:\KimiData\daimon-share\daimon\runtime\python\.venv\Scripts\python.exe
```

默认 Python 3.15 下的引擎导入失败不属于本次验收结果。以下命令均在仓库根目录的 Git Bash 中执行：

```bash
PY="D:/KimiData/daimon-share/daimon/runtime/python/.venv/Scripts/python.exe"
"$PY" -m pip install -r requirements.txt
```

### 准备字节码

当前交付只有 `engine/__pycache__/*.cpython-312.pyc`。将 6 个引擎文件复制到上一级并去掉 `.cpython-312`，保留原始缓存：

```bash
for src in "C 11.12 三指数/engine/__pycache__/"*.cpython-312.pyc; do
  name=$(basename "$src" .cpython-312.pyc)
  cp -n -- "$src" "C 11.12 三指数/engine/${name}.pyc"
done
```

不要复制或修改 `agent/audit/`。临时场景由根目录 `load_scenario.py` 构造，目前只承诺 `ai_governance + us`；其他对手国家返回 `INVALID_AGENT`。

### 启动和验收

启动离线 API，监听 `127.0.0.1:8765`：

```bash
NEG_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 "$PY" api.py
```

在另一个终端运行自动化测试和真实 HTTP 验收：

```bash
NEG_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest test_api.py test_engine_flow.py -q
NEG_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 "$PY" manual_api_check.py
```

CLI 保护性自检：

```bash
PYTHONDONTWRITEBYTECODE=1 "$PY" neg_cli.py --check
NEG_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 "$PY" neg_cli.py --offline
```

`test_engine_flow.py` 直接对 `RulesEngine` 执行五步 FLOW，并逐步检查接受结果、终局评估、快照和指数回放；HTTP 链路单独验收，避免自动对手回应引入第六步。C 自带的 5 个 unittest 仍等待正式 `scenarios/demo_scenario.json`，当前记为 `BLOCKED/NOT_RUN`，不计入通过率。

### 正式交付替换

1. 取得 C 的引擎源码、接口说明、17 项错误定义和正式场景文件。
2. 用正式源码替代临时字节码，并将 API 的场景入口从 `make_scenario()` 切换到 `load_scenario(正式场景路径)`；显式加载失败不得回退到临时场景。
3. 使用同一 Python 3.12 环境重跑 API、FLOW、CLI 和 C 的 5 个 unittest，核对公开状态、错误原码、终局和隐私结果。
4. 等价回归通过并确认唯一真源后，再删除 `engine/` 上一级的 6 个临时 `.pyc`；临时 `load_scenario.py` 的归档或删除另行确认。

内部归档包含双方私有状态和行动 ID，只能用于候选事务与内部验收，不得写入 HTTP 响应或公开日志。服务重启后内存会话不会恢复，`/debrief` 仍是 202 占位接口。

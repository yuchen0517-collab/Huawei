"""兼容壳：B→C 场景转换的唯一实现已迁至成员C 的
`C 11.12 三指数/load_scenario_bridge.py`（内部委托 `adapter/scenario_adapter.py`）。

本模块不含任何转换逻辑，只做路径引导与再导出，供仓库根目录下的
test_api.py / test_e2e.py / test_isolation.py / test_engine_flow.py 等
既有调用方继续以 `from load_scenario import ...` 的方式使用。

背景：旧的 convert_b_scenario() 与 C 的适配层重复且存在实质缺陷
（枚举效用分忽略 goals[].target、无红线时回填 ideal 导致红线失效等），
已于 2026-11-14 按成员C 的建议废弃，改为全项目单一路径。
"""

from __future__ import annotations

import sys
from pathlib import Path

_ENGINE_DIR = Path(__file__).resolve().parent / "C 11.12 三指数"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from load_scenario_bridge import (  # noqa: F401
    CLAUSE_NAMES,
    ENGINE_ROOT,
    SCENARIO_ID,
    convert_b_scenario,
    get_last_warnings,
    is_b_scenario,
    load_scenario,
    make_scenario,
)

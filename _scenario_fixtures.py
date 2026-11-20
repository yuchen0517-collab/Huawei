"""测试用的场景常量与建会话请求体。

产品默认场景已切到芯片（`api.DEFAULT_SCENARIO_PATH`）。旧的 `ai_governance`
题材不再由产品提供：它没有对应的场景文件，条款也不在任何交付场景里。

但仓库里大量契约回归（幂等、fork、教练建议、行动点粒度、发言评分）是按它的
「3 条款（2 枚举 + 1 数值）」形状写的。为了让这些回归继续守住契约本身，
把当时由 `make_scenario()` 生成的引擎场景**冻结**成
`fixtures/legacy_ai_governance.json` —— 它只是测试夹具，不是可演示场景。

新增测试请直接用芯片场景（`chip_body()`）；只有明确在测「3 条款形状」的
历史用例才用 `legacy_body()`。
"""
from __future__ import annotations

import copy
from pathlib import Path

_FIXTURES = Path(__file__).resolve().parent / "fixtures"

LEGACY_ID = "ai_governance"
LEGACY_PATH = str(_FIXTURES / "legacy_ai_governance.json")
LEGACY_CLAUSES = ("全球算力资源分配", "前沿模型评测门槛", "数据跨境流动")

CHIP_ID = "scn-chip-controls-0001"
CHIP_PATH = str(
    Path(__file__).resolve().parent
    / "scenario agent v2"
    / "data"
    / "scenarios"
    / "main_chip_controls.json"
)
CHIP_CLAUSES = ("芯片算力门槛", "第三国再出口限制", "关键矿产出口安排", "协议退出与救济安排")


def legacy_body() -> dict:
    return {"scenario_id": LEGACY_ID, "agent": "us", "scenario_path": LEGACY_PATH}


def chip_body() -> dict:
    return {"scenario_id": CHIP_ID, "agent": "us", "scenario_path": CHIP_PATH}


def chip_offer_patch() -> dict:
    """一份对芯片场景合法、且不触双方红线的报价：算力 1000 + 三个枚举取 O2。"""
    return {
        "芯片算力门槛": {"option": 1000, "note": "位于中方 800 以上、美方 1500 以下的安全区间。"},
        "第三国再出口限制": {"option": "O2", "note": "避开美方对 O1 的硬红线。"},
        "关键矿产出口安排": {"option": "O2", "note": "避开中方对 O3/O4 的硬红线。"},
        "协议退出与救济安排": {"option": "O2", "note": "双方都可接受的协商延长履约期。"},
    }


def copy_patch(patch: dict) -> dict:
    return copy.deepcopy(patch)

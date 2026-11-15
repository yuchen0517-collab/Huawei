"""外交谈判规则引擎。

对外暴露 RulesEngine / load_scenario / TERMINAL_TYPES / TERMINAL_LABELS，
以及复盘闸门异常 IllegalDebriefAccess。
"""

from .core import IllegalDebriefAccess, RulesEngine, load_scenario
from .terminal import TERMINAL_LABELS, TERMINAL_TYPES

__all__ = [
    "RulesEngine",
    "IllegalDebriefAccess",
    "load_scenario",
    "TERMINAL_TYPES",
    "TERMINAL_LABELS",
]
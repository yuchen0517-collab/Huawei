"""外交谈判规则引擎。

只对外暴露 RulesEngine / load_scenario / TERMINAL_TYPES / TERMINAL_LABELS。
"""

from .core import RulesEngine, load_scenario
from .terminal import TERMINAL_LABELS, TERMINAL_TYPES

__all__ = [
    "RulesEngine",
    "load_scenario",
    "TERMINAL_TYPES",
    "TERMINAL_LABELS",
]
"""场景契约适配层：把成员B 的场景契约翻译成成员C 引擎可直接加载的格式。"""

from .scenario_adapter import (
    ScenarioContractError,
    adapt_scenario,
    adapt_scenario_with_warnings,
    load_and_adapt,
    validate_b_contract,
)

__all__ = [
    "ScenarioContractError",
    "adapt_scenario",
    "adapt_scenario_with_warnings",
    "load_and_adapt",
    "validate_b_contract",
]
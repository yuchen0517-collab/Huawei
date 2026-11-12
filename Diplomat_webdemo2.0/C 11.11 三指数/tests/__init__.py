"""测试包公共工具。"""

import json
import os

from engine import RulesEngine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIO_PATH = os.path.join(ROOT, "scenarios", "demo_scenario.json")


def load_demo() -> dict:
    with open(SCENARIO_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def make_scenario(**overrides) -> dict:
    data = load_demo()
    data.update(overrides)
    return data


def make_engine(**overrides) -> RulesEngine:
    return RulesEngine(make_scenario(**overrides), session_id="test-session")


def normalize_patch(patch) -> dict:
    result = {}
    for name, value in (patch or {}).items():
        if isinstance(value, dict):
            result[name] = {
                "option": value["option"],
                "note": value.get("note", "测试"),
            }
        else:
            result[name] = {"option": value, "note": "测试"}
    return result


def make_action(
    action_id="a1",
    actor="cn",
    action_type="offer",
    patch=None,
    conditions=None,
    labels=None,
    card_id=None,
) -> dict:
    action = {
        "action_id": action_id,
        "actor": actor,
        "action_type": action_type,
        "card_id": card_id,
        "offer_patch": normalize_patch(patch),
        "conditions": list(conditions) if conditions is not None else [],
        "expected_effect": "测试用行动",
        "public_message": "测试用发言。",
    }
    if labels is not None:
        action["effect_labels"] = labels
    return action


def submit(
    engine,
    action_id="a1",
    actor="cn",
    action_type="offer",
    patch=None,
    conditions=None,
    labels=None,
):
    return engine.submit_action(
        make_action(action_id, actor, action_type, patch, conditions, labels)
    )


FLOW = (
    {
        "action_id": "flow-1",
        "actor": "cn",
        "action_type": "offer",
        "patch": {"全球算力资源分配": "附带可核查机制"},
        "labels": [{"label": "constructive_proposal", "magnitude": "moderate"}],
    },
    {
        "action_id": "flow-2",
        "actor": "us",
        "action_type": "counter_offer",
        "patch": {"前沿模型评测门槛": 50},
    },
    {
        "action_id": "flow-3",
        "actor": "cn",
        "action_type": "final_offer",
        "patch": {"数据跨境流动": "白名单互认"},
    },
    {
        "action_id": "flow-4",
        "actor": "us",
        "action_type": "counter_offer",
        "patch": {"前沿模型评测门槛": 45},
    },
    {"action_id": "flow-5", "actor": "cn", "action_type": "accept"},
)


def full_flow(engine):
    return [submit(engine, **step) for step in FLOW]


def full_engine() -> RulesEngine:
    engine = make_engine(action_points_per_round=6)
    full_flow(engine)
    return engine
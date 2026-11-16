"""行动契约 v2 的校验测试。

用真实引擎（C 侧 engine/ + load_scenario_bridge）构造状态，确保
negotiation_rules 判定与引擎的有效性判定不冲突。
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE_DIR = ROOT / "C 11.12 三指数"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from engine.core import RulesEngine  # noqa: E402
from load_scenario_bridge import load_scenario  # noqa: E402

import negotiation_rules as rules  # noqa: E402

REGISTRY = rules.load_registry()
COUNTER = 0


def make_engine(ap: int = 8) -> RulesEngine:
    scenario = copy.deepcopy(load_scenario())
    scenario["action_points_per_round"] = ap
    scenario["deadlock_rounds"] = 99
    scenario["max_rounds"] = 50
    return RulesEngine(scenario)


def action(
    actor: str,
    action_type: str,
    patch: dict | None = None,
    card_id: str | None = None,
    payload: dict | None = None,
) -> dict:
    global COUNTER
    COUNTER += 1
    item = {
        "action_id": f"t-{COUNTER:04d}",
        "actor": actor,
        "action_type": action_type,
        "card_id": card_id,
        "offer_patch": patch or {},
        "conditions": [],
        "expected_effect": "test",
        "public_message": "test",
    }
    if payload is not None:
        item["card_payload"] = payload
    return item


def _candidate_patches(scenario: dict):
    for clause in scenario.get("clauses", []):
        if clause.get("type") == "numeric":
            low, high = clause.get("range", [0, 0])
            for value in (low, (low + high) // 2, high):
                yield {clause["name"]: {"option": value, "note": "t"}}
        else:
            for option in clause.get("options", []):
                yield {clause["name"]: {"option": option["id"], "note": "t"}}


def pick_legal_patch(engine: RulesEngine, actor: str, action_type: str = "offer") -> dict:
    """从场景里挑一个引擎认为合法的条款变更（含红线校验）。"""
    for patch in _candidate_patches(engine.scenario):
        trial = copy.deepcopy(engine)
        ok, _code, _msg, _events = trial.submit_action(action(actor, action_type, patch))
        if ok:
            return patch
    raise AssertionError("场景里找不到合法条款变更")


def submit(engine: RulesEngine, item: dict) -> None:
    """先把 card_payload 摘掉（引擎不认识该字段），再提交。"""
    payload = dict(item)
    payload.pop("card_payload", None)
    ok, code, msg, _events = engine.submit_action(payload)
    assert ok, f"引擎拒绝了 {item['action_type']}: {code} {msg}"


def check(engine: RulesEngine, item: dict):
    return rules.check_card_action(item, engine.state, engine.scenario, REGISTRY)


# ----------------------------------------------------------------------
# 报价板法则
# ----------------------------------------------------------------------
def test_offer_without_patch_is_empty_turn():
    engine = make_engine()
    ok, code, _ = check(engine, action("cn", "offer"))
    assert not ok and code == "EMPTY_TURN"


def test_quote_board_card_requires_patch():
    engine = make_engine()
    ok, code, _ = check(engine, action("cn", "offer", card_id="anchor_offer"))
    assert not ok and code == "CARD_REQUIRES_QUOTE_BOARD"

    patch = pick_legal_patch(engine, "cn")
    ok, code, _ = check(engine, action("cn", "offer", patch, card_id="anchor_offer"))
    assert ok, code


def test_non_quote_card_forbids_patch():
    engine = make_engine()
    patch = pick_legal_patch(engine, "cn")
    ok, code, _ = check(
        engine,
        action("cn", "probe", patch, card_id="probe_priority",
               payload={"target": "us"}),
    )
    assert not ok and code == "CARD_FORBIDS_QUOTE_BOARD"


def test_card_action_mismatch():
    engine = make_engine()
    patch = pick_legal_patch(engine, "cn")
    ok, code, _ = check(
        engine, action("cn", "offer", patch, card_id="final_offer")
    )
    assert not ok and code == "CARD_ACTION_MISMATCH"


def test_unknown_card():
    engine = make_engine()
    patch = pick_legal_patch(engine, "cn")
    ok, code, _ = check(engine, action("cn", "offer", patch, card_id="nope"))
    assert not ok and code == "CARD_UNKNOWN"


# ----------------------------------------------------------------------
# 载荷
# ----------------------------------------------------------------------
def test_probe_requires_target():
    engine = make_engine()
    ok, code, _ = check(engine, action("cn", "probe", card_id="probe_priority"))
    assert not ok and code == "CARD_PAYLOAD_MISSING"

    ok, code, _ = check(
        engine,
        action("cn", "probe", card_id="probe_priority", payload={"target": "us"}),
    )
    assert ok, code


def test_probe_rejects_unknown_payload_field():
    engine = make_engine()
    ok, code, _ = check(
        engine,
        action(
            "cn", "probe", card_id="probe_priority",
            payload={"target": "us", "bribe": 1},
        ),
    )
    assert not ok and code == "CARD_PAYLOAD_INVALID"


def test_probe_rejects_foreign_target():
    engine = make_engine()
    ok, code, _ = check(
        engine,
        action("cn", "probe", card_id="probe_priority", payload={"target": "ru"}),
    )
    assert not ok and code == "CARD_PAYLOAD_INVALID"


def test_clause_role_requires_target_clause():
    engine = make_engine()
    patch = pick_legal_patch(engine, "cn")
    role_clause = next(
        clause for clause in engine.scenario["clauses"] if clause["name"] not in patch
    )
    engine.scenario["clause_roles"] = {"condition": role_clause["name"]}

    ok, code, _ = check(
        engine, action("cn", "offer", patch, card_id="effective_condition")
    )
    assert not ok and code == "CARD_PAYLOAD_INVALID"

    if role_clause.get("type") == "numeric":
        low, high = role_clause.get("range", [0, 0])
        value = (low + high) // 2
    else:
        value = role_clause["options"][0]["id"]
    patch[role_clause["name"]] = {"option": value, "note": "t"}
    ok, code, _ = check(
        engine, action("cn", "offer", patch, card_id="effective_condition")
    )
    assert ok, code


# ----------------------------------------------------------------------
# 冷却与限次
# ----------------------------------------------------------------------
def test_cooldown_blocks_following_rounds():
    engine = make_engine()
    card = "demand_basis"
    item = action("cn", "probe", card_id=card, payload={"target": "us"})
    assert check(engine, item)[0]
    submit(engine, item)

    engine.next_round()  # 第 2 回合
    ok, code, _ = check(engine, action("cn", "probe", card_id=card, payload={"target": "us"}))
    assert not ok and code == "CARD_COOLING"

    engine.next_round()  # 第 3 回合
    engine.next_round()  # 第 4 回合
    ok, code, _ = check(engine, action("cn", "probe", card_id=card, payload={"target": "us"}))
    assert ok, code


def test_uses_per_game():
    engine = make_engine()
    patch = pick_legal_patch(engine, "cn")
    item = action("cn", "final_offer", patch, card_id="final_offer")
    assert check(engine, item)[0]
    submit(engine, item)

    ok, code, _ = check(engine, action("cn", "final_offer", patch, card_id="final_offer"))
    assert not ok and code == "CARD_EXHAUSTED"


# ----------------------------------------------------------------------
# 响应闭包
# ----------------------------------------------------------------------
def test_deferral_limit_is_one():
    engine = make_engine()
    patch = pick_legal_patch(engine, "cn")
    submit(engine, action("cn", "offer", patch))

    first = action("us", "probe", card_id="probe_priority", payload={"target": "cn"})
    assert check(engine, first)[0]
    submit(engine, first)

    second = action("us", "probe", card_id="verify_capacity", payload={"target": "cn"})
    ok, code, _ = check(engine, second)
    assert not ok and code == "PENDING_RESPONSE_EXCEEDED"


def test_resolving_always_allowed():
    engine = make_engine()
    patch = pick_legal_patch(engine, "cn")
    submit(engine, action("cn", "offer", patch))
    submit(engine, action("us", "probe", card_id="probe_priority", payload={"target": "cn"}))

    counter = action("us", "counter_offer", patch)
    assert check(engine, counter)[0]
    submit(engine, counter)


def test_self_revision_locked():
    engine = make_engine()
    patch = pick_legal_patch(engine, "cn")
    submit(engine, action("cn", "offer", patch))

    ok, code, _ = check(engine, action("cn", "offer", patch))
    assert not ok and code == "SELF_REVISION_LOCKED"


def test_repeat_hold_forbidden():
    engine = make_engine()
    patch = pick_legal_patch(engine, "cn")
    submit(engine, action("cn", "offer", patch))

    hold = action("us", "reject")
    assert check(engine, hold)[0]
    submit(engine, hold)

    ok, code, _ = check(engine, action("us", "reject"))
    assert not ok and code == "REPEAT_HOLD_FORBIDDEN"


def test_statement_needs_card():
    engine = make_engine()
    ok, code, _ = check(engine, action("cn", "statement"))
    assert not ok and code == "EMPTY_TURN"

    ok, code, _ = check(
        engine,
        action("cn", "statement", card_id="public_commitment",
               payload={"text": "我方承诺不首先使用出口管制。"}),
    )
    assert ok, code


# ----------------------------------------------------------------------
# 与引擎的一致性
# ----------------------------------------------------------------------
def test_legal_flow_passes_checker_and_engine():
    engine = make_engine()
    patch = pick_legal_patch(engine, "cn")
    flow = [
        action("cn", "offer", patch, card_id="anchor_offer"),
        action("us", "probe", card_id="probe_priority", payload={"target": "cn"}),
        action("us", "counter_offer", patch),
        action("cn", "probe", card_id="demand_basis", payload={"target": "us"}),
    ]
    for item in flow:
        ok, code, msg = check(engine, item)
        assert ok, f"{item['action_type']} 被契约层拒绝：{code} {msg}"
        submit(engine, item)


def test_pending_hint_explains_state():
    engine = make_engine()
    patch = pick_legal_patch(engine, "cn")
    submit(engine, action("cn", "offer", patch))
    submit(engine, action("us", "probe", card_id="probe_priority", payload={"target": "cn"}))

    hint = rules.pending_hint(engine.state, engine.scenario, REGISTRY)
    assert hint["responder"] == "us"
    assert hint["deferrals_used"] == 1
    assert hint["deferrals_left"] == 0
    assert hint["must_resolve"] is True


def test_available_cards_marks_cooldown():
    engine = make_engine()
    item = action("cn", "probe", card_id="probe_priority", payload={"target": "us"})
    submit(engine, item)
    engine.next_round()

    table = {row["id"]: row for row in rules.available_cards("cn", engine.state, REGISTRY)}
    assert table["probe_priority"]["available"] is False
    assert "冷却" in table["probe_priority"]["reason"]
    assert table["probe_priority"]["quote_board"] is False
    assert table["anchor_offer"]["quote_board"] is True

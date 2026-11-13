import copy
import importlib.util
import json
import sys
from pathlib import Path

from load_scenario import make_scenario

BASE_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = BASE_DIR / "C 11.12 三指数"
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from engine.core import RulesEngine
from engine.state import NegotiationState, Offer

HELPER_PATH = ENGINE_ROOT / "tests" / "__pycache__" / "__init__.cpython-312.pyc"
SPEC = importlib.util.spec_from_file_location("c_flow_fixtures", HELPER_PATH)
HELPERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPERS)


def flow_action(step):
    return {
        "action_id": step["action_id"],
        "actor": step["actor"],
        "action_type": step["action_type"],
        "card_id": None,
        "offer_patch": {
            name: {"option": option, "note": "FLOW 验证"}
            for name, option in step.get("patch", {}).items()
        },
        "conditions": [],
        "expected_effect": "FLOW 验证",
        "public_message": f"{step['actor']} 执行 {step['action_type']}。",
    }


def restore(engine):
    archive = copy.deepcopy(engine.state.to_archive_dict())
    archive["offers"] = [Offer(**offer) for offer in archive["offers"]]
    archive["agreement"] = Offer(**archive["agreement"]) if archive["agreement"] else None
    candidate = RulesEngine(copy.deepcopy(engine.scenario), engine.session_id)
    candidate.state = NegotiationState(**archive)
    return candidate


def test_flow_five_steps_reach_terminal_without_effect_labels(tmp_path):
    engine = RulesEngine(make_scenario(), "flow-test")
    assert len(HELPERS.FLOW) == 5
    submitted = []
    for step in HELPERS.FLOW:
        action = flow_action(step)
        assert "effect_labels" not in action
        assert set(action) == {
            "action_id", "actor", "action_type", "card_id", "offer_patch",
            "conditions", "expected_effect", "public_message",
        }
        ok, code, detail, _ = engine.submit_action(action)
        assert ok, (step["action_id"], code, detail)
        submitted.append(step["action_id"])
    assert submitted == ["flow-1", "flow-2", "flow-3", "flow-4", "flow-5"]
    public = engine.public_state("cn")
    action_events = [event for event in public["public_events"] if event.get("type") == "action"]
    assert [event["action_id"] for event in action_events] == submitted
    assert public["status"] == "ended"
    assert public["open_issues"] == []
    assert all(item["label_mode"] == "fallback" for item in engine.state.behavior_log)
    terminal = engine.finish()
    assert terminal["type"] == "FULL_AGREEMENT"
    evaluation = engine.evaluate()
    assert evaluation["terminal_type"] == "FULL_AGREEMENT"
    assert evaluation["agreement_quality"]["coverage"] == 1.0
    replay = engine.replay()
    assert replay["consistent"] is True
    snapshot = tmp_path / "flow_snapshot.json"
    engine.dump(str(snapshot))
    archived = json.loads(snapshot.read_text(encoding="utf-8"))
    assert archived["session_id"] == "flow-test"
    assert archived["status"] == "ended"


def test_archive_restore_is_independent_and_can_replay_remaining_flow():
    engine = RulesEngine(make_scenario(), "flow-restore-test")
    first = flow_action(HELPERS.FLOW[0])
    ok, code, detail, _ = engine.submit_action(first)
    assert ok, (code, detail)
    original_archive = copy.deepcopy(engine.state.to_archive_dict())
    candidate = restore(engine)
    assert candidate.state.to_archive_dict() == original_archive
    for step in HELPERS.FLOW[1:]:
        ok, code, detail, _ = candidate.submit_action(flow_action(step))
        assert ok, (step["action_id"], code, detail)
    assert engine.state.to_archive_dict() == original_archive
    assert candidate.public_state("cn")["status"] == "ended"
    assert candidate.replay()["consistent"] is True
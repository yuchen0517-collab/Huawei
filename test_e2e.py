import json
import sys
from pathlib import Path

from load_scenario import ENGINE_ROOT, load_scenario, make_scenario

if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from engine.core import RulesEngine
from engine.terminal import TERMINAL_TYPES

BASE_DIR = Path(__file__).resolve().parent
CHIP_SCENARIO_PATH = (
    # B 最新交付已从 feat/scenario-b 收编进仓库（11/13），仓库自包含
    BASE_DIR / "scenario agent v2" / "data" / "scenarios" / "main_chip_controls.json"
)

CLAUSE_COMPUTE = "芯片算力门槛"
CLAUSE_DAYS = "许可审批时限"
CLAUSE_REEXPORT = "第三国再出口限制"
CLAUSE_MINERALS = "关键矿产出口安排"
REEXPORT_O2 = "仅对实体清单对象要求许可"
REEXPORT_O3 = "第三国再出口一律事前许可"
MINERALS_O2 = "对民用终端设 30 天快速通道"


def make_action(action_id, actor, action_type, patch=None, message=""):
    return {
        "action_id": action_id,
        "actor": actor,
        "action_type": action_type,
        "card_id": None,
        "offer_patch": {
            name: {"option": option, "note": "e2e 离线验证"}
            for name, option in (patch or {}).items()
        },
        "conditions": [],
        "expected_effect": "e2e 离线整局验证",
        "public_message": message or f"{actor} 执行 {action_type}。",
    }


def run_steps(engine, steps):
    for step in steps:
        if engine.state.status == "ended":
            break
        if step is None:
            info = engine.next_round()
            print(f"  -- 进入第 {info['round']} 轮 phase={info['phase']}")
            continue
        ok, code, detail, events = engine.submit_action(step)
        assert ok, (step["action_id"], code, detail)
        version = events[0]["version"]
        print(
            f"  R{engine.state.round} {step['actor']} {step['action_type']}"
            f" v{version} | {step['public_message']}"
        )
    assert engine.state.status == "ended", "剧本结束后仍未到达终局"


def print_report(engine):
    state = engine.state
    print("  [协议版本记录]")
    for offer in state.offers:
        clauses = {name: entry["option"] for name, entry in offer.clauses.items()}
        print(
            f"    v{offer.version} R{offer.created_round} {offer.actor} {offer.kind}"
            f" {json.dumps(clauses, ensure_ascii=False)}"
        )
    if state.agreement is not None:
        print(
            f"    协议 v{state.agreement.version} 由 {state.agreement.actor} 接受，"
            f"覆盖 {len(state.agreement.clauses)} 项条款"
        )
    else:
        print("    未达成协议")
    evaluation = engine.evaluate()
    assert evaluation["terminal_type"] in TERMINAL_TYPES
    print(
        f"  [终局类型] {evaluation['terminal_type']}"
        f"（{state.terminal['label']}，第 {state.terminal['round']} 轮）"
    )
    print(f"  [协议质量] {json.dumps(evaluation['agreement_quality'], ensure_ascii=False)}")
    print(f"  [红线检查] {json.dumps(evaluation['redline_check'], ensure_ascii=False)}")
    print(f"  [BATNA 对比] {json.dumps(evaluation['batna_comparison'], ensure_ascii=False)}")
    return evaluation


def assert_no_redline_violation(evaluation):
    assert all(
        not violated
        for clause in evaluation["redline_check"].values()
        for violated in clause.values()
    ), evaluation["redline_check"]


def test_minimal_scenario_full_agreement():
    print("\n===== 局 1：默认最小场景（make_scenario）离线整局 =====")
    engine = RulesEngine(make_scenario(), "e2e-minimal")
    steps = [
        make_action("e1-1", "cn", "offer", {
            "全球算力资源分配": "附带可核查机制",
            "前沿模型评测门槛": 60,
        }, "中方首轮报价：算力附带可核查机制，评测门槛 60。"),
        make_action("e1-2", "us", "counter_offer", {
            "前沿模型评测门槛": 40,
        }, "美方反报价：评测门槛压到 40。"),
        None,
        make_action("e1-3", "cn", "counter_offer", {
            "前沿模型评测门槛": 40,
            "数据跨境流动": "白名单互认",
        }, "中方第二轮接受门槛 40，并提出数据白名单互认。"),
        make_action("e1-4", "us", "counter_offer", {
            "全球算力资源分配": "附带可核查机制",
            "数据跨境流动": "白名单互认",
        }, "美方对齐算力与数据条款。"),
        make_action("e1-5", "cn", "accept", None, "双方取值已一致，中方接受协议。"),
    ]
    run_steps(engine, steps)
    evaluation = print_report(engine)
    assert evaluation["terminal_type"] == "FULL_AGREEMENT"
    assert evaluation["agreement_quality"]["coverage"] == 1.0
    assert_no_redline_violation(evaluation)
    assert engine.replay()["consistent"] is True


def test_chip_scenario_full_agreement():
    print("\n===== 局 2：B 芯片场景（load_scenario 转换）离线整局 =====")
    scenario = load_scenario(CHIP_SCENARIO_PATH)
    assert scenario["scenario_id"] == "scn-chip-controls-0001"
    assert [clause["type"] for clause in scenario["clauses"]] == [
        "numeric", "numeric", "enum", "enum",
    ]
    assert scenario["index_rules"]["initial"]["cn"] == {"image": 60, "trust": 45}
    compute = next(c for c in scenario["clauses"] if c["name"] == CLAUSE_COMPUTE)
    assert compute["range"] == [100, 5000]
    assert compute["unit"] == "TFLOPS(FP16)"
    assert compute["weights"] == {"cn": 0.35, "us": 0.25}
    assert compute["positions"]["cn"] == {"ideal": 1500, "redline": 800}
    reexport = next(c for c in scenario["clauses"] if c["name"] == CLAUSE_REEXPORT)
    assert reexport["options"][0]["score"] == {"cn": 1.0, "us": 0.25}
    assert reexport["redlines"]["us"] == ["仅需终端用户声明"]
    assert reexport["redlines"]["cn"] == []
    minerals = next(c for c in scenario["clauses"] if c["name"] == CLAUSE_MINERALS)
    assert minerals["redlines"]["cn"] == ["设年度配额并接受第三方核查", "取消出口许可"]
    engine = RulesEngine(scenario, "e2e-chip")
    steps = [
        make_action("e2-1", "cn", "offer", {
            CLAUSE_COMPUTE: 1200, CLAUSE_DAYS: 75,
        }, "中方报价：门槛 1200 TFLOPS，审批 75 天。"),
        make_action("e2-2", "us", "counter_offer", {
            CLAUSE_COMPUTE: 1000, CLAUSE_REEXPORT: REEXPORT_O3,
        }, "美方反报价：门槛 1000，第三国转口一律事前许可。"),
        None,
        make_action("e2-3", "cn", "counter_offer", {
            CLAUSE_COMPUTE: 1200, CLAUSE_REEXPORT: REEXPORT_O2, CLAUSE_MINERALS: MINERALS_O2,
        }, "中方让步：转口限实体清单对象，矿产设民用快速通道。"),
        make_action("e2-4", "us", "counter_offer", {
            CLAUSE_COMPUTE: 1200, CLAUSE_DAYS: 75,
            CLAUSE_REEXPORT: REEXPORT_O2, CLAUSE_MINERALS: MINERALS_O2,
        }, "美方全面对齐中方方案。"),
        make_action("e2-5", "us", "accept", None, "美方接受协议。"),
    ]
    run_steps(engine, steps)
    evaluation = print_report(engine)
    assert evaluation["terminal_type"] == "FULL_AGREEMENT"
    assert evaluation["agreement_quality"]["coverage"] == 1.0
    assert_no_redline_violation(evaluation)
    batna = evaluation["batna_comparison"]
    assert batna["cn"]["batna"] == 40
    assert batna["us"]["batna"] == 35
    assert engine.replay()["consistent"] is True


def test_chip_scenario_withdrawal():
    print("\n===== 局 3：B 芯片场景 walk_away 退出 =====")
    scenario = load_scenario(CHIP_SCENARIO_PATH)
    engine = RulesEngine(scenario, "e2e-chip-withdrawal")
    steps = [
        make_action("e3-1", "cn", "offer", {CLAUSE_COMPUTE: 1200}, "中方报价门槛 1200。"),
        make_action("e3-2", "us", "walk_away", None, "美方宣布退出谈判。"),
    ]
    run_steps(engine, steps)
    evaluation = print_report(engine)
    assert evaluation["terminal_type"] == "WITHDRAWAL"
    assert evaluation["agreement_quality"]["coverage"] == 0.0
    assert evaluation["redline_check"] == {}
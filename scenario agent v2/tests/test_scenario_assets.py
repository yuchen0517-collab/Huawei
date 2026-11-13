"""场景资产测试：data/scenarios 下每份场景都必须自洽、可加载、可行性符合设计意图。"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.scenario.models import validate_scenario
from agent.scenario.zopa import evaluate_deal, scenario_feasibility, suggest_deal

SCENARIO_DIR = ROOT / "data" / "scenarios"
SCENARIO_FILES = sorted(SCENARIO_DIR.glob("*.json"))
SCENARIO_IDS = [path.stem for path in SCENARIO_FILES]

KEBAB_ID = re.compile(r"^scn-[a-z0-9]+(-[a-z0-9]+)*$")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 四组通用检查，对每一份场景都跑一遍
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", SCENARIO_FILES, ids=SCENARIO_IDS)
def test_scenario_validates_clean(path):
    problems = validate_scenario(load(path))
    detail = [(p.code, p.path, p.message) for p in problems]
    assert problems == [], f"{path.name} 校验未通过：{detail}"


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=SCENARIO_IDS)
def test_scenario_id_is_kebab_case(path):
    data = load(path)
    assert KEBAB_ID.match(data["scenario_id"]), f"{data['scenario_id']!r} 不符合 scn-xxx-0001 风格"


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=SCENARIO_IDS)
def test_scenario_is_bilateral_and_named_for_engine(path):
    data = load(path)
    assert len(data["parties"]) == 2
    names = [issue["name"] for issue in data["issues"]]
    assert len(set(names)) == len(names), "条款名会被当作 JSON 键，必须唯一"
    assert all(len(name) <= 20 for name in names)
    for fact in data["public_facts"]:
        assert fact["source"]["url"].startswith("http"), fact["fact_id"]


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=SCENARIO_IDS)
def test_scenario_type_is_labelled(path):
    """假设推演必须真的写出假设理由。"""
    data = load(path)
    assert data["scenario_type"] in ("documented", "hypothesis")
    if data["scenario_type"] == "hypothesis":
        assert data["assumptions"], "假设推演必须至少有一条假设"
        for assumption in data["assumptions"]:
            assert assumption["reason"].strip()


# ---------------------------------------------------------------------------
# 各场景的设计意图（Day 5 的核心验收）
# ---------------------------------------------------------------------------
def test_main_scenario_has_zopa():
    data = load(SCENARIO_DIR / "main_chip_controls.json")
    feasibility = scenario_feasibility(data)
    assert feasibility["zopa_exists"] is True
    assert feasibility["infeasible_issues"] == []
    assert set(suggest_deal(data)) == {issue["issue_id"] for issue in data["issues"]}


def test_main_scenario_suggested_deal_beats_batna():
    data = load(SCENARIO_DIR / "main_chip_controls.json")
    result = evaluate_deal(data, suggest_deal(data))
    assert result["any_redline_violated"] is False
    assert result["all_above_batna"] is True, result["parties"]


def test_no_zopa_variant_actually_has_no_zopa():
    data = load(SCENARIO_DIR / "no_zopa_variant.json")
    feasibility = scenario_feasibility(data)
    assert feasibility["zopa_exists"] is False
    assert "I4" in feasibility["infeasible_issues"]
    assert data["negotiability"]["zopa_exists"] is False


def test_no_zopa_variant_leads_to_rational_exit():
    """无合作区间时，只锁定部分议题的方案对双方都不如 BATNA —— 理性选择是退出。

    这不是 bug：手册 5.2 要求「退出不直接等于失败」，规则引擎应能识别这种情况。
    """
    data = load(SCENARIO_DIR / "no_zopa_variant.json")
    result = evaluate_deal(data, suggest_deal(data))
    assert result["all_above_batna"] is False


def test_backup_scenario_is_demo_ready():
    data = load(SCENARIO_DIR / "backup_dst_bilateral.json")
    feasibility = scenario_feasibility(data)
    assert feasibility["zopa_exists"] is True
    result = evaluate_deal(data, suggest_deal(data))
    assert result["any_redline_violated"] is False
    assert result["all_above_batna"] is True, result["parties"]


def test_backup_scenario_covers_a_different_topic():
    """备选的用途是「主场景出问题时还能演示」，所以议题必须真的不同。

    两份事实卡共用 CN-01 / US-01 编号空间，所以不能靠 fact_id 判断来源，
    改判正文落在各自领域。
    """
    main = load(SCENARIO_DIR / "main_chip_controls.json")
    backup = load(SCENARIO_DIR / "backup_dst_bilateral.json")

    assert main["scenario_id"] != backup["scenario_id"]
    main_issues = {issue["name"] for issue in main["issues"]}
    backup_issues = {issue["name"] for issue in backup["issues"]}
    assert main_issues.isdisjoint(backup_issues)

    main_text = "".join(fact["text"] for fact in main["public_facts"])
    backup_text = "".join(fact["text"] for fact in backup["public_facts"])
    assert "芯片" in main_text or "算力" in main_text
    assert "数字" in backup_text or "税" in backup_text

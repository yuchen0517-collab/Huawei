import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.scenario.negotiability import check

CASES = [
    (
        "中美先进计算芯片的许可门槛与审批时限",
        {"pending", "direct"},
        None,
        "案例1_芯片许可门槛与审批时限",
    ),
    (
        "两国跨境河流的年度取水量分配与生态补偿",
        {"pending"},
        None,
        "案例2_跨境河流水量分配",
    ),
    (
        "中美科技竞争",
        {"pending"},
        None,
        "案例3_中美科技竞争_宽泛",
    ),
    (
        "六国数字税谈判",
        {"needs_narrowing"},
        "U4",
        "案例4_六国数字税_U4",
    ),
    (
        "谁该为全球变暖负主要责任",
        {"unsupported"},
        "U1",
        "案例5_全球变暖责任_U1",
    ),
    (
        "2028 年美国大选结果会怎样",
        {"unsupported"},
        "U2",
        "案例6_美国大选结果_U2",
    ),
    (
        "中美芯片出口管制谈判，讨论是否设立双边热线",
        "!unsupported",
        None,
        "案例7_芯片出口管制热线_排除unsupported",
    ),
    (
        "中美之间的隐私与数据跨境问题",
        "!unsupported",
        None,
        "案例8_隐私与数据跨境_排除unsupported",
    ),
    (
        "某部长的私生活传闻",
        {"unsupported"},
        "U3",
        "案例9_部长私生活_U3",
    ),
]

IDS = [case[3] for case in CASES]


@pytest.mark.parametrize("topic, expected_verdicts, expected_rule", [case[:3] for case in CASES], ids=IDS)
def test_check_boundary_cases(topic, expected_verdicts, expected_rule):
    result = check(topic)
    assert set(result) == {"verdict", "reasons", "suggestions", "matched_rules"}
    if isinstance(expected_verdicts, str):
        forbidden = expected_verdicts[1:]
        assert result["verdict"] != forbidden, (
            f"「{topic}」不允许 {forbidden}，实际 {result['verdict']}，"
            f"matched_rules={result['matched_rules']}"
        )
    else:
        assert result["verdict"] in expected_verdicts, (
            f"「{topic}」期望 {sorted(expected_verdicts)}，实际 {result['verdict']}，"
            f"matched_rules={result['matched_rules']}"
        )
    assert result["reasons"], "reasons 不能为空"
    assert result["suggestions"], "suggestions 不能为空"
    if expected_rule is None:
        assert result["matched_rules"] == [], f"「{topic}」规则层不应命中任何 U 规则"
    else:
        assert result["matched_rules"] == [expected_rule], (
            f"「{topic}」期望命中 {expected_rule}，实际 {result['matched_rules']}"
        )
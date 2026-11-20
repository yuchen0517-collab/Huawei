"""口径一致性回归：B 的 `zopa` 与引擎必须对同一份方案算出同一结果。

背景：11-20 之前两边是两套算法（order vs target、closeness vs 红线比例、
部分协议是否计入现状值），导致 no_zopa 变体在 QA 里"双方都该退出"、
在 App 里"双方都大赚"。本文件把 `check_score_alignment.py` 从诊断脚本
升级为回归测试，防止两边再次漂移。
"""

import check_score_alignment as alignment


def test_zopa_and_engine_agree_on_every_b_scenario():
    rows = alignment.compare_all()
    assert rows, "至少应覆盖三份 B 场景"
    for row in rows:
        assert row["match"], f"数值不一致：{row}"
        assert row["engine_above_batna"] == row["zopa_above_batna"], f"结论不一致：{row}"


def test_no_zopa_variant_is_below_batna_for_both_parties():
    """该变体的设计意图：任何不含 I4 的部分方案都低于双方 BATNA，理性终局是退出。"""
    rows = [
        row
        for row in alignment.compare_all()
        if row["scenario"] == "no_zopa_variant.json"
    ]
    assert len(rows) == 2
    for row in rows:
        assert not row["engine_above_batna"], row


def test_main_and_backup_are_demo_ready():
    """主场景与备选场景的参考方案必须对双方都优于 BATNA。"""
    for scenario in ("main_chip_controls.json", "backup_dst_bilateral.json"):
        rows = [
            row for row in alignment.compare_all() if row["scenario"] == scenario
        ]
        assert len(rows) == 2
        for row in rows:
            assert row["engine_above_batna"], row

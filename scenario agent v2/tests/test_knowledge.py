"""知识依据检索的 4 条验收测试。

对应手册 4.3 的三档行为：有资料返回出处 / 资料不足给建议 / 绝不编造。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.scenario.knowledge import (
    EMPTY_HINT,
    FactCorpus,
    build_corpus,
    lookup,
    lookup_with_hint,
)

MAIN = ROOT / "data" / "scenarios" / "main_chip_controls.json"


def load_main() -> dict:
    return json.loads(MAIN.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. 命中：能召回、带出处、理由说得通
# ---------------------------------------------------------------------------
def test_hit_returns_evidence_with_source():
    corpus = build_corpus(scenario=load_main())
    results = lookup("芯片出口许可", corpus, issue_id="I1")

    assert results, "应当召回至少一条证据"
    for item in results:
        assert item.fact_id
        assert item.text.strip()
        assert item.source["url"].startswith(("http://", "https://")), item.fact_id
        assert item.source["name"].strip(), item.fact_id
        assert item.match_reason.strip(), "每条都要说明为什么相关"
        assert item.reliability in ("high", "medium", "low")

    # 指定 issue_id 时，必须有一条命中「明确标注适用于议题」这个加分理由
    assert any("明确标注适用于议题" in item.match_reason for item in results), \
        f"指定 issue_id 应触发议题加分，实际理由：{[i.match_reason for i in results]}"

    # 结果按相关度降序
    scores = [item.score for item in results]
    assert scores == sorted(scores, reverse=True)


def test_top_k_is_respected():
    corpus = build_corpus(scenario=load_main())
    assert len(lookup("芯片", corpus, top_k=2)) <= 2


# ---------------------------------------------------------------------------
# 2. 空结果：返回空 + 建议文案，不编造来源
# ---------------------------------------------------------------------------
def test_miss_returns_empty_with_hint():
    corpus = build_corpus(scenario=load_main())
    results, hint = lookup_with_hint("南极磷虾捕捞配额的年际调整机制", corpus)

    assert results == [], "没有相关资料时必须返回空，不能凑一条出来"
    assert hint == EMPTY_HINT
    assert "假设推演" in hint or "补充" in hint


# ---------------------------------------------------------------------------
# 3. C 级（待核实）默认排除，显式放行时标 low
# ---------------------------------------------------------------------------
def test_low_confidence_is_flagged_and_excluded_by_default():
    data = load_main()
    target = data["public_facts"][0]
    target["source"]["confidence"] = "C"
    target["text"] = "待核实：芯片出口许可审批口径可能调整"
    corpus = FactCorpus.from_scenario(data)

    default_results = lookup("芯片出口许可审批", corpus, allow_low=False)
    assert all(item.fact_id != target["fact_id"] for item in default_results), \
        "C 级不应出现在默认结果里"

    loosened = lookup("芯片出口许可审批", corpus, allow_low=True)
    flagged = [item for item in loosened if item.fact_id == target["fact_id"]]
    assert flagged, "显式 allow_low=True 时应该能检出来"
    assert flagged[0].reliability == "low"


# ---------------------------------------------------------------------------
# 4. 不泄漏私有状态：返回结构里只有公开字段
# ---------------------------------------------------------------------------
def test_evidence_never_leaks_private_state():
    data = load_main()
    corpus = build_corpus(scenario=data)
    results = lookup("关键矿产 稀土 出口许可", corpus, issue_id="I4")

    assert results, "应当召回稀土相关证据"
    blob = json.dumps([item.to_dict() for item in results], ensure_ascii=False)

    # 私有状态的关键字一律不能出现
    for forbidden in ("hidden_task", "redlines", "batna", "priority_ranking",
                      "把稀土议题与芯片许可解耦", "不接受第三方核查"):
        assert forbidden not in blob, f"证据里泄漏了 {forbidden!r}"

    # corpus 里也不该有私有数据
    assert all("goals" not in fact for fact in corpus.facts)
    assert all("redlines" not in fact for fact in corpus.facts)

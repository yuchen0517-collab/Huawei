import copy
import json
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.scenario.factcard_loader import (
    CONFIDENCE_VALUES,
    FACT_TYPE_VALUES,
    build_index,
    load_factcard_file,
    load_factcards,
    to_public_facts,
)

CHIP_CARDS = ROOT / "data" / "facts" / "算力与芯片出口管制_事实卡_补充版.xlsx"
DST_CARDS = ROOT / "data" / "facts" / "数字服务税与跨境征税权分配_事实卡_六国.xlsx"
PARTY_MAP = {"中国": "cn", "美国": "us", "欧盟": "eu", "印度": "in", "英国": "uk", "土耳其": "tr"}
HEADER = ["编号", "类型", "内容（一句话，≤60字）", "数值", "时间", "来源名称", "来源链接", "可信度", "备注"]

FACT_KEYS = {"fact_id", "text", "type", "source", "applies_to"}
SOURCE_KEYS = {"name", "url", "published_at", "confidence"}


def _write_xlsx(path: Path, rows: list[list], sheet_title: str = "中国_事实卡") -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_title
    sheet.append(HEADER)
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    workbook.close()


# ===========================================================================
# 第一组：原有 3 条（针对 load_factcards 的 (facts, low_confidence) 接口）
# ===========================================================================
def test_loads_real_factcards():
    facts, low_confidence = load_factcards(CHIP_CARDS, PARTY_MAP)
    assert facts
    assert any(fact["fact_id"] == "CN-01" for fact in facts)
    assert all(fact["source"]["url"].startswith(("http://", "https://")) for fact in facts)
    assert all(fact["source"]["confidence"] in {"A", "B", "C"} for fact in facts)
    assert {fact["fact_id"] for fact in low_confidence} <= {fact["fact_id"] for fact in facts}


def test_rejects_bad_url(tmp_path):
    path = tmp_path / "bad_url.xlsx"
    _write_xlsx(path, [
        ["CN-99", "行动", "坏链接条目", "", "2025-01-01", "某来源", "ftp://example.com/x", "A", ""],
        ["CN-98", "行动", "正常条目", "", "2025-01-01", "某来源", "https://example.com/ok", "A", ""],
    ])
    facts, low_confidence = load_factcards(path, PARTY_MAP)
    ids = {fact["fact_id"] for fact in facts}
    assert "CN-99" not in ids
    assert "CN-98" in ids
    assert not low_confidence


def test_c_confidence_goes_to_low_confidence(tmp_path):
    path = tmp_path / "low_confidence.xlsx"
    _write_xlsx(path, [
        ["CN-97", "立场", "待核实条目", "", "2025-01", "某媒体", "https://example.com/c", "C", ""],
    ])
    facts, low_confidence = load_factcards(path, PARTY_MAP)
    assert {fact["fact_id"] for fact in facts} == {"CN-97"}
    assert {fact["fact_id"] for fact in low_confidence} == {"CN-97"}
    assert facts[0]["source"]["published_at"] == "2025-01"


# ===========================================================================
# 第二组：条数与真实卡片对得上（Day 4 验收第 1 条）
# ===========================================================================
@pytest.fixture(scope="module")
def chip_bundle():
    return load_factcard_file(CHIP_CARDS, PARTY_MAP)


@pytest.fixture(scope="module")
def dst_bundle():
    return load_factcard_file(DST_CARDS, PARTY_MAP)


def test_chip_card_counts_match_xlsx(chip_bundle):
    assert len(chip_bundle.facts) == 47
    assert chip_bundle.summary()["by_party"] == {"cn": 23, "us": 24}
    assert chip_bundle.invalid == [], "真实卡片不应有被丢弃的条目"


def test_dst_card_counts_match_xlsx(dst_bundle):
    assert len(dst_bundle.facts) == 137
    assert dst_bundle.invalid == []


def test_counts_equal_loaded_plus_rejected(chip_bundle):
    """载入数 + 被拒数 == xlsx 数据行数，一条都不能凭空消失。"""
    loaded = len(chip_bundle.facts)
    rejected = len(chip_bundle.invalid)
    assert loaded + rejected == 47


# ===========================================================================
# 第三组：来源与 schema 合规（Day 4 验收第 2、3 条）
# ===========================================================================
def test_every_fact_has_http_source(chip_bundle):
    for fact in chip_bundle.facts:
        assert fact["source"]["url"].startswith(("http://", "https://")), fact["fact_id"]
        assert fact["source"]["name"].strip(), fact["fact_id"]
        assert fact["text"].strip(), fact["fact_id"]


def test_output_is_schema_compliant(chip_bundle):
    """public_facts 与 source 都是 additionalProperties=false，不能夹带自定义字段。"""
    for fact in chip_bundle.facts:
        assert set(fact) == FACT_KEYS, fact["fact_id"]
        assert set(fact["source"]) == SOURCE_KEYS, fact["fact_id"]


def test_enums_are_valid(chip_bundle):
    for fact in chip_bundle.facts:
        assert fact["type"] in FACT_TYPE_VALUES, fact["fact_id"]
        assert fact["source"]["confidence"] in CONFIDENCE_VALUES, fact["fact_id"]


def test_every_fact_has_confidence(chip_bundle):
    assert all(fact["source"].get("confidence") for fact in chip_bundle.facts)


def test_low_confidence_is_exactly_the_c_level(chip_bundle):
    assert chip_bundle.low_confidence, "真实卡片里应该有 C 级条目"
    assert all(fact["source"]["confidence"] == "C" for fact in chip_bundle.low_confidence)
    expected = {f["fact_id"] for f in chip_bundle.facts if f["source"]["confidence"] == "C"}
    assert {fact["fact_id"] for fact in chip_bundle.low_confidence} == expected


# ===========================================================================
# 第四组：阶段标签不能混进 public_facts
# ===========================================================================
def test_stage_parsed_from_note_but_kept_out_of_facts(dst_bundle):
    assert dst_bundle.stage_by_fact, "DST 卡的备注里有 P1-P6，应该被解析出来"
    sample_id = next(iter(dst_bundle.stage_by_fact))
    assert dst_bundle.stage_by_fact[sample_id].startswith("P")
    fact = next(fact for fact in dst_bundle.facts if fact["fact_id"] == sample_id)
    assert "stage" not in fact, "schema 不允许额外字段，stage 只能进索引"


def test_dst_cards_cover_six_parties(dst_bundle):
    assert set(dst_bundle.party_by_fact.values()) == {"cn", "us", "eu", "in", "uk", "tr"}


# ===========================================================================
# 第五组：脏数据必须被拦
# ===========================================================================
def test_fact_without_url_is_rejected(tmp_path):
    path = tmp_path / "no_url.xlsx"
    _write_xlsx(path, [
        ["CN-96", "行动", "没有链接的事实", "", "2025-01-01", "某来源", "", "A", ""],
        ["CN-95", "行动", "有链接的事实", "", "2025-01-01", "某来源", "https://example.com/x", "A", ""],
    ])
    bundle = load_factcard_file(path, PARTY_MAP)
    assert [f["fact_id"] for f in bundle.facts] == ["CN-95"]
    assert bundle.invalid[0]["fact_id"] == "CN-96"
    assert "链接" in bundle.invalid[0]["reason"]


def test_unknown_type_is_rejected(tmp_path):
    path = tmp_path / "bad_type.xlsx"
    _write_xlsx(path, [
        ["CN-94", "谣言", "类型不在枚举内", "", "2025-01-01", "某来源", "https://example.com/x", "A", ""],
    ])
    bundle = load_factcard_file(path, PARTY_MAP)
    assert bundle.facts == []
    assert "类型" in bundle.invalid[0]["reason"]


def test_bad_confidence_falls_back_to_c(tmp_path):
    path = tmp_path / "bad_conf.xlsx"
    _write_xlsx(path, [
        ["CN-93", "行动", "可信度写错了", "", "2025-01-01", "某来源", "https://example.com/x", "Z", ""],
    ])
    bundle = load_factcard_file(path, PARTY_MAP)
    assert bundle.facts[0]["source"]["confidence"] == "C"
    assert any("可信度" in item for item in bundle.warnings)


def test_duplicate_fact_id_is_rejected(tmp_path):
    path = tmp_path / "dup.xlsx"
    _write_xlsx(path, [
        ["CN-92", "行动", "第一条", "", "2025-01-01", "某来源", "https://example.com/a", "A", ""],
        ["CN-92", "行动", "重复编号", "", "2025-01-02", "某来源", "https://example.com/b", "A", ""],
    ])
    bundle = load_factcard_file(path, PARTY_MAP)
    assert len(bundle.facts) == 1
    assert "重复" in bundle.invalid[0]["reason"]


# ===========================================================================
# 第六组：取用与索引
# ===========================================================================
def test_to_public_facts_filters_by_party_and_ids(chip_bundle):
    only_cn = to_public_facts(chip_bundle, parties=["cn"])
    assert only_cn
    assert all(chip_bundle.party_by_fact[f["fact_id"]] == "cn" for f in only_cn)

    picked = to_public_facts(chip_bundle, parties=["cn", "us"], facts=["CN-05", "US-09"])
    assert [f["fact_id"] for f in picked] == ["CN-05", "US-09"]


def test_to_public_facts_fills_applies_to(chip_bundle):
    picked = to_public_facts(chip_bundle, parties=["cn"], facts=["CN-05"], applies_to={"CN-05": ["I4"]})
    assert picked[0]["applies_to"] == ["I4"]


def test_index_keeps_metadata_out_of_facts(chip_bundle):
    index = build_index(chip_bundle)
    assert index["meta"]["total"] == 47
    assert index["meta"]["by_party"] == {"cn": 23, "us": 24}
    assert "by_stage" in index and "low_confidence" in index
    json.dumps(index, ensure_ascii=False)  # 必须可序列化

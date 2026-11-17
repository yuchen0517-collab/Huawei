"""知识依据检索：把「要求依据」这个行动真正接上事实库。

设计原则（手册 4.3）
--------------------
· 只在 **public_facts** 上检索，永不触碰 private_state
· 有结果就返回摘要 + 出处（带 url），供「要求依据」卡调用
· 没结果就返回空 + 一句建议文案，**不许编造来源**
· C 级（待核实）默认不进结果，需要时显式 allow_low=True

为什么不建向量库
----------------
`public_facts` 已经是结构化数据（text + type + source + applies_to），
中文短句用「n-gram 覆盖度」召回已经很准，且零依赖、零成本、可测试。
建 RAG 全家桶属于手册 1.4 明确排除的范围膨胀。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

RELIABILITY_BY_CONFIDENCE = {"A": "high", "B": "medium", "C": "low"}
DEFAULT_TOP_K = 5
RECALL_POOL = 20
EMPTY_HINT = "现有资料未覆盖该条款，建议切换到假设推演模式或补充资料。"

__all__ = [
    "Evidence",
    "FactCorpus",
    "lookup",
    "lookup_with_hint",
    "build_corpus",
    "EMPTY_HINT",
]


# ---------------------------------------------------------------------------
@dataclass
class Evidence:
    fact_id: str
    text: str
    source: dict[str, Any]
    match_reason: str
    reliability: str
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "text": self.text,
            "source": self.source,
            "match_reason": self.match_reason,
            "reliability": self.reliability,
        }


@dataclass
class FactCorpus:
    """可检索的事实集合。只装 public_facts，装不进任何私有状态。"""

    facts: list[dict[str, Any]] = field(default_factory=list)
    issues: dict[str, str] = field(default_factory=dict)  # issue_id -> name

    @classmethod
    def from_scenario(cls, data: Mapping[str, Any]) -> "FactCorpus":
        facts = [dict(fact) for fact in data.get("public_facts") or [] if isinstance(fact, Mapping)]
        issues = {
            issue["issue_id"]: issue.get("name", "")
            for issue in data.get("issues") or []
            if isinstance(issue, Mapping) and issue.get("issue_id")
        }
        # 只保留白名单字段，防止调用方顺手把别的字段塞进来
        cleaned = [
            {
                "fact_id": fact.get("fact_id", ""),
                "text": fact.get("text", ""),
                "type": fact.get("type", ""),
                "source": dict(fact.get("source") or {}),
                "applies_to": list(fact.get("applies_to") or []),
            }
            for fact in facts
        ]
        return cls(facts=cleaned, issues=issues)

    @classmethod
    def from_scenario_files(cls, paths: Iterable[str | Path]) -> "FactCorpus":
        corpus = cls()
        seen: set[str] = set()
        for raw in paths:
            path = Path(raw)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            part = cls.from_scenario(data)
            for fact in part.facts:
                if fact["fact_id"] in seen:
                    continue
                seen.add(fact["fact_id"])
                corpus.facts.append(fact)
            corpus.issues.update(part.issues)
        return corpus

    def __len__(self) -> int:
        return len(self.facts)


# ---------------------------------------------------------------------------
def _ngrams(text: str, low: int = 2, high: int = 4) -> set[str]:
    """中文没有空格，用 2~4 字的滑动窗口当检索单元。"""
    cleaned = "".join(ch for ch in text if ch.strip())
    grams: set[str] = set()
    for size in range(low, min(high, len(cleaned)) + 1):
        for start in range(len(cleaned) - size + 1):
            grams.add(cleaned[start:start + size])
    return grams


def _reliability(fact: Mapping[str, Any]) -> str:
    confidence = (fact.get("source") or {}).get("confidence", "C")
    return RELIABILITY_BY_CONFIDENCE.get(str(confidence).upper(), "low")


def _score(query_grams: set[str], fact: Mapping[str, Any], issues: Mapping[str, str],
           issue_id: str | None) -> tuple[float, list[str]]:
    text = str(fact.get("text", ""))
    haystack = _ngrams(text) | _ngrams(str(fact.get("type", "")), 2, 2)

    hits = query_grams & haystack
    if not hits:
        return 0.0, []

    score = len(hits) / max(len(query_grams), 1)
    reasons = [f"命中「{'、'.join(sorted(hits)[:3])}」"]

    applies = fact.get("applies_to") or []
    if issue_id and issue_id in applies:
        score += 0.35
        reasons.append(f"明确标注适用于议题「{issues.get(issue_id, issue_id)}」")
    elif applies:
        names = "、".join(issues.get(item, item) for item in applies[:2])
        reasons.append(f"标注适用于 {names}")

    if fact.get("type") in ("引用", "立场"):
        score += 0.05  # 公开表态类更适合作为「要求依据」的回复

    return round(score, 4), reasons


# ---------------------------------------------------------------------------
def lookup(
    query: str,
    corpus: FactCorpus,
    issue_id: str | None = None,
    top_k: int = DEFAULT_TOP_K,
    allow_low: bool = False,
) -> list[Evidence]:
    """在公开事实上检索，返回按相关度排序的证据。

    · 绝不读取 private_state —— corpus 里根本没有这类数据
    · allow_low=False 时过滤掉 C 级（待核实）
    """
    query = (query or "").strip()
    if not query or not corpus.facts:
        return []

    query_grams = _ngrams(query)
    if not query_grams:
        return []

    scored: list[tuple[float, list[str], dict[str, Any]]] = []
    for fact in corpus.facts:
        score, reasons = _score(query_grams, fact, corpus.issues, issue_id)
        if score <= 0:
            continue
        scored.append((score, reasons, fact))

    scored.sort(key=lambda item: (-item[0], item[2].get("fact_id", "")))

    results: list[Evidence] = []
    for score, reasons, fact in scored[:RECALL_POOL]:
        reliability = _reliability(fact)
        if reliability == "low" and not allow_low:
            continue
        results.append(
            Evidence(
                fact_id=str(fact.get("fact_id", "")),
                text=str(fact.get("text", "")),
                source=dict(fact.get("source") or {}),
                match_reason="；".join(reasons) or "文本重合",
                reliability=reliability,
                score=score,
            )
        )
        if len(results) >= top_k:
            break

    return results


def lookup_with_hint(
    query: str,
    corpus: FactCorpus,
    issue_id: str | None = None,
    top_k: int = DEFAULT_TOP_K,
    allow_low: bool = False,
) -> tuple[list[Evidence], str]:
    """检索 + 兜底文案。空结果时 hint 非空，绝不编造来源。"""
    results = lookup(query, corpus, issue_id=issue_id, top_k=top_k, allow_low=allow_low)
    if results:
        return results, ""
    return [], EMPTY_HINT


def build_corpus(scenario: Mapping[str, Any] | None = None,
                 scenario_dir: str | Path | None = None) -> FactCorpus:
    """两种建库方式：给一份场景，或给一个装场景 json 的目录。"""
    if scenario is not None:
        return FactCorpus.from_scenario(scenario)
    if scenario_dir is not None:
        return FactCorpus.from_scenario_files(sorted(Path(scenario_dir).glob("*.json")))
    return FactCorpus()

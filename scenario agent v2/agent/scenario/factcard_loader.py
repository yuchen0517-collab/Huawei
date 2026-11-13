"""事实卡加载器：把 xlsx 事实卡转成 schema 合规的 public_facts。

· url 不是 http 开头的整条丢弃（进 invalid，附行号）
· 可信度不在 A/B/C 的按 C 处理并告警
· 类型不在 立场/行动/数字/引用/智库 的整条丢弃
· 同一 fact_id 重复的丢弃并告警

public_facts 与 source 在 schema 里都是 additionalProperties=false，
所以阶段标签、数值、备注一律进 facts_index，不进事实本体。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

FACT_TYPE_VALUES = ("立场", "行动", "数字", "引用", "智库")
CONFIDENCE_VALUES = ("A", "B", "C")
SHEET_SUFFIX = "_事实卡"
MAX_TEXT_LEN = 60

PARTY_CODE = {
    "中国": "cn", "美国": "us", "欧盟": "eu", "英国": "uk", "法国": "fr",
    "德国": "de", "印度": "in", "土耳其": "tr", "日本": "jp", "巴西": "br",
}

HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "fact_id": ("编号", "id", "fact_id"),
    "type": ("类型",),
    "text": ("内容", "事实"),
    "value": ("数值",),
    "published_at": ("时间", "日期"),
    "source_name": ("来源名称", "来源"),
    "source_url": ("来源链接", "链接", "url"),
    "confidence": ("可信度",),
    "note": ("备注",),
}

_STAGE_PATTERN = re.compile(r"P\d")

__all__ = [
    "FactCardBundle", "load_factcard_file", "load_factcards",
    "to_public_facts", "build_index", "write_index", "PARTY_CODE",
]


@dataclass
class FactCardBundle:
    facts: list[dict[str, Any]] = field(default_factory=list)
    low_confidence: list[dict[str, Any]] = field(default_factory=list)
    invalid: list[dict[str, Any]] = field(default_factory=list)
    stage_by_fact: dict[str, str] = field(default_factory=dict)
    party_by_fact: dict[str, str] = field(default_factory=dict)
    note_by_fact: dict[str, str] = field(default_factory=dict)
    value_by_fact: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def merge(self, other: "FactCardBundle") -> None:
        known = {fact["fact_id"] for fact in self.facts}
        for fact in other.facts:
            if fact["fact_id"] in known:
                self.warnings.append(
                    f"fact_id 冲突：{fact['fact_id']} 已存在，后出现的条目被跳过"
                    f"（不同 topic 的编号空间不共享，请按 topic 分别建索引）"
                )
                continue
            self.facts.append(fact)
            known.add(fact["fact_id"])
        self.low_confidence.extend(other.low_confidence)
        self.invalid.extend(other.invalid)
        for attr in ("stage_by_fact", "party_by_fact", "note_by_fact", "value_by_fact"):
            getattr(self, attr).update(getattr(other, attr))
        self.warnings.extend(other.warnings)

    def only_parties(self, parties: Iterable[str]) -> list[dict[str, Any]]:
        wanted = set(parties)
        return [f for f in self.facts if self.party_by_fact.get(f["fact_id"]) in wanted]

    def summary(self) -> dict[str, Any]:
        by_party: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for fact in self.facts:
            party = self.party_by_fact.get(fact["fact_id"], "?")
            by_party[party] = by_party.get(party, 0) + 1
            conf = fact["source"]["confidence"]
            by_confidence[conf] = by_confidence.get(conf, 0) + 1
        return {
            "total": len(self.facts),
            "by_party": by_party,
            "by_confidence": by_confidence,
            "low_confidence": len(self.low_confidence),
            "invalid": len(self.invalid),
            "warnings": len(self.warnings),
        }


def _norm_header(value: Any) -> str:
    text = str(value or "").strip()
    for mark in ("（", "("):
        if mark in text:
            text = text.split(mark)[0]
    return text.strip()


def _map_header(ws) -> tuple[int, dict[str, int]] | None:
    for row_index, row in enumerate(ws.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
        if not row:
            continue
        normalized = [_norm_header(cell) for cell in row]
        if "编号" not in normalized:
            continue
        mapping: dict[str, int] = {}
        for key, aliases in HEADER_ALIASES.items():
            for column, header in enumerate(normalized):
                if header in aliases:
                    mapping[key] = column
                    break
        if "fact_id" in mapping and "text" in mapping:
            return row_index, mapping
    return None


def _cell(row: tuple, mapping: Mapping[str, int], key: str) -> Any:
    column = mapping.get(key)
    if column is None or column >= len(row):
        return None
    return row[column]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def _party_of(sheet_title: str) -> str:
    prefix = sheet_title.split(SHEET_SUFFIX)[0].strip()
    return PARTY_CODE.get(prefix, prefix.lower())


def _iter_data_rows(ws, header_row: int):
    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        if not row:
            continue
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        yield row


def load_factcard_file(path: str | Path) -> FactCardBundle:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"事实卡文件不存在：{path}")

    import openpyxl

    bundle = FactCardBundle()
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        titles = [t for t in workbook.sheetnames if t.endswith(SHEET_SUFFIX)]
        if not titles:
            bundle.warnings.append(f"{path.name}：没有找到以 {SHEET_SUFFIX} 结尾的工作表")
            return bundle

        for title in titles:
            sheet = workbook[title]
            party = _party_of(title)
            located = _map_header(sheet)
            if located is None:
                bundle.warnings.append(f"{title}：找不到表头（需要含「编号」「内容」列）")
                continue
            header_row, mapping = located
            if "source_url" not in mapping:
                bundle.warnings.append(f"{title}：缺少「来源链接」列，全部条目将被判为无来源")
            if "confidence" not in mapping:
                bundle.warnings.append(f"{title}：缺少「可信度」列，全部条目按 C 处理")

            for offset, row in enumerate(_iter_data_rows(sheet, header_row), start=header_row + 1):
                fact_id = _text(_cell(row, mapping, "fact_id"))
                if not fact_id:
                    continue
                text = _text(_cell(row, mapping, "text"))
                fact_type = _text(_cell(row, mapping, "type"))
                url = _text(_cell(row, mapping, "source_url"))
                name = _text(_cell(row, mapping, "source_name"))
                published_at = _text(_cell(row, mapping, "published_at"))
                confidence = _text(_cell(row, mapping, "confidence")).upper()
                note = _text(_cell(row, mapping, "note"))
                value = _text(_cell(row, mapping, "value"))

                reason = None
                if not text:
                    reason = "内容为空"
                elif fact_type not in FACT_TYPE_VALUES:
                    reason = f"类型 {fact_type!r} 不在 {list(FACT_TYPE_VALUES)}"
                elif not url.lower().startswith(("http://", "https://")):
                    reason = f"来源链接不是 http(s)：{url!r}" if url else "缺少来源链接"
                elif not name:
                    reason = "来源名称为空"
                elif fact_id in bundle.party_by_fact:
                    reason = f"fact_id {fact_id!r} 重复"

                if reason is not None:
                    bundle.invalid.append(
                        {"sheet": title, "row": offset, "fact_id": fact_id or "<空>", "reason": reason}
                    )
                    continue

                if confidence not in CONFIDENCE_VALUES:
                    bundle.warnings.append(
                        f"{title} 第 {offset} 行：可信度 {confidence!r} 非 A/B/C，按 C 处理"
                    )
                    confidence = "C"
                if len(text) > MAX_TEXT_LEN:
                    bundle.warnings.append(
                        f"{title} 第 {offset} 行（{fact_id}）：内容 {len(text)} 字，超过建议的 {MAX_TEXT_LEN} 字"
                    )

                fact = {
                    "fact_id": fact_id,
                    "text": text,
                    "type": fact_type,
                    "source": {"name": name, "url": url,
                               "published_at": published_at, "confidence": confidence},
                    "applies_to": [],
                }
                bundle.facts.append(fact)
                bundle.party_by_fact[fact_id] = party
                if confidence == "C":
                    bundle.low_confidence.append(fact)
                if note:
                    bundle.note_by_fact[fact_id] = note
                    match = _STAGE_PATTERN.search(note)
                    if match:
                        bundle.stage_by_fact[fact_id] = match.group(0)
                if value:
                    bundle.value_by_fact[fact_id] = value
    finally:
        workbook.close()

    bundle.stats = bundle.summary()
    return bundle


def load_factcards(paths: Iterable[str | Path]) -> FactCardBundle:
    merged = FactCardBundle()
    for item in paths:
        merged.merge(load_factcard_file(item))
    merged.stats = merged.summary()
    return merged


def to_public_facts(
    bundle: FactCardBundle,
    parties: Iterable[str] | None = None,
    applies_to: Mapping[str, list[str]] | None = None,
    facts: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    selected = bundle.facts if parties is None else bundle.only_parties(parties)
    if facts is not None:
        wanted = set(facts)
        selected = [f for f in selected if f["fact_id"] in wanted]
    result = []
    for fact in selected:
        cloned = json.loads(json.dumps(fact, ensure_ascii=False))
        if applies_to is not None:
            cloned["applies_to"] = list(applies_to.get(cloned["fact_id"], []))
        result.append(cloned)
    return result


def build_index(bundle: FactCardBundle) -> dict[str, Any]:
    by_party: dict[str, list[str]] = {}
    by_type: dict[str, list[str]] = {}
    by_stage: dict[str, list[str]] = {}
    for fact in bundle.facts:
        fact_id = fact["fact_id"]
        by_party.setdefault(bundle.party_by_fact.get(fact_id, "?"), []).append(fact_id)
        by_type.setdefault(fact["type"], []).append(fact_id)
        stage = bundle.stage_by_fact.get(fact_id)
        if stage:
            by_stage.setdefault(stage, []).append(fact_id)
    return {
        "meta": {
            "generator": "agent/scenario/factcard_loader.py",
            "note": "public_facts 只保留 schema 允许的 5 个字段；阶段、备注、数值存这里",
            **bundle.stats,
        },
        "by_party": by_party,
        "by_type": by_type,
        "by_stage": by_stage,
        "stage_by_fact": bundle.stage_by_fact,
        "note_by_fact": bundle.note_by_fact,
        "value_by_fact": bundle.value_by_fact,
        "low_confidence": [f["fact_id"] for f in bundle.low_confidence],
        "invalid_rows": bundle.invalid,
        "warnings": bundle.warnings,
    }


def write_index(bundle: FactCardBundle, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_index(bundle), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="事实卡 xlsx → public_facts / facts_index.json")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--out", default=None)
    parser.add_argument("--dump", action="store_true")
    args = parser.parse_args(argv)

    jobs: list[tuple[Path, Path]] = []
    if len(args.paths) == 1:
        jobs.append((Path(args.paths[0]), Path(args.out) if args.out else Path("data/facts/facts_index.json")))
    else:
        base = Path(args.out).parent if args.out else Path("data/facts")
        for raw in args.paths:
            source = Path(raw)
            if source.suffix.lower() not in (".xlsx", ".xlsm"):
                print(f"跳过非表格文件：{source}")
                continue
            stem = re.sub(r"_?事实卡.*$", "", source.stem) or source.stem
            jobs.append((source, base / f"facts_index_{stem}.json"))

    for source, out in jobs:
        bundle = load_factcard_file(source)
        print(f"\n=== {source.name} ===")
        print(json.dumps(bundle.summary(), ensure_ascii=False, indent=2))
        if bundle.warnings:
            print(f"警告 {len(bundle.warnings)} 条（前 5 条）：")
            for item in bundle.warnings[:5]:
                print("  -", item)
        if bundle.invalid:
            print(f"丢弃 {len(bundle.invalid)} 条（前 5 条）：")
            for item in bundle.invalid[:5]:
                print(f"  - {item['sheet']} 第{item['row']}行 {item['fact_id']}：{item['reason']}")
        print(f"索引已写入：{write_index(bundle, out)}")
        if args.dump:
            print(json.dumps(bundle.facts[:3], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

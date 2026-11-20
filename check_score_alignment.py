from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE_DIR = ROOT / "C 11.12 三指数"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from load_scenario_bridge import load_scenario

SCENARIO_DIR = ROOT / "scenario agent v2" / "data" / "scenarios"
SCENARIO_FILES = (
    "main_chip_controls.json",
    "backup_dst_bilateral.json",
    "no_zopa_variant.json",
)


def ranked_option_ids(scores: dict[str, float]) -> list[str]:
    return sorted(scores, key=lambda option_id: (-scores[option_id], option_id))


def compare_scenario(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    converted = load_scenario(path)
    converted_parties = [party["id"] for party in converted["parties"]]
    party_aliases = dict(zip(("P1", "P2"), converted_parties))
    clause_by_name = {clause["name"]: clause for clause in converted["clauses"]}
    rows = []

    for issue in raw["issues"]:
        if issue.get("type") != "enumerated":
            continue
        options = sorted(issue["options"], key=lambda option: option["order"])
        option_ids = [option["option_id"] for option in options]
        clause = clause_by_name[issue["name"]]
        adapted_scores = {
            option["id"]: option["score"] for option in clause["options"]
        }
        for raw_party, adapted_party in party_aliases.items():
            explicit = all(
                isinstance(option.get("score_by_party"), dict)
                and raw_party in option["score_by_party"]
                for option in options
            )
            if explicit:
                b_scores = {
                    option["option_id"]: option["score_by_party"][raw_party]
                    for option in options
                }
                source = "score_by_party"
            else:
                count = len(options)
                b_scores = {
                    option["option_id"]: (
                        (count - option["order"] + 1) / count
                        if raw_party == "P1"
                        else option["order"] / count
                    )
                    for option in options
                }
                source = "negotiability_order_fallback"
            adapter_scores = {
                option_id: adapted_scores[option_id][adapted_party]
                for option_id in option_ids
            }
            rows.append(
                {
                    "scenario_id": raw["scenario_id"],
                    "issue": issue["name"],
                    "party": raw_party,
                    "score_source": source,
                    "b_scores": b_scores,
                    "adapter_scores": adapter_scores,
                    "b_ranking": ranked_option_ids(b_scores),
                    "adapter_ranking": ranked_option_ids(adapter_scores),
                    "ranking_matches": ranked_option_ids(b_scores)
                    == ranked_option_ids(adapter_scores),
                    "scores_match": b_scores == adapter_scores,
                }
            )
    return rows


def main() -> None:
    rows = [
        row
        for filename in SCENARIO_FILES
        for row in compare_scenario(SCENARIO_DIR / filename)
    ]
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                "comparisons": len(rows),
                "ranking_mismatches": sum(not row["ranking_matches"] for row in rows),
                "score_mismatches": sum(not row["scores_match"] for row in rows),
                "explicit_score_by_party_rows": sum(
                    row["score_source"] == "score_by_party" for row in rows
                ),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
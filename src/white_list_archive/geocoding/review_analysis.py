from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

CANDIDATE_PREFIX = "matched_"


def _pct(value: float | None) -> float | None:
    return None if value is None else round(100.0 * value, 2)


def read_review_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "address_id",
        "review_stratum",
        "stratum_population",
        "stratum_sample",
        "sampling_weight",
        "review_verdict",
    }
    if not rows:
        raise ValueError("review CSV is empty")
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"review CSV missing columns: {sorted(missing)}")
    return rows


def analyse_review_rows(
    rows: Iterable[dict[str, str]],
    *,
    treat_not_found_as_coverage_failure: bool = False,
) -> dict[str, Any]:
    rows = list(rows)
    if not rows:
        raise ValueError("review rows are empty")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["review_stratum"])].append(row)

    strata: dict[str, dict[str, Any]] = {}
    total_population = 0
    candidate_population = 0
    candidate_sample = 0
    weighted_correct = 0.0
    weighted_determinate = 0.0
    candidate_unreviewed = 0

    for stratum, items in sorted(grouped.items()):
        populations = {int(item["stratum_population"]) for item in items}
        sample_sizes = {int(item["stratum_sample"]) for item in items}
        if len(populations) != 1 or len(sample_sizes) != 1:
            raise ValueError(f"inconsistent stratum metadata for {stratum}")
        population = populations.pop()
        expected_sample = sample_sizes.pop()
        if expected_sample != len(items):
            raise ValueError(
                f"stratum sample count mismatch for {stratum}: "
                f"{len(items)} rows != {expected_sample}"
            )
        total_population += population

        verdicts = [str(item.get("review_verdict") or "").strip() for item in items]
        correct = sum(v == "correct" for v in verdicts)
        incorrect = sum(v == "incorrect" for v in verdicts)
        uncertain = sum(v == "uncertain" for v in verdicts)
        blank = sum(v == "" for v in verdicts)
        determinate = correct + incorrect

        is_candidate = stratum.startswith(CANDIDATE_PREFIX)
        if is_candidate:
            candidate_population += population
            candidate_sample += len(items)
            candidate_unreviewed += blank
            for item, verdict in zip(items, verdicts):
                weight = float(item["sampling_weight"])
                if weight <= 0:
                    raise ValueError(f"non-positive sampling weight in {stratum}")
                if verdict == "correct":
                    weighted_correct += weight
                    weighted_determinate += weight
                elif verdict == "incorrect":
                    weighted_determinate += weight

        precision = correct / determinate if determinate else None
        strata[stratum] = {
            "population": population,
            "sample": len(items),
            "correct": correct,
            "incorrect": incorrect,
            "uncertain": uncertain,
            "blank": blank,
            "review_completion_pct": _pct((len(items) - blank) / len(items)),
            "determinate_precision_pct": _pct(precision),
            "is_candidate_stratum": is_candidate,
        }

    if candidate_unreviewed:
        raise ValueError(
            f"candidate review is incomplete: {candidate_unreviewed} candidate rows have no verdict"
        )

    candidate_precision = (
        weighted_correct / weighted_determinate if weighted_determinate else None
    )
    coverage = candidate_population / total_population if total_population else None
    validated_yield = (
        coverage * candidate_precision
        if coverage is not None and candidate_precision is not None
        else None
    )

    not_found = strata.get("not_found")
    not_found_population = int(not_found["population"]) if not_found else 0
    not_found_sample = int(not_found["sample"]) if not_found else 0
    not_found_blank = int(not_found["blank"]) if not_found else 0
    not_found_explicit_incorrect = int(not_found["incorrect"]) if not_found else 0

    return {
        "review_rows": len(rows),
        "population": total_population,
        "candidate_population": candidate_population,
        "candidate_sample_rows": candidate_sample,
        "candidate_review_complete": candidate_unreviewed == 0,
        "candidate_weighted_precision_pct": _pct(candidate_precision),
        "candidate_coverage_pct": _pct(coverage),
        "estimated_validated_yield_pct": _pct(validated_yield),
        "precision_excludes_not_found": True,
        "not_found_population": not_found_population,
        "not_found_sample_rows": not_found_sample,
        "not_found_explicit_incorrect_rows": not_found_explicit_incorrect,
        "not_found_unmarked_rows": not_found_blank,
        "not_found_effective_semantics": (
            "coverage_failure"
            if treat_not_found_as_coverage_failure
            else "reported_as_reviewed"
        ),
        "strata": strata,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Address review summary",
        "",
        f"- Population: **{summary['population']}**",
        f"- Candidate population: **{summary['candidate_population']} "
        f"({summary['candidate_coverage_pct']}%)**",
        f"- Candidate review rows: **{summary['candidate_sample_rows']}**",
        f"- Weighted candidate precision: **{summary['candidate_weighted_precision_pct']}%**",
        f"- Estimated validated end-to-end yield: **{summary['estimated_validated_yield_pct']}%**",
        f"- Not-found population: **{summary['not_found_population']}**",
        "",
        "## Strata",
        "",
        "| Stratum | Population | Sample | Correct | Incorrect | Uncertain | Blank | Precision |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in summary["strata"].items():
        precision = (
            "—"
            if item["determinate_precision_pct"] is None
            else f"{item['determinate_precision_pct']}%"
        )
        lines.append(
            f"| `{name}` | {item['population']} | {item['sample']} | "
            f"{item['correct']} | {item['incorrect']} | {item['uncertain']} | "
            f"{item['blank']} | {precision} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "`not_found` is excluded from precision because it is a coverage/recall outcome, "
            "not a returned false match. When configured as `coverage_failure`, it contributes "
            "to end-to-end yield rather than match precision.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarise a frozen manual address-review export."
    )
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--treat-not-found-as-coverage-failure", action="store_true")
    args = parser.parse_args()

    summary = analyse_review_rows(
        read_review_csv(args.review_csv),
        treat_not_found_as_coverage_failure=args.treat_not_found_as_coverage_failure,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "validation" / "pistoia"


def test_pistoia_review_metadata_and_candidate_decisions_are_frozen():
    metadata = json.loads(
        (DATA / "address-review-2026-09-09.metadata.json").read_text(encoding="utf-8")
    )
    assert metadata["prefecture"] == "Pistoia"
    assert metadata["region"] == "Toscana"
    assert metadata["canonical_source_backed_address_population"] == 287
    assert metadata["candidate_population"] == 5
    assert metadata["not_found_population"] == 282
    assert metadata["candidate_coverage_pct"] == 1.74
    assert metadata["review_sample"]["rows"] == 150
    assert metadata["review_sample"]["sample_sha256"] == (
        "df35ef283e07e2f166b969fbeb86618c04a63a8dbae97b661673431a1dfdde52"
    )
    assert metadata["review_sample"]["database_uuid_independent"] is True
    assert metadata["candidate_review"] == {
        "reviewed": 5,
        "correct": 5,
        "incorrect": 0,
        "candidate_precision_pct": 100.0,
        "civic_access": {"reviewed": 1, "correct": 1, "precision_pct": 100.0},
        "street": {"reviewed": 4, "correct": 4, "precision_pct": 100.0},
    }
    assert metadata["estimated_validated_end_to_end_yield_pct"] == 1.74
    assert "Do not introduce national automatic acceptance" in metadata[
        "production_policy_decision"
    ]

    with (DATA / "address-review-2026-09-09.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 5
    assert {row["review_verdict"] for row in rows} == {"correct"}
    assert sum(row["review_stratum"] == "matched_civic_access" for row in rows) == 1
    assert sum(row["review_stratum"] == "matched_street" for row in rows) == 4

"""Read-only strict source-parser QA for two exact historical Lodi originals.

This is a bounded compatibility assessment, not a new capture, edition approval,
semantic observation, canonical fact, or public release. The existing primary
R2 evidence store remains the only input: live URLs are never requested.
Only closed, aggregate, source-value-free diagnostics may leave the worker.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from white_list_archive.acquisition.historical_object_audit import PINS, MAX_EXPECTED_SOURCE_BYTES
from white_list_archive.parsers.lodi_sheets import parse_lodi_applicants, parse_lodi_listed


# The reviewed physical-parser contracts already live in lodi_sheets.py.
# Their existing observation-boundary labels are NOT administrative edition dates.
_TARGETS = (
    {
        "source_key": "lodi-listed", "scope": "lodi-listed-september",
        "sha256": PINS[0][1], "population_scope": "listed",
        "reference_date": "2026-09-27", "parser": "lodi_listed",
        "records": 169,
        "statuses": {"listed": 145, "renewal_update_in_progress": 24},
    },
    {
        "source_key": "lodi-applicants", "scope": "lodi-applicants-september",
        "sha256": PINS[1][1], "population_scope": "applicant",
        "reference_date": "2026-09-21", "parser": "lodi_applicants",
        "records": 6,
        "statuses": {"rejected_or_denied": 2, "pending": 4},
    },
)
_PARSERS = {"lodi-listed": parse_lodi_listed, "lodi-applicants": parse_lodi_applicants}


def _qualify_one(
    store: Any, cfg: dict | None, spec: dict, parser: Callable[[Path, dict], Any],
) -> dict[str, Any]:
    """Never expose parser exceptions, physical source rows, or private object keys."""
    answer = {
        "scope": spec["scope"], "status": "selection_unverified",
        "primary_bytes_verified": False, "strict_parser_compatible": False,
        "document_occurrences": None,
    }
    expected_cfg = {
        "source_key": spec["source_key"],
        "authority_key": "lodi",
        "population_scope": spec["population_scope"],
        "reference_date": spec["reference_date"],
        "sha256": spec["sha256"],
        "parser": spec["parser"],
    }
    if not isinstance(cfg, dict) or any(cfg.get(key) != value for key, value in expected_cfg.items()):
        return answer

    try:
        raw = store.read_digest_verified(spec["sha256"])
        if (type(raw) is not bytes or not 0 < len(raw) <= MAX_EXPECTED_SOURCE_BYTES
                or hashlib.sha256(raw).hexdigest() != spec["sha256"]):
            return {**answer, "status": "primary_bytes_unknown"}
    except Exception:
        return {**answer, "status": "primary_bytes_unknown"}

    answer = {**answer, "primary_bytes_verified": True, "status": "parser_review_required"}
    try:
        with TemporaryDirectory(prefix="lodi-source-qa-") as directory:
            source = Path(directory) / "frozen-source.csv"
            source.write_bytes(raw)
            batch = parser(source, cfg)
        statuses = Counter(record["source_status"] for record in batch.records)
        if (len(batch.records) != spec["records"]
                or dict(statuses) != spec["statuses"]
                or batch.diagnostics.get("status_counts") != spec["statuses"]):
            return answer
        return {
            **answer, "status": "strict_parser_compatible_source_only",
            "strict_parser_compatible": True, "document_occurrences": len(batch.records),
        }
    except Exception:
        # A parser error can contain an identifier, address or source row.
        return answer


def inspect_lodi_qualifications(store: Any, source_config: dict) -> dict[str, Any]:
    """Verify the existing reviewed parser against exactly two byte-pinned originals."""
    sources = source_config.get("sources") if isinstance(source_config, dict) else None
    if not isinstance(sources, list):
        sources = []
    selected: dict[str, dict] = {}
    duplicated = set()
    for cfg in sources:
        if isinstance(cfg, dict) and cfg.get("source_key") in _PARSERS:
            key = cfg["source_key"]
            if key in selected:
                duplicated.add(key)
            else:
                selected[key] = cfg
    results = [
        _qualify_one(
            store, None if spec["source_key"] in duplicated else selected.get(spec["source_key"]),
            spec, _PARSERS[spec["source_key"]],
        )
        for spec in _TARGETS
    ]
    return {
        "schema_version": 1,
        "checked_historical_sources": len(results),
        "primary_bytes_verified": sum(int(x["primary_bytes_verified"]) for x in results),
        "strict_parser_compatible_source_only": sum(int(x["strict_parser_compatible"]) for x in results),
        "results": results,
        "capture_catalogue_provenance_verified_by_this_check": False,
        "relational_source_observations_written": 0,
        "administrative_editions_approved": 0,
        "semantic_or_canonical_writes": 0,
        "public_promotions": 0,
    }


def main() -> int:
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for

    try:
        source_config = json.loads(
            Path("data/publication/multi_prefecture_pilot.json").read_text(encoding="utf-8")
        )
        store_config = StoreConfig.from_env()
        store = EvidenceStore(client_for(store_config), store_config)
        summary = inspect_lodi_qualifications(store, source_config)
    except Exception:
        # Unavailable provider/configuration never becomes parser acceptance.
        summary = inspect_lodi_qualifications(None, {})
    print(json.dumps(summary, sort_keys=True, allow_nan=False))
    # This read-only QA must not prevent independent reviewed-source transformations.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

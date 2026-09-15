from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = "https://prefettura.interno.gov.it/it/prefetture/torino/evidenza/white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/90/2026-09/w.l-11.09.2026.pdf"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/90/2026-09/w.l-11.09.2026-i.pdf"
LISTED_SHA = "5c8341cd984de01f6472e049b9fa22569798ebc41761e6f85763796c8a90ba0d"
APPLICANT_SHA = "f84d6da09090d557ba85cd216bc1e4962935f0f43ddb2614e77995b613ed2f51"


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one replacement in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def update_source_registry() -> None:
    path = ROOT / "data/source_registry/source_series_inventory.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise RuntimeError("Missing source-series header")
        rows = list(reader)

    matches = {row["source_series_key"]: row for row in rows if row["authority_key"] == "torino"}
    if set(matches) != {"torino-listed", "torino-applicants"}:
        raise RuntimeError(f"Unexpected Torino source-series set: {sorted(matches)!r}")

    listed = matches["torino-listed"]
    listed.update(
        {
            "population_scope": "listed",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": PAGE,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": "2026-09-15",
            "notes": (
                "Current official Torino page and White List provinciale PDF directly revalidated 15 September 2026 by independent byte-identical GETs. "
                "The byte-pinned 11 September edition yields exactly 1,501 listed-side observations: 1,237 listed and 264 renewal/update in progress. "
                "Seven reviewed malformed identifier fields, two activity-separator typography exceptions and eight legal-basis annotations are preserved without inferential repair; exact evidence is documented in docs/sources/torino-operational-check-2026-09-15.md."
            ),
        }
    )
    applicants = matches["torino-applicants"]
    applicants.update(
        {
            "population_scope": "applicant",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": PAGE,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": "2026-09-15",
            "notes": (
                "Current official Torino page and Elenco imprese richiedenti iscrizione PDF directly revalidated 15 September 2026 by independent byte-identical GETs. "
                "The byte-pinned 11 September edition yields exactly 162 positive pending applicant observations, all with strict identifiers and valid application dates; exact evidence is documented in docs/sources/torino-operational-check-2026-09-15.md."
            ),
        }
    )

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8")


def update_monitoring() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in data["prefectures"] if item.get("authority_key") == "torino"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Torino monitoring entry, found {len(matches)}")
    item = matches[0]
    if item.get("public_export_enabled") or item.get("parser_validated"):
        raise RuntimeError("Torino monitoring entry is already promoted; refusing duplicate transaction")
    item.update(
        {
            "official_landing_page": PAGE,
            "source_verified": True,
            "current_edition_identified": True,
            "capture_implemented": True,
            "parser_implemented": True,
            "parser_validated": True,
            "company_observations_loaded": True,
            "observation_layer": "public_source_observations",
            "canonical_integration_validated": False,
            "public_export_enabled": True,
            "durable_evidence_verified": False,
            "population_scopes_complete": True,
            "latest_source_reference_date": "2026-09-11",
            "last_successful_investigation_on": "2026-09-15",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/torino-operational-check-2026-09-15.md",
                "src/white_list_archive/parsers/torino_tables.py",
                "tests/test_torino_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/torino-operational-check-2026-09-15.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data["sources"]
    if any(item.get("authority_key") == "torino" for item in sources):
        raise RuntimeError("Torino already exists in publication configuration")
    common = {
        "authority_key": "torino",
        "authority_name": "Prefettura di Torino",
        "register_key": "torino-ordinary",
        "register_name": "White List — Prefettura di Torino",
        "reference_date": "2026-09-11",
        "last_source_update": "2026-09-11",
        "last_source_update_basis": "date embedded in the two current official resource filenames; used only as the source-edition boundary and not as an inferred company decision, registration or legal-effect date",
        "source_page_url": PAGE,
    }
    sources.extend(
        [
            {
                **common,
                "source_key": "torino-listed",
                "parser": "torino_listed",
                "population_scope": "listed",
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_source_rows": 1501,
                "notes": "Official White List provinciale PDF revalidated 15 September 2026 by two byte-identical independent GETs. The fail-closed 37-page parser yields exactly 1,501 listed-side observations: 1,237 listed and 264 renewal/update in progress. Strict identifier coverage is 1,496/1,501; reviewed raw identifier, activity-separator and legal-basis annotation exceptions remain source-faithful and uninferred.",
            },
            {
                **common,
                "source_key": "torino-applicants",
                "parser": "torino_applicants",
                "population_scope": "applicant",
                "resource_url": APPLICANT_URL,
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 162,
                "notes": "Official Elenco imprese richiedenti iscrizione PDF revalidated 15 September 2026 by two byte-identical independent GETs. The fail-closed seven-page parser yields exactly 162 pending applicant observations, all with strict identifiers and valid source application dates.",
            },
        ]
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bind_parser() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    replace_exact(
        path,
        "from white_list_archive.parsers.trento_tables import parse_trento_applicants, parse_trento_listed\n",
        "from white_list_archive.parsers.trento_tables import parse_trento_applicants, parse_trento_listed\nfrom white_list_archive.parsers.torino_tables import parse_torino_applicants, parse_torino_listed\n",
    )
    replace_exact(
        path,
        'TRENTO_PARSERS = {\n    "trento_listed": parse_trento_listed,\n    "trento_applicants": parse_trento_applicants,\n}\n',
        'TRENTO_PARSERS = {\n    "trento_listed": parse_trento_listed,\n    "trento_applicants": parse_trento_applicants,\n}\nTORINO_PARSERS = {\n    "torino_listed": parse_torino_listed,\n    "torino_applicants": parse_torino_applicants,\n}\n',
    )
    replace_exact(
        path,
        '        or TRENTO_PARSERS.get(cfg["parser"])\n',
        '        or TRENTO_PARSERS.get(cfg["parser"])\n        or TORINO_PARSERS.get(cfg["parser"])\n',
    )


def main() -> None:
    update_source_registry()
    update_monitoring()
    update_publication_config()
    bind_parser()
    print("Torino national candidate transaction applied to working tree")


if __name__ == "__main__":
    main()

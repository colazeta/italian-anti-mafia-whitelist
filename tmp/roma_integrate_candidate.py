from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement anchor, found {count}: {old!r}")
    write(path, text.replace(old, new, 1))


def rewrite_csv(path: str, key_field: str, key_value: str, updates: dict[str, str]) -> None:
    csv_path = ROOT / path
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise RuntimeError(f"{path}: missing CSV header")
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    matches = [row for row in rows if row.get(key_field) == key_value]
    if len(matches) != 1:
        raise RuntimeError(f"{path}: expected one {key_field}={key_value!r}, found {len(matches)}")
    unknown = set(updates) - set(fieldnames)
    if unknown:
        raise RuntimeError(f"{path}: update fields not in header: {sorted(unknown)!r}")
    matches[0].update(updates)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


# 1. Add the two byte-pinned official Roma publication inputs.
config_path = ROOT / "data/publication/multi_prefecture_pilot.json"
config = json.loads(config_path.read_text(encoding="utf-8"))
sources = config["sources"]
if any(source.get("authority_key") == "roma" for source in sources):
    raise RuntimeError("Roma is already present in publication config")

listed_page = "https://prefettura.interno.gov.it/it/prefetture/roma/white-list-elenco-imprese-iscritte"
applicant_page = "https://prefettura.interno.gov.it/it/prefetture/roma/white-list-elenco-imprese-richiedenti-iscrizione"
listed_url = "https://prefettura.interno.gov.it/sites/default/files/57/2026-09/elenco-imprese-iscritte-alla-white-list-aggiornato-alla-data-di-pubblicazione.pdf"
applicant_url = "https://prefettura.interno.gov.it/sites/default/files/57/2026-09/elenco-imprese-richiedenti-iscrizione-alla-white-list-aggiornato-alla-data-di-pubblicazione.pdf"
common = {
    "authority_key": "roma",
    "authority_name": "Prefettura di Roma",
    "register_key": "roma-ordinary",
    "register_name": "White List ordinaria",
    "reference_date": "2026-09-14",
    "last_source_update": "2026-09-14",
    "last_source_update_basis": "date printed in the official PDF footer on every page; used as the document reference boundary and not as an inferred legal publication timestamp for the webpage",
}
sources.extend(
    [
        {
            **common,
            "source_key": "roma-listed",
            "parser": "roma_positioned_listed",
            "population_scope": "listed",
            "source_page_url": listed_page,
            "resource_url": listed_url,
            "sha256": "8a2bbdb210757a8e7bf1da74db4bd7440c4fc45b3198b09e225c0aee2e6ef4af",
            "expected_source_rows": 2169,
            "notes": "Dedicated official registered-company page and 168-page PDF revalidated 15 September 2026. Independent retrievals were byte-identical. The positioned fail-closed parser yields exactly 2,169 observations (1,215 listed; 954 renewal/update in progress) and freezes the reviewed malformed/missing-date exceptions without inference. Exact evidence is documented in docs/sources/roma-operational-check-2026-09-15.md.",
        },
        {
            **common,
            "source_key": "roma-applicants",
            "parser": "roma_positioned_applicants",
            "population_scope": "applicant",
            "source_page_url": applicant_page,
            "resource_url": applicant_url,
            "sha256": "9bf34641f92b7480492646f0ab442b47305438a06547e1739dafd324c2b1b32a",
            "expected_source_rows": 2259,
            "notes": "Dedicated official applicant-company page and 142-page PDF revalidated 15 September 2026. Independent retrievals were byte-identical. The positioned fail-closed parser yields exactly 2,259 observations (2,256 pending; 3 explicit AGGIORNAMENTO IN CORSO) and freezes the reviewed malformed/missing application-date exceptions without inference. Exact evidence is documented in docs/sources/roma-operational-check-2026-09-15.md.",
        },
    ]
)
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 2. Refresh the already-qualified Roma source-series inventory rows without changing cardinality.
rewrite_csv(
    "data/source_registry/source_series_inventory.csv",
    "source_series_key",
    "roma-listed",
    {
        "publication_model": "linked_series_page",
        "series_url": listed_page,
        "resource_resolution_status": "direct_series_page_resolved",
        "verified_date": "2026-09-15",
        "notes": "Dedicated current official registered-company page revalidated 15 September 2026. Its current 168-page PDF is internally dated 14 September 2026 and byte-pinned at the approved SHA-256; the parser yields exactly 2,169 observations. Exact source identity and fail-closed parser boundary are documented in docs/sources/roma-operational-check-2026-09-15.md.",
    },
)
rewrite_csv(
    "data/source_registry/source_series_inventory.csv",
    "source_series_key",
    "roma-applicants",
    {
        "publication_model": "linked_series_page",
        "series_url": applicant_page,
        "resource_resolution_status": "direct_series_page_resolved",
        "verified_date": "2026-09-15",
        "notes": "Dedicated current official applicant-company page revalidated 15 September 2026. Its current 142-page PDF is internally dated 14 September 2026 and byte-pinned at the approved SHA-256; the parser yields exactly 2,259 observations. Exact source identity and fail-closed parser boundary are documented in docs/sources/roma-operational-check-2026-09-15.md.",
    },
)

# 3. Refresh the existing primary-page verification row in place.
rewrite_csv(
    "data/source_registry/verified_primary_pages.csv",
    "authority_key",
    "roma",
    {
        "landing_url": "https://prefettura.interno.gov.it/it/prefetture/roma/evidenza/white-list",
        "verification_date": "2026-09-15",
        "verification_status": "verified",
    },
)

# 4. Promote only the public-source observation layer. Canonical DB and durable evidence remain separate controls.
coverage_path = ROOT / "data/monitoring/national_coverage.json"
coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
matches = [item for item in coverage["prefectures"] if item.get("authority_key") == "roma"]
if len(matches) != 1:
    raise RuntimeError(f"Expected one Roma coverage row, found {len(matches)}")
row = matches[0]
if row.get("source_verified") is not True or row.get("population_scopes_complete") is not True:
    raise RuntimeError("Roma pre-integration source/population evidence is not in the expected positive state")
if row.get("canonical_integration_validated") is not False or row.get("durable_evidence_verified") is not False:
    raise RuntimeError("Roma infrastructure boundary drifted before public integration")
if row.get("public_export_enabled") is not False:
    raise RuntimeError("Roma unexpectedly public before candidate integration")
row.update(
    {
        "current_edition_identified": True,
        "capture_implemented": True,
        "parser_implemented": True,
        "parser_validated": True,
        "company_observations_loaded": True,
        "observation_layer": "public_source_observations",
        "public_export_enabled": True,
        "latest_source_reference_date": "2026-09-14",
        "last_successful_investigation_on": "2026-09-15",
        "unresolved_issue": [
            "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
        ],
        "actionable_issue": False,
        "coverage_status": "VALIDATED",
        "completion_evidence": [
            "docs/sources/roma-operational-check-2026-09-15.md",
            "src/white_list_archive/parsers/roma_positioned.py",
            "tests/test_roma_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        "known_content_sha256": [
            "8a2bbdb210757a8e7bf1da74db4bd7440c4fc45b3198b09e225c0aee2e6ef4af",
            "9bf34641f92b7480492646f0ab442b47305438a06547e1739dafd324c2b1b32a",
        ],
        "evidence": [
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/roma-operational-check-2026-09-15.md",
        ],
        "last_completed_coverage_stage": "VALIDATED",
    }
)
coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 5. Bind the audited Roma positioned parser into the recursively closed public registry with an explicit adapter.
registry_path = "src/white_list_archive/publishing/public_national_registry.py"
replace_once(
    registry_path,
    "from white_list_archive.parsers.lodi_sheets import PARSERS as LODI_PARSERS\n",
    "from white_list_archive.parsers.lodi_sheets import PARSERS as LODI_PARSERS\nfrom white_list_archive.parsers.roma_positioned import PARSERS as ROMA_PARSERS\n",
)
replace_once(
    registry_path,
    "\n\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n",
    '''\n\ndef _adapt_roma_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    """Project audited Roma positioned-PDF evidence onto the closed public source-field contract."""\n    adapted: list[dict[str, Any]] = []\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get("source_fields")\n        if not isinstance(fields, dict):\n            raise RuntimeError("Roma source_fields must be a mapping")\n        sections = record.get("requested_activities")\n        if not isinstance(sections, list) or any(not isinstance(value, str) for value in sections):\n            raise RuntimeError("Roma requested-activity/section type drift")\n        if parser_name == "roma_positioned_listed":\n            expected = {\n                "source_page", "source_row_on_page", "listing_date_raw",\n                "registration_protocol_raw", "expiry_date_raw", "sections_raw",\n                "note_raw", "reviewed_header_note_contamination",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f"Roma listed source-field drift: {sorted(fields)!r}")\n            if any(type(fields[key]) is not int for key in ("source_page", "source_row_on_page")):\n                raise RuntimeError("Roma listed source-locator type drift")\n            if type(fields["reviewed_header_note_contamination"]) is not bool:\n                raise RuntimeError("Roma listed reviewed-header flag type drift")\n            for key in ("listing_date_raw", "registration_protocol_raw", "expiry_date_raw", "sections_raw", "note_raw"):\n                if not isinstance(fields[key], str):\n                    raise RuntimeError(f"Roma listed source-field scalar drift: {key}")\n            update_raw = fields["note_raw"] if record.get("source_status") == "renewal_update_in_progress" else ""\n            record["source_fields"] = {\n                "sections": list(sections),\n                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],\n                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],\n                "in_aggiornamento": update_raw,\n            }\n        elif parser_name == "roma_positioned_applicants":\n            expected = {\n                "source_page", "source_row_on_page", "application_date_raw",\n                "sections_raw", "note_raw",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f"Roma applicant source-field drift: {sorted(fields)!r}")\n            if any(type(fields[key]) is not int for key in ("source_page", "source_row_on_page")):\n                raise RuntimeError("Roma applicant source-locator type drift")\n            for key in ("application_date_raw", "sections_raw", "note_raw"):\n                if not isinstance(fields[key], str):\n                    raise RuntimeError(f"Roma applicant source-field scalar drift: {key}")\n            record["source_fields"] = {\n                "sections": list(sections),\n                "requested_activities_source": fields["sections_raw"],\n                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],\n                "in_aggiornamento": fields["note_raw"],\n            }\n        else:\n            raise RuntimeError(f"Unexpected Roma parser: {parser_name!r}")\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n\n\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n''',
)
replace_once(
    registry_path,
    '        or LODI_PARSERS.get(cfg["parser"])\n',
    '        or LODI_PARSERS.get(cfg["parser"])\n        or ROMA_PARSERS.get(cfg["parser"])\n',
)
replace_once(
    registry_path,
    '    if cfg["parser"] in LODI_PARSERS:\n        batch = _adapt_lodi_public_fields(batch, cfg["parser"])\n',
    '    if cfg["parser"] in LODI_PARSERS:\n        batch = _adapt_lodi_public_fields(batch, cfg["parser"])\n    if cfg["parser"] in ROMA_PARSERS:\n        batch = _adapt_roma_public_fields(batch, cfg["parser"])\n',
)

print("Roma candidate production integration applied fail-closed")

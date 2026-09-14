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


# 1. Add the two byte-pinned official publication inputs.
config_path = ROOT / "data/publication/multi_prefecture_pilot.json"
config = json.loads(config_path.read_text(encoding="utf-8"))
sources = config["sources"]
if any(source.get("authority_key") == "lodi" for source in sources):
    raise RuntimeError("Lodi is already present in publication config")

page = "https://prefettura.interno.gov.it/it/prefetture/lodi/evidenza/white-list"
listed_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSTOZ3x5FBo4IanDtISccAnqZmVLPmGhEYaj0YrDn4aP6ZpwY8kzpiHhAX0i26IwipgD6bvsWhSigwz/pub?gid=0&single=true&output=csv"
applicant_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSTOZ3x5FBo4IanDtISccAnqZmVLPmGhEYaj0YrDn4aP6ZpwY8kzpiHhAX0i26IwipgD6bvsWhSigwz/pub?gid=245180329&single=true&output=csv"
common = {
    "authority_key": "lodi",
    "authority_name": "Prefettura di Lodi",
    "register_key": "lodi-ordinary",
    "register_name": "White List ordinaria",
    "reference_date": "2026-09-15",
    "source_page_url": page,
    "last_source_update": "2026-09-15",
    "last_source_update_basis": "observation/capture date of the mutable official Google Sheets publication; the sheet does not expose a reliable edition date, so no publication date is inferred",
}
sources.extend(
    [
        {
            **common,
            "source_key": "lodi-listed",
            "parser": "lodi_listed",
            "population_scope": "listed",
            "resource_url": listed_url,
            "sha256": "ad64ab8669084bc31b80938a384b41849be4db28b448e9b2c0ce199f6af1d6ec",
            "expected_source_rows": 169,
            "notes": "Official mutable Google Sheet linked by the Prefettura di Lodi. Two independent bounded GETs on 15 September 2026 were byte-identical. The fail-closed parser freezes 324 physical rows and 291 statutory-section membership rows, then conservatively groups exact identifier/date/status peers into 169 public observations (146 listed; 23 renewal/update in progress) while retaining all section memberships and source variants. Exact evidence is documented in docs/sources/lodi-operational-check-2026-09-15.md.",
        },
        {
            **common,
            "source_key": "lodi-applicants",
            "parser": "lodi_applicants",
            "population_scope": "applicant",
            "resource_url": applicant_url,
            "sha256": "55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228",
            "expected_source_rows": 4,
            "notes": "Official applicant tab linked by the Prefettura di Lodi. Two independent bounded GETs on 15 September 2026 were byte-identical. Four positively identified observations are present: two explicit denials with source-explicit decision dates and two records explicitly in istruttoria. No applicant status or completeness is inferred from failed search. Exact evidence is documented in docs/sources/lodi-operational-check-2026-09-15.md.",
        },
    ]
)
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 2. Refresh the already-qualified source-series inventory rows without changing cardinality.
rewrite_csv(
    "data/source_registry/source_series_inventory.csv",
    "source_series_key",
    "lodi-listed",
    {
        "publication_model": "linked_series_page",
        "series_url": page,
        "resource_resolution_status": "landing_page_resolved",
        "verified_date": "2026-09-15",
        "notes": "Official Lodi landing page directly revalidated 15 September 2026 and positively exposes the registered-company Google Sheet tab. Repeat CSV exports are byte-identical at the approved SHA-256; 291 statutory-section membership rows group conservatively to 169 public observations. Exact source identity and parser boundary are documented in docs/sources/lodi-operational-check-2026-09-15.md.",
    },
)
rewrite_csv(
    "data/source_registry/source_series_inventory.csv",
    "source_series_key",
    "lodi-applicants",
    {
        "publication_model": "linked_series_page",
        "series_url": page,
        "resource_resolution_status": "landing_page_resolved",
        "verified_date": "2026-09-15",
        "notes": "Official Lodi landing page directly revalidated 15 September 2026 and positively exposes the requesting-company Google Sheet tab. Repeat CSV exports are byte-identical at the approved SHA-256; four positively identified applicant observations are present (two explicit denials and two in istruttoria). Exact evidence is documented in docs/sources/lodi-operational-check-2026-09-15.md.",
    },
)

# 3. Refresh the existing primary-page verification row in place.
rewrite_csv(
    "data/source_registry/verified_primary_pages.csv",
    "authority_key",
    "lodi",
    {
        "landing_url": page,
        "verification_date": "2026-09-15",
        "verification_status": "verified",
    },
)

# 4. Promote only the public-source observation layer. Canonical DB and durable evidence remain separate controls.
coverage_path = ROOT / "data/monitoring/national_coverage.json"
coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
matches = [item for item in coverage["prefectures"] if item.get("authority_key") == "lodi"]
if len(matches) != 1:
    raise RuntimeError(f"Expected one Lodi coverage row, found {len(matches)}")
row = matches[0]
if row.get("source_verified") is not True or row.get("population_scopes_complete") is not True:
    raise RuntimeError("Lodi pre-integration source/population evidence is not in the expected positive state")
if row.get("canonical_integration_validated") is not False or row.get("durable_evidence_verified") is not False:
    raise RuntimeError("Lodi infrastructure boundary drifted before public integration")
if row.get("public_export_enabled") is not False:
    raise RuntimeError("Lodi unexpectedly public before candidate integration")
row.update(
    {
        "current_edition_identified": True,
        "capture_implemented": True,
        "parser_implemented": True,
        "parser_validated": True,
        "company_observations_loaded": True,
        "observation_layer": "public_source_observations",
        "public_export_enabled": True,
        "latest_source_reference_date": "2026-09-15",
        "last_successful_investigation_on": "2026-09-15",
        "unresolved_issue": [
            "The official Google Sheet is mutable and exposes no reliable edition date; 2026-09-15 is the byte-pinned observation/capture boundary, not an inferred publication date.",
            "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure.",
        ],
        "actionable_issue": False,
        "coverage_status": "VALIDATED",
        "completion_evidence": [
            "docs/sources/lodi-operational-check-2026-09-15.md",
            "src/white_list_archive/parsers/lodi_sheets.py",
            "tests/test_lodi_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        "known_content_sha256": [
            "ad64ab8669084bc31b80938a384b41849be4db28b448e9b2c0ce199f6af1d6ec",
            "55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228",
        ],
        "evidence": [
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/lodi-operational-check-2026-09-15.md",
        ],
        "last_completed_coverage_stage": "VALIDATED",
    }
)
coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 5. Bind the audited parser family into the recursively closed public registry with an explicit adapter.
registry_path = "src/white_list_archive/publishing/public_national_registry.py"
replace_once(
    registry_path,
    "from white_list_archive.parsers.trento_tables import parse_trento_applicants, parse_trento_listed\n",
    "from white_list_archive.parsers.trento_tables import parse_trento_applicants, parse_trento_listed\nfrom white_list_archive.parsers.lodi_sheets import PARSERS as LODI_PARSERS\n",
)
replace_once(
    registry_path,
    "\n\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n",
    '''\n\ndef _adapt_lodi_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    """Project audited Lodi evidence onto the recursively closed public source-field contract."""\n    adapted: list[dict[str, Any]] = []\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get("source_fields")\n        if not isinstance(fields, dict):\n            raise RuntimeError("Lodi source_fields must be a mapping")\n        if parser_name == "lodi_listed":\n            expected = {\n                "sections", "source_memberships", "name_variants",\n                "registered_office_variants", "secondary_office_variants",\n                "identifier_raw_variants", "listing_date_raw", "expiry_date_raw",\n                "update_raw",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f"Lodi listed source-field drift: {sorted(fields)!r}")\n            for key in (\n                "sections", "name_variants", "registered_office_variants",\n                "secondary_office_variants", "identifier_raw_variants",\n            ):\n                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):\n                    raise RuntimeError(f"Lodi listed source-list type drift: {key}")\n            memberships = fields["source_memberships"]\n            if not isinstance(memberships, list) or not memberships or any(not isinstance(value, dict) for value in memberships):\n                raise RuntimeError("Lodi listed source-membership type/cardinality drift")\n            expected_membership = {\n                "source_row", "section", "name_raw", "registered_office_raw",\n                "secondary_office_raw", "identifier_raw", "listing_date_raw",\n                "expiry_date_raw", "update_raw",\n            }\n            for membership in memberships:\n                if set(membership) != expected_membership or type(membership["source_row"]) is not int:\n                    raise RuntimeError("Lodi listed source-membership shape drift")\n                if any(not isinstance(membership[key], str) for key in expected_membership - {"source_row"}):\n                    raise RuntimeError("Lodi listed source-membership scalar drift")\n            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw", "update_raw")):\n                raise RuntimeError("Lodi listed raw scalar type drift")\n            record["source_fields"] = {\n                "sections": list(fields["sections"]),\n                "registered_office_variants": list(fields["registered_office_variants"]),\n                "secondary_office_variants": list(fields["secondary_office_variants"]),\n                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],\n                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],\n                "in_aggiornamento": fields["update_raw"],\n            }\n        elif parser_name == "lodi_applicants":\n            expected = {"source_row", "activities_raw", "application_date_raw", "outcome_raw"}\n            if set(fields) != expected or type(fields["source_row"]) is not int:\n                raise RuntimeError("Lodi applicant source-field shape drift")\n            if any(not isinstance(fields[key], str) for key in ("activities_raw", "application_date_raw", "outcome_raw")):\n                raise RuntimeError("Lodi applicant source-field scalar drift")\n            record["source_fields"] = {\n                "requested_activities_source": fields["activities_raw"],\n                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],\n            }\n        else:\n            raise RuntimeError(f"Unexpected Lodi parser: {parser_name!r}")\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n\n\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n''',
)
replace_once(
    registry_path,
    '        or TRENTO_PARSERS.get(cfg["parser"])\n',
    '        or TRENTO_PARSERS.get(cfg["parser"])\n        or LODI_PARSERS.get(cfg["parser"])\n',
)
replace_once(
    registry_path,
    '    if cfg["parser"] in TRENTO_PARSERS:\n        batch = _adapt_trento_public_fields(batch, cfg["parser"])\n',
    '    if cfg["parser"] in TRENTO_PARSERS:\n        batch = _adapt_trento_public_fields(batch, cfg["parser"])\n    if cfg["parser"] in LODI_PARSERS:\n        batch = _adapt_lodi_public_fields(batch, cfg["parser"])\n',
)

print("Lodi candidate production integration applied fail-closed")

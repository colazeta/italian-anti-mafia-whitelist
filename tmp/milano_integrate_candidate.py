from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = "https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list"
RESOURCE = "https://whitelist.prefmi.it/elenco/elenco.php"
SHA256 = "350e995ac06fc9525c1bd21cc2e2ad8b69224e4dd603e530a65553c21f44b044"
REGISTERED_SIBLING_SHA256 = "81226e37aa744a8907f4de70121e46362ceb0177259e3de076f2eb15ebaafb7e"
REFERENCE_DATE = "2026-09-16"
SOURCE_NOTE = "docs/sources/milano-operational-check-2026-09-16.md"


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one replacement in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def update_verified_page() -> None:
    path = ROOT / "data/source_registry/verified_primary_pages.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise RuntimeError("Missing verified-page header")
        rows = list(reader)
    matches = [row for row in rows if row["authority_key"] == "milano"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Milano verified-page row, found {len(matches)}")
    row = matches[0]
    if row["landing_url"] != PAGE or row["verification_status"] != "verified":
        raise RuntimeError(f"Unexpected Milano verified-page state: {row!r}")
    row["verification_date"] = REFERENCE_DATE
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8")


def update_source_registry() -> None:
    path = ROOT / "data/source_registry/source_series_inventory.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise RuntimeError("Missing source-series header")
        rows = list(reader)
    matches = [row for row in rows if row["authority_key"] == "milano"]
    if len(matches) != 1 or matches[0]["source_series_key"] != "milano-listed":
        raise RuntimeError(
            "Milano source-series pre-state drift: "
            f"{[(row['source_series_key'], row['population_scope']) for row in matches]!r}"
        )
    row = matches[0]
    row.update(
        {
            "source_series_key": "milano-combined",
            "authority_key": "milano",
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "listed_and_applicant",
            "sector_scope": "all",
            "publication_model": "custom_web_application",
            "series_url": PAGE,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": REFERENCE_DATE,
            "notes": (
                "Current official Prefettura di Milano application directly revalidated 16 September 2026. "
                "The live combined operational table was captured twice with byte-identical no-cache GETs and positively publishes listed, renewal/update and first-time applicant rows, including applications dated through 15 September 2026. "
                "The byte-pinned HTML contains 4,214 statutory-sector membership rows yielding 2,614 conservative logical observations; the registered-only sibling view was independently stable at SHA-256 "
                f"{REGISTERED_SIBLING_SHA256} and is not co-ingested because it overlaps the combined non-pending population. Exact evidence is documented in {SOURCE_NOTE}."
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
    matches = [item for item in data["prefectures"] if item.get("authority_key") == "milano"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Milano monitoring entry, found {len(matches)}")
    item = matches[0]
    if item.get("public_export_enabled") or item.get("parser_validated"):
        raise RuntimeError("Milano monitoring entry is already promoted; refusing duplicate transaction")
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
            "latest_source_reference_date": REFERENCE_DATE,
            "last_successful_source_check_at": "2026-09-16T05:09:32Z",
            "last_attempted_source_check_at": "2026-09-16T05:09:32Z",
            "last_successful_investigation_on": REFERENCE_DATE,
            "monitoring_status": "CURRENT",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                SOURCE_NOTE,
                "src/white_list_archive/parsers/milano_webapp.py",
                "tests/test_milano_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [SHA256],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                SOURCE_NOTE,
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data["sources"]
    if any(item.get("authority_key") == "milano" for item in sources):
        raise RuntimeError("Milano already exists in publication configuration")
    sources.append(
        {
            "source_key": "milano-combined",
            "parser": "milano_combined",
            "authority_key": "milano",
            "authority_name": "Prefettura di Milano",
            "register_key": "milano-ordinary",
            "register_name": "White List — Prefettura di Milano",
            "population_scope": "listed_and_applicant",
            "reference_date": REFERENCE_DATE,
            "source_page_url": PAGE,
            "resource_url": RESOURCE,
            "sha256": SHA256,
            "expected_sector_rows": 4214,
            "expected_source_rows": 2614,
            "last_source_update": REFERENCE_DATE,
            "last_source_update_basis": (
                "current mutable official web application captured and independently revalidated on this date; "
                "the date is a capture/reference boundary only and is not an inferred company event or legal-effect date"
            ),
            "notes": (
                "Official combined operational table revalidated 16 September 2026 by two byte-identical no-cache GETs. "
                "The fail-closed parser expands source colspan geometry and yields exactly 2,614 logical observations from 4,214 sector rows: "
                "940 listed, 516 renewal/update in progress and 1,158 pending. All 2,614 source identifiers are strict; all observations have explicit statutory activity coverage; "
                "all pending observations have explicit application dates and all listed observations have explicit listing/expiry dates. The registered-only sibling surface is not co-ingested to avoid duplicate/conflicting presentations of the same non-pending company identities."
            ),
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bind_parser_and_public_contract() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    replace_exact(
        path,
        "from white_list_archive.parsers.sassari_openxml import PARSERS as SASSARI_PARSERS\n",
        "from white_list_archive.parsers.sassari_openxml import PARSERS as SASSARI_PARSERS\nfrom white_list_archive.parsers.milano_webapp import PARSERS as MILANO_PARSERS\n",
    )
    replace_exact(
        path,
        '        or SASSARI_PARSERS.get(cfg["parser"])\n',
        '        or SASSARI_PARSERS.get(cfg["parser"])\n        or MILANO_PARSERS.get(cfg["parser"])\n',
    )
    adapter = '''\n\ndef _adapt_milano_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    """Project audited Milano HTML evidence onto the closed public source-field contract."""\n    if parser_name != "milano_combined":\n        raise RuntimeError(f"Unexpected Milano parser: {parser_name!r}")\n    adapted: list[dict[str, Any]] = []\n    expected = {\n        "sections", "section_headings", "physical_locators",\n        "status_or_listing_raw", "expiry_raw", "note",\n    }\n    request_re = re.compile(r"^RICHIESTA\\s+ISCRIZIONE\\s*\\((\\d{2}/\\d{2}/\\d{4})\\)$", re.I)\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get("source_fields")\n        if not isinstance(fields, dict) or set(fields) != expected:\n            raise RuntimeError(f"Milano source-field drift: {sorted(fields) if isinstance(fields, dict) else fields!r}")\n        sections = fields["sections"]\n        headings = fields["section_headings"]\n        locators = fields["physical_locators"]\n        if (\n            not isinstance(sections, list)\n            or not isinstance(headings, list)\n            or not isinstance(locators, list)\n            or any(not isinstance(value, str) for value in sections + headings + locators)\n            or not (len(sections) == len(headings) == len(locators))\n        ):\n            raise RuntimeError("Milano section/source-locator type or cardinality drift")\n        first = fields["status_or_listing_raw"]\n        expiry = fields["expiry_raw"]\n        note = fields["note"]\n        if any(not isinstance(value, str) for value in (first, expiry, note)):\n            raise RuntimeError("Milano raw source-field type drift")\n        status = record.get("source_status")\n        listing_raw: list[str] = []\n        application_raw: list[str] = []\n        expiry_raw: list[str] = []\n        in_aggiornamento = ""\n        if status == "listed":\n            if not first or not expiry:\n                raise RuntimeError("Milano listed row lost raw listing/expiry evidence")\n            listing_raw = [first]\n            expiry_raw = [expiry]\n        elif status == "pending":\n            match = request_re.fullmatch(first)\n            if match is None or expiry:\n                raise RuntimeError("Milano pending row lost request-label semantics")\n            application_raw = [match.group(1)]\n        elif status == "renewal_update_in_progress":\n            if first.casefold() != "in aggiornamento" or expiry:\n                raise RuntimeError("Milano renewal/update row lost explicit update semantics")\n            in_aggiornamento = first\n        else:\n            raise RuntimeError(f"Milano unapproved public status: {status!r}")\n        record["source_fields"] = {\n            "sections": list(sections),\n            "physical_locators": list(locators),\n            "notes": [note] if note else [],\n            "listing_date_raw_variants": listing_raw,\n            "application_date_raw_variants": application_raw,\n            "expiry_date_raw_variants": expiry_raw,\n            "in_aggiornamento": in_aggiornamento,\n        }\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n'''
    replace_exact(
        path,
        "\ndef _adapt_bolzano_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n",
        adapter + "\ndef _adapt_bolzano_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n",
    )
    replace_exact(
        path,
        '    batch = parser(path, cfg)\n    if cfg["parser"] in BOLZANO_PARSERS:\n',
        '    batch = parser(path, cfg)\n    if cfg["parser"] in MILANO_PARSERS:\n        batch = _adapt_milano_public_fields(batch, cfg["parser"])\n    if cfg["parser"] in BOLZANO_PARSERS:\n',
    )


def update_population_regression() -> None:
    path = ROOT / "tests/test_source_population_coverage.py"
    replace_exact(path, '    assert report["complete_register_scope_count"] == 47\n', '    assert report["complete_register_scope_count"] == 48\n')
    replace_exact(path, '    assert report["incomplete_register_scope_count"] == 1\n', '    assert report["incomplete_register_scope_count"] == 0\n')
    marker = '    assert all(row["covering_series_keys"] == ["sassari-combined"] for row in sassari)\n'
    addition = marker + '\n    milano = [\n        row\n        for row in report["rows"]\n        if row["authority_key"] == "milano"\n        and row["regime_code"] == "WL-REGIME-L190-2012"\n    ]\n    assert {row["coverage_status"] for row in milano} == {"COVERED_COMBINED_SERIES"}\n    assert all(row["covering_series_keys"] == ["milano-combined"] for row in milano)\n'
    replace_exact(path, marker, addition)
    old = '''    milano = {\n        row["population_target"]: row\n        for row in report["rows"]\n        if row["authority_key"] == "milano"\n    }\n    assert milano["listed"]["coverage_status"] == "COVERED_SEPARATE_SERIES"\n    assert milano["applicant"]["coverage_status"] == "UNRESOLVED_REQUIRES_REVIEW"\n\n    unresolved = {\n        row["authority_key"]\n        for row in report["scopes"]\n        if not row["source_population_complete"]\n    }\n    assert unresolved == {"milano"}\n'''
    new = '''    unresolved = {\n        row["authority_key"]\n        for row in report["scopes"]\n        if not row["source_population_complete"]\n    }\n    assert unresolved == set()\n'''
    replace_exact(path, old, new)


def main() -> None:
    update_verified_page()
    update_source_registry()
    update_monitoring()
    update_publication_config()
    bind_parser_and_public_contract()
    update_population_regression()
    print("Milano national candidate transaction applied to working tree")


if __name__ == "__main__":
    main()

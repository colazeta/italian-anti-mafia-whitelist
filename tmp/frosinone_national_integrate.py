from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LISTED_SHA = "aad166b49393055a197b9b1fef4eba82d0a70453a90d84209f967180d2855d71"
APPLICANT_SHA = "9906d55864f4c1dc8e027efa2b44fa2c6463c512fb34241a32aa9b21a5ba6db8"
LANDING = "https://prefettura.interno.gov.it/it/prefetture/frosinone/evidenza/white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/9/2026-09/elenco-societa-iscritte-white-list-al-2-settembre-2026-aggiornato.pdf"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/9/2026-09/elenco-ric-iscr-white-list-aggiornato-al-2-settembre-2026-ordine-alfabetico-ok.pdf"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one marker, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def append_csv_row(path: Path, row: list[str]) -> None:
    with path.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(row)


validation_path = ROOT / "tmp/frosinone_parser_validation.json"
validation = json.loads(validation_path.read_text(encoding="utf-8"))
assert validation["validation"] == "passed"
assert validation["capture_sha256"] == {"listed": LISTED_SHA, "applicants": APPLICANT_SHA}
assert validation["combined_public_records"] == 1236
assert validation["combined_status_counts"] == {
    "renewal_update_in_progress": 232,
    "listed": 529,
    "pending": 475,
}
assert validation["listed"]["continuation_fragments_joined"] == 44
assert validation["applicants"]["continuation_fragments_joined"] == 5

coverage_path = ROOT / "data/monitoring/national_coverage.json"
coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
rows = [row for row in coverage["prefectures"] if row["authority_key"] == "frosinone"]
if len(rows) != 1:
    raise RuntimeError(f"Expected one Frosinone coverage row, found {len(rows)}")
row = rows[0]
expected_initial = {
    "source_verified": False,
    "current_edition_identified": None,
    "capture_implemented": False,
    "parser_implemented": False,
    "parser_validated": False,
    "company_observations_loaded": False,
    "observation_layer": None,
    "public_export_enabled": False,
    "population_scopes_complete": False,
    "latest_source_reference_date": None,
    "last_successful_investigation_on": None,
    "coverage_status": "SOURCE_IDENTIFIED",
    "known_content_sha256": [],
}
for key, expected in expected_initial.items():
    if row.get(key) != expected:
        raise RuntimeError(f"Frosinone coverage baseline drift for {key}: {row.get(key)!r} != {expected!r}")
row.update(
    {
        "source_verified": True,
        "current_edition_identified": True,
        "capture_implemented": True,
        "parser_implemented": True,
        "parser_validated": True,
        "company_observations_loaded": True,
        "observation_layer": "public_source_observations",
        "public_export_enabled": True,
        "population_scopes_complete": True,
        "latest_source_reference_date": "2026-09-02",
        "last_successful_investigation_on": "2026-09-13",
        "unresolved_issue": [
            "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
        ],
        "actionable_issue": False,
        "coverage_status": "VALIDATED",
        "completion_evidence": [
            "docs/sources/frosinone-operational-check-2026-09-13.md",
            "src/white_list_archive/parsers/frosinone_tables.py",
            "tests/test_frosinone_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
        "evidence": [
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/frosinone-operational-check-2026-09-13.md",
        ],
        "last_completed_coverage_stage": "VALIDATED",
    }
)
write_json(coverage_path, coverage)

pages_path = ROOT / "data/source_registry/verified_primary_pages.csv"
page_rows = list(csv.DictReader(io.StringIO(pages_path.read_text(encoding="utf-8"))))
if any(r["authority_key"] == "frosinone" for r in page_rows):
    raise RuntimeError("Frosinone already present in verified_primary_pages.csv")
append_csv_row(pages_path, ["frosinone", LANDING, "2026-09-13", "verified"])

series_path = ROOT / "data/source_registry/source_series_inventory.csv"
series_rows = list(csv.DictReader(io.StringIO(series_path.read_text(encoding="utf-8"))))
existing_keys = {r["source_series_key"] for r in series_rows}
if {"frosinone-listed", "frosinone-applicants"} & existing_keys:
    raise RuntimeError("Frosinone source-series key already present")
append_csv_row(
    series_path,
    [
        "frosinone-listed",
        "frosinone",
        "WL-REGIME-L190-2012",
        "listed",
        "all",
        "periodic_attachment",
        LANDING,
        "landing_page_resolved",
        "2026-09-13",
        "Current official landing page and listed-company PDF directly revalidated 13 September 2026. The byte-pinned 91-page edition updated 2 September 2026 yields exactly 761 observations: 529 listed and 232 renewal/update in progress. Forty-four continuation row fragments belong to forty logical company records; malformed official dates and raw identifiers remain uninferred.",
    ],
)
append_csv_row(
    series_path,
    [
        "frosinone-applicants",
        "frosinone",
        "WL-REGIME-L190-2012",
        "applicant",
        "all",
        "periodic_attachment",
        LANDING,
        "landing_page_resolved",
        "2026-09-13",
        "Current official landing page and applicant PDF directly revalidated 13 September 2026. The byte-pinned 37-page edition updated 2 September 2026 yields exactly 475 pending observations. Five continuation fragments, including one reviewed identifier continuation, are handled fail-closed; malformed source dates and blank outcome cells remain raw and uninferred.",
    ],
)

catalog_path = ROOT / "data/catalog.csv"
replace_once(
    catalog_path,
    "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,41,false,internal_research",
    "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,42,false,internal_research",
)
replace_once(
    catalog_path,
    "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,77,false,internal_research",
    "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,79,false,internal_research",
)

pubcfg_path = ROOT / "data/publication/multi_prefecture_pilot.json"
pubcfg = json.loads(pubcfg_path.read_text(encoding="utf-8"))
if any(s["authority_key"] == "frosinone" for s in pubcfg["sources"]):
    raise RuntimeError("Frosinone already present in publication config")
pubcfg["sources"].extend(
    [
        {
            "authority_key": "frosinone",
            "authority_name": "Prefettura di Frosinone",
            "register_key": "frosinone-ordinary",
            "register_name": "White List ordinaria",
            "source_page_url": LANDING,
            "source_key": "frosinone-listed",
            "parser": "frosinone_listed",
            "population_scope": "listed",
            "reference_date": "2026-09-02",
            "resource_url": LISTED_URL,
            "sha256": LISTED_SHA,
            "expected_source_rows": 761,
            "last_source_update": "2026-09-02",
            "last_source_update_basis": "dated official resource directly revalidated and byte-pinned 13 September 2026",
            "notes": "Byte-pinned 91-page listed-company PDF. The fail-closed parser yields exactly 761 observations: 529 listed and 232 renewal/update in progress. Forty-four continuation row fragments attach to 40 logical records; eight reviewed malformed official dates remain raw and uninferred.",
        },
        {
            "authority_key": "frosinone",
            "authority_name": "Prefettura di Frosinone",
            "register_key": "frosinone-ordinary",
            "register_name": "White List ordinaria",
            "source_page_url": LANDING,
            "source_key": "frosinone-applicants",
            "parser": "frosinone_applicants",
            "population_scope": "applicant",
            "reference_date": "2026-09-02",
            "resource_url": APPLICANT_URL,
            "sha256": APPLICANT_SHA,
            "expected_source_rows": 475,
            "last_source_update": "2026-09-02",
            "last_source_update_basis": "dated official resource directly revalidated and byte-pinned 13 September 2026",
            "notes": "Byte-pinned 37-page applicant PDF. The fail-closed parser yields exactly 475 pending observations. Five continuation fragments, two reviewed malformed dates and four blank outcome cells are preserved under explicit invariants without inferred repair.",
        },
    ]
)
write_json(pubcfg_path, pubcfg)

registry_path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
replace_once(
    registry_path,
    "from white_list_archive.parsers.forli_cesena_combined import parse_forli_cesena_combined\n",
    "from white_list_archive.parsers.forli_cesena_combined import parse_forli_cesena_combined\n"
    "from white_list_archive.parsers.frosinone_tables import parse_frosinone_applicants, parse_frosinone_listed\n",
)
replace_once(
    registry_path,
    'FORLI_CESENA_PARSERS = {"forli_cesena_combined": parse_forli_cesena_combined}\n',
    'FORLI_CESENA_PARSERS = {"forli_cesena_combined": parse_forli_cesena_combined}\n'
    "FROSINONE_PARSERS = {\n"
    '    "frosinone_listed": parse_frosinone_listed,\n'
    '    "frosinone_applicants": parse_frosinone_applicants,\n'
    "}\n",
)
adapter_lines = [
    "",
    "",
    "def _adapt_frosinone_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:",
    '    """Project audited Frosinone evidence onto the closed public source-field contract."""',
    "    adapted: list[dict[str, Any]] = []",
    "    for source_record in batch.records:",
    "        record = dict(source_record)",
    '        fields = record.get("source_fields")',
    "        if not isinstance(fields, dict):",
    '            raise RuntimeError("Frosinone source_fields must be a mapping")',
    '        if parser_name == "frosinone_listed":',
    "            expected = {",
    '                "source_locator", "continuation_fragments", "identifier_raw",',
    '                "listing_date_raw", "expiry_date_raw", "sections_raw", "note_raw",',
    "            }",
    "            if set(fields) != expected:",
    '                raise RuntimeError(f"Frosinone listed source-field drift: {sorted(fields)!r}")',
    '            scalar_keys = ("source_locator", "identifier_raw", "listing_date_raw", "expiry_date_raw", "sections_raw", "note_raw")',
    "            if any(not isinstance(fields[key], str) for key in scalar_keys):",
    '                raise RuntimeError("Frosinone listed source-field type drift")',
    '            fragments = fields["continuation_fragments"]',
    "            if not isinstance(fragments, list):",
    '                raise RuntimeError("Frosinone listed continuation-fragment type drift")',
    "            for fragment in fragments:",
    '                if not isinstance(fragment, dict) or set(fragment) != {"source_locator", "cells", "before"}:',
    '                    raise RuntimeError("Frosinone listed continuation-fragment shape drift")',
    '                if not isinstance(fragment["source_locator"], str):',
    '                    raise RuntimeError("Frosinone listed continuation locator type drift")',
    '                for key in ("cells", "before"):',
    '                    if not isinstance(fragment[key], list) or len(fragment[key]) != 7 or any(not isinstance(value, str) for value in fragment[key]):',
    '                        raise RuntimeError(f"Frosinone listed continuation {key} drift")',
    '            record["source_fields"] = {',
    '                "sections": [fields["sections_raw"]] if fields["sections_raw"] else [],',
    '                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],',
    '                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],',
    "            }",
    '        elif parser_name == "frosinone_applicants":',
    "            expected = {",
    '                "source_locator", "continuation_fragments", "identifier_raw",',
    '                "sections_raw", "application_date_raw", "outcome_raw",',
    "            }",
    "            if set(fields) != expected:",
    '                raise RuntimeError(f"Frosinone applicant source-field drift: {sorted(fields)!r}")',
    '            scalar_keys = ("source_locator", "identifier_raw", "sections_raw", "application_date_raw", "outcome_raw")',
    "            if any(not isinstance(fields[key], str) for key in scalar_keys):",
    '                raise RuntimeError("Frosinone applicant source-field type drift")',
    '            fragments = fields["continuation_fragments"]',
    "            if not isinstance(fragments, list):",
    '                raise RuntimeError("Frosinone applicant continuation-fragment type drift")',
    "            for fragment in fragments:",
    '                if not isinstance(fragment, dict) or set(fragment) != {"source_locator", "cells", "before"}:',
    '                    raise RuntimeError("Frosinone applicant continuation-fragment shape drift")',
    '                if not isinstance(fragment["source_locator"], str):',
    '                    raise RuntimeError("Frosinone applicant continuation locator type drift")',
    '                for key in ("cells", "before"):',
    '                    if not isinstance(fragment[key], list) or len(fragment[key]) != 7 or any(not isinstance(value, str) for value in fragment[key]):',
    '                        raise RuntimeError(f"Frosinone applicant continuation {key} drift")',
    '            record["source_fields"] = {',
    '                "sections": [fields["sections_raw"]] if fields["sections_raw"] else [],',
    '                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],',
    "            }",
    "        else:",
    '            raise RuntimeError(f"Unexpected Frosinone parser: {parser_name!r}")',
    "        adapted.append(record)",
    "    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)",
    "",
]
adapter = "\n".join(adapter_lines)
replace_once(
    registry_path,
    "\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n",
    adapter + "\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n",
)
replace_once(
    registry_path,
    '        or FORLI_CESENA_PARSERS.get(cfg["parser"])\n',
    '        or FORLI_CESENA_PARSERS.get(cfg["parser"])\n        or FROSINONE_PARSERS.get(cfg["parser"])\n',
)
replace_once(
    registry_path,
    '    if cfg["parser"] in FOGGIA_PARSERS:\n        batch = _adapt_foggia_public_fields(batch, cfg["parser"])\n',
    '    if cfg["parser"] in FOGGIA_PARSERS:\n        batch = _adapt_foggia_public_fields(batch, cfg["parser"])\n'
    '    if cfg["parser"] in FROSINONE_PARSERS:\n        batch = _adapt_frosinone_public_fields(batch, cfg["parser"])\n',
)

semantic_test = ROOT / "tests/test_frosinone_parser_semantics.py"
if semantic_test.exists():
    raise RuntimeError("Frosinone semantic test already exists")
semantic_lines = [
    "from __future__ import annotations",
    "",
    "import pytest",
    "",
    "from white_list_archive.parsers.frosinone_tables import (",
    "    _EXPECTED_APPLICANT_FRAGMENT_ROWS,",
    "    _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE,",
    "    _EXPECTED_APPLICANT_RAW_IDENTIFIER_ONLY,",
    "    _EXPECTED_APPLICANT_RECORDS,",
    "    _EXPECTED_APPLICANT_STATUS_COUNTS,",
    "    _EXPECTED_LISTED_FRAGMENT_ROWS,",
    "    _EXPECTED_LISTED_IDENTIFIER_COVERAGE,",
    "    _EXPECTED_LISTED_RAW_IDENTIFIER_ONLY,",
    "    _EXPECTED_LISTED_RECORDS,",
    "    _EXPECTED_LISTED_STATUS_COUNTS,",
    "    _listed_status,",
    "    _parse_date,",
    "    _strict_identifiers,",
    ")",
    "",
    "",
    "def test_frosinone_source_denominators_are_frozen() -> None:",
    "    assert _EXPECTED_LISTED_RECORDS == 761",
    '    assert _EXPECTED_LISTED_STATUS_COUNTS == {"listed": 529, "renewal_update_in_progress": 232}',
    "    assert _EXPECTED_LISTED_FRAGMENT_ROWS == 44",
    "    assert _EXPECTED_LISTED_IDENTIFIER_COVERAGE == 737",
    "    assert _EXPECTED_LISTED_RAW_IDENTIFIER_ONLY == 24",
    "    assert _EXPECTED_APPLICANT_RECORDS == 475",
    '    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 475}',
    "    assert _EXPECTED_APPLICANT_FRAGMENT_ROWS == 5",
    "    assert _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE == 473",
    "    assert _EXPECTED_APPLICANT_RAW_IDENTIFIER_ONLY == 2",
    "",
    "",
    "def test_frosinone_listed_status_vocabulary_is_fail_closed() -> None:",
    '    assert _listed_status("") == "listed"',
    '    assert _listed_status("Aggiornamento in corso per richiesta a permanere del 11/02/2026") == "renewal_update_in_progress"',
    '    with pytest.raises(RuntimeError, match="unreviewed listed note/status"):',
    '        _listed_status("RINNOVO IN CORSO")',
    "",
    "",
    "def test_frosinone_dates_are_never_repaired() -> None:",
    '    assert _parse_date("02/09/2026") == "2026-09-02"',
    '    assert _parse_date("30/07/*2026") == ""',
    '    assert _parse_date("224/02/2027") == ""',
    '    assert _parse_date("24/02/20270") == ""',
    '    assert _parse_date("13/05/206") == ""',
    "",
    "",
    "def test_frosinone_identifiers_are_never_repaired() -> None:",
    '    assert _strict_identifiers("03332660608") == ["03332660608"]',
    '    assert _strict_identifiers("PGLLNZ94D01I838U") == ["PGLLNZ94D01I838U"]',
    '    assert _strict_identifiers("0543034730") == []',
    '    assert _strict_identifiers("003332660608") == []',
]
semantic_test.write_text("\n".join(semantic_lines) + "\n", encoding="utf-8")

pop_test = ROOT / "tests/test_source_population_coverage.py"
replace_once(pop_test, 'assert report["verified_authority_count"] == 41', 'assert report["verified_authority_count"] == 42')
replace_once(pop_test, 'assert report["register_scope_count"] == 42', 'assert report["register_scope_count"] == 43')
replace_once(pop_test, 'assert report["complete_register_scope_count"] == 40', 'assert report["complete_register_scope_count"] == 41')
registry_test = ROOT / "tests/test_source_registry.py"
replace_once(registry_test, "assert len(pages) == 41", "assert len(pages) == 42")

browser = ROOT / "tests/public_portal_browser.cjs"
replace_once(
    browser,
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Forlì-Cesena'));\n",
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Forlì-Cesena'));\n"
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Frosinone'));\n",
)
replace_once(browser, "      assert.equal(stats.total,31307);", "      assert.equal(stats.total,32543);")
replace_once(
    browser,
    "'foggia','forli-cesena'].includes(r.authority_key)",
    "'foggia','forli-cesena','frosinone'].includes(r.authority_key)",
)
replace_once(
    browser,
    "      assert.deepEqual(statusCounts(forli),{listed:401,pending:144,renewal_update_in_progress:204});\n",
    "      assert.deepEqual(statusCounts(forli),{listed:401,pending:144,renewal_update_in_progress:204});\n"
    "      const frosinone=registry.records.filter(r=>r.authority_key==='frosinone');\n"
    "      assert.equal(frosinone.length,1236);\n"
    "      assert.equal(frosinone.filter(r=>r.source_key==='frosinone-listed').length,761);\n"
    "      assert.equal(frosinone.filter(r=>r.source_key==='frosinone-applicants').length,475);\n"
    "      assert.deepEqual(statusCounts(frosinone),{listed:529,pending:475,renewal_update_in_progress:232});\n"
    "      assert.equal(frosinone.filter(r=>r.source_fields&&Array.isArray(r.source_fields.listing_date_raw_variants)&&r.source_fields.listing_date_raw_variants.includes('30/07/*2026')&&r.observed_listing_date==='').length,1);\n"
    "      assert.equal(frosinone.filter(r=>r.source_fields&&Array.isArray(r.source_fields.application_date_raw_variants)&&r.source_fields.application_date_raw_variants.includes('13/05/206')&&r.application_date==='').length,1);\n",
)

print("Frosinone production transaction staged")

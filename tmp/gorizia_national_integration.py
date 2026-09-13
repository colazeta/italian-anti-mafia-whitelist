from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/gorizia/evidenza/white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/gorizia-elenco-ditte-iscritte-wl.docx"
APPLICANTS_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/2026.08-white-list-ditte-richiedenti-iscrizione.pdf"
LISTED_SHA = "680f0822f56ce7499a5d3f6c9e524d3d33b631feca51886e57e70fdf9e5fbd6d"
APPLICANTS_SHA = "befe7ed054e0cfe9dda48c8dec59f843b569019e40b925d6d5d1fcec19021c7c"


def read_csv(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"integration anchor drift: {label}")
    return text.replace(old, new, 1)


# Publication config: two positively evidenced populations, one statutory register.
publication_path = ROOT / "data/publication/multi_prefecture_pilot.json"
publication = json.loads(publication_path.read_text(encoding="utf-8"))
if any(source.get("authority_key") == "gorizia" for source in publication["sources"]):
    raise RuntimeError("Gorizia publication config already present unexpectedly")
publication["sources"].extend([
    {
        "authority_key": "gorizia",
        "authority_name": "Prefettura di Gorizia",
        "register_key": "gorizia-ordinary",
        "register_name": "White List ordinaria",
        "source_page_url": LANDING,
        "source_key": "gorizia-listed",
        "parser": "gorizia_listed",
        "population_scope": "listed",
        "reference_date": "2026-09-13",
        "resource_url": LISTED_URL,
        "sha256": LISTED_SHA,
        "expected_source_rows": 117,
        "expected_sector_rows": 186,
        "last_source_update": "2026-08-17",
        "last_source_update_basis": "official landing page last updated 17 August 2026; attachment itself is undated; current bytes repeat-fetched and byte-pinned 13 September 2026",
        "notes": "Byte-pinned DOCX with 10 physical sector tables and 186 sector rows. The fail-closed parser groups only exact source tuples into 117 observations: 86 listed and 31 renewal/update in progress. Two exact blank-expiry registrations and reviewed malformed/split date lexemes are preserved under explicit invariants without inferential repair.",
    },
    {
        "authority_key": "gorizia",
        "authority_name": "Prefettura di Gorizia",
        "register_key": "gorizia-ordinary",
        "register_name": "White List ordinaria",
        "source_page_url": LANDING,
        "source_key": "gorizia-applicants",
        "parser": "gorizia_applicants",
        "population_scope": "applicant",
        "reference_date": "2026-09-13",
        "resource_url": APPLICANTS_URL,
        "sha256": APPLICANTS_SHA,
        "expected_source_rows": 10,
        "last_source_update": "2026-08-17",
        "last_source_update_basis": "official landing page last updated 17 August 2026; attachment itself is undated; current bytes repeat-fetched and byte-pinned 13 September 2026",
        "notes": "Byte-pinned two-page applicant PDF. The fail-closed parser binds exactly ten positively verified identifier/name anchors in source order and yields ten pending observations; blank application dates remain blank and are never inferred.",
    },
])
publication_path.write_text(json.dumps(publication, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Verified official page and complete source-series inventory.
pages_path = ROOT / "data/source_registry/verified_primary_pages.csv"
pages, page_fields = read_csv(pages_path)
if any(row["authority_key"] == "gorizia" for row in pages):
    raise RuntimeError("Gorizia verified page already present unexpectedly")
pages.append({"authority_key": "gorizia", "landing_url": LANDING, "verification_date": "2026-09-13", "verification_status": "verified"})
write_csv(pages_path, pages, page_fields)

series_path = ROOT / "data/source_registry/source_series_inventory.csv"
series, series_fields = read_csv(series_path)
if any(row["authority_key"] == "gorizia" for row in series):
    raise RuntimeError("Gorizia source series already present unexpectedly")
series.extend([
    {
        "source_series_key": "gorizia-listed", "authority_key": "gorizia", "regime_code": "WL-REGIME-L190-2012", "population_scope": "listed", "sector_scope": "all", "publication_model": "periodic_attachment", "series_url": LANDING, "resource_resolution_status": "landing_page_resolved", "verified_date": "2026-09-13",
        "notes": f"Official landing page revalidated 13 September 2026. Listed DOCX is byte-pinned at SHA-256 {LISTED_SHA} and yields exactly 117 grouped observations from 186 sector rows: 86 listed and 31 renewal/update in progress; exact reviewed blank-expiry and malformed-date evidence remains fail-closed.",
    },
    {
        "source_series_key": "gorizia-applicants", "authority_key": "gorizia", "regime_code": "WL-REGIME-L190-2012", "population_scope": "applicant", "sector_scope": "all", "publication_model": "periodic_attachment", "series_url": LANDING, "resource_resolution_status": "landing_page_resolved", "verified_date": "2026-09-13",
        "notes": f"Official landing page revalidated 13 September 2026. Applicant PDF is byte-pinned at SHA-256 {APPLICANTS_SHA} and yields exactly ten pending observations from ten positively verified identifier/name anchors.",
    },
])
write_csv(series_path, series, series_fields)
if len(pages) != 43 or len(series) != 81:
    raise RuntimeError(f"source denominator drift: pages={len(pages)} series={len(series)}")

catalog_path = ROOT / "data/catalog.csv"
catalog, catalog_fields = read_csv(catalog_path)
by_id = {row["dataset_id"]: row for row in catalog}
by_id["verified-primary-pages"]["record_count"] = str(len(pages))
by_id["source-series-inventory"]["record_count"] = str(len(series))
write_csv(catalog_path, catalog, catalog_fields)

# Coverage state records public-source integration conservatively; hosted canonical integration remains separately governed.
coverage_path = ROOT / "data/monitoring/national_coverage.json"
coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
matches = [row for row in coverage["prefectures"] if row["authority_key"] == "gorizia"]
if len(matches) != 1:
    raise RuntimeError(f"expected one Gorizia coverage row, got {len(matches)}")
entry = matches[0]
entry.update({
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
    "latest_source_reference_date": "2026-09-13",
    "last_successful_investigation_on": "2026-09-13",
    "unresolved_issue": ["Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."],
    "actionable_issue": False,
    "coverage_status": "VALIDATED",
    "terminal_reason": None,
    "completion_evidence": ["docs/sources/gorizia-operational-check-2026-09-13.md", "src/white_list_archive/parsers/gorizia_tables.py", "tests/test_gorizia_parser_semantics.py", "data/publication/multi_prefecture_pilot.json"],
    "known_content_sha256": [LISTED_SHA, APPLICANTS_SHA],
    "evidence": ["data/source_registry/verified_primary_pages.csv", "data/source_registry/source_series_inventory.csv", "data/publication/multi_prefecture_pilot.json", "docs/sources/gorizia-operational-check-2026-09-13.md"],
    "last_completed_coverage_stage": "VALIDATED",
})
coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Public parser dispatch and explicit closed-contract adapter.
registry_path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
registry = registry_path.read_text(encoding="utf-8")
registry = replace_once(
    registry,
    "from white_list_archive.parsers.frosinone_tables import parse_frosinone_applicants, parse_frosinone_listed\nfrom white_list_archive.publishing.public_contract import public_record, validate_registry\n",
    "from white_list_archive.parsers.frosinone_tables import parse_frosinone_applicants, parse_frosinone_listed\nfrom white_list_archive.parsers.gorizia_tables import parse_gorizia_applicants, parse_gorizia_listed\nfrom white_list_archive.publishing.public_contract import public_record, validate_registry\n",
    "Gorizia parser import",
)
registry = replace_once(
    registry,
    'FROSINONE_PARSERS = {\n    "frosinone_listed": parse_frosinone_listed,\n    "frosinone_applicants": parse_frosinone_applicants,\n}\n',
    'FROSINONE_PARSERS = {\n    "frosinone_listed": parse_frosinone_listed,\n    "frosinone_applicants": parse_frosinone_applicants,\n}\nGORIZIA_PARSERS = {\n    "gorizia_listed": parse_gorizia_listed,\n    "gorizia_applicants": parse_gorizia_applicants,\n}\n',
    "Gorizia parser map",
)
adapter = '''\n\ndef _adapt_gorizia_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    """Project audited Gorizia evidence onto the closed public source-field contract."""\n    adapted: list[dict[str, Any]] = []\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get("source_fields")\n        if not isinstance(fields, dict):\n            raise RuntimeError("Gorizia source_fields must be a mapping")\n        if parser_name == "gorizia_listed":\n            expected = {"source_rows", "sections", "identifier_raw", "listing_date_raw", "expiry_date_raw", "update_values"}\n            if set(fields) != expected:\n                raise RuntimeError(f"Gorizia listed source-field drift: {sorted(fields)!r}")\n            if not isinstance(fields["source_rows"], list) or any(not isinstance(item, list) or len(item) != 2 or any(type(value) is not int for value in item) for item in fields["source_rows"]):\n                raise RuntimeError("Gorizia listed source-row cardinality drift")\n            if not isinstance(fields["sections"], list) or any(type(value) is not int for value in fields["sections"]):\n                raise RuntimeError("Gorizia listed section type drift")\n            if not isinstance(fields["update_values"], list) or any(not isinstance(value, str) for value in fields["update_values"]):\n                raise RuntimeError("Gorizia listed update type drift")\n            for key in ("identifier_raw", "listing_date_raw", "expiry_date_raw"):\n                if not isinstance(fields[key], str):\n                    raise RuntimeError(f"Gorizia listed source-field type drift: {key}")\n            record["source_fields"] = {\n                "sections": [f"Sezione {section}" for section in fields["sections"]],\n                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],\n                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],\n                "in_aggiornamento": " · ".join(value for value in fields["update_values"] if value),\n            }\n        elif parser_name == "gorizia_applicants":\n            expected = {"page", "identifier_raw", "application_date_raw"}\n            if set(fields) != expected or type(fields["page"]) is not int or any(not isinstance(fields[key], str) for key in ("identifier_raw", "application_date_raw")):\n                raise RuntimeError("Gorizia applicant source-field drift")\n            raw = fields["application_date_raw"]\n            record["source_fields"] = {"application_date_raw_variants": [raw] if raw else []}\n        else:\n            raise RuntimeError(f"Unexpected Gorizia parser: {parser_name!r}")\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n'''
registry = replace_once(registry, "\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n", adapter + "\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n", "Gorizia public adapter")
registry = replace_once(registry, '        or FROSINONE_PARSERS.get(cfg["parser"])\n    )\n', '        or FROSINONE_PARSERS.get(cfg["parser"])\n        or GORIZIA_PARSERS.get(cfg["parser"])\n    )\n', "Gorizia parser dispatch")
registry = replace_once(registry, '    if cfg["parser"] in FROSINONE_PARSERS:\n        batch = _adapt_frosinone_public_fields(batch, cfg["parser"])\n    for record in batch.records:\n', '    if cfg["parser"] in FROSINONE_PARSERS:\n        batch = _adapt_frosinone_public_fields(batch, cfg["parser"])\n    if cfg["parser"] in GORIZIA_PARSERS:\n        batch = _adapt_gorizia_public_fields(batch, cfg["parser"])\n    for record in batch.records:\n', "Gorizia adapter dispatch")
registry_path.write_text(registry, encoding="utf-8")

# Permanent semantic regression tests.
(ROOT / "tests/test_gorizia_parser_semantics.py").write_text('''from __future__ import annotations\n\nimport pytest\n\nfrom white_list_archive.parsers.gorizia_tables import (\n    _EXPECTED_APPLICANT_IDENTIFIERS, _EXPECTED_APPLICANT_NAMES,\n    _EXPECTED_LISTED_REGISTRATIONS, _EXPECTED_LISTED_SECTOR_ROWS,\n    _EXPECTED_LISTED_STATUS_COUNTS, _REVIEWED_BLANK_EXPIRY_ROWS,\n    _normalise_italian_date,\n)\n\ndef test_gorizia_source_denominators_are_frozen() -> None:\n    assert _EXPECTED_LISTED_SECTOR_ROWS == 186\n    assert _EXPECTED_LISTED_REGISTRATIONS == 117\n    assert _EXPECTED_LISTED_STATUS_COUNTS == {"listed": 86, "renewal_update_in_progress": 31}\n    assert len(_EXPECTED_APPLICANT_IDENTIFIERS) == 10\n    assert len(_EXPECTED_APPLICANT_NAMES) == 10\n    assert len(_REVIEWED_BLANK_EXPIRY_ROWS) == 2\n\ndef test_gorizia_date_handling_is_fail_closed() -> None:\n    assert _normalise_italian_date("24.06.2025") == "2025-06-24"\n    assert _normalise_italian_date("1° giugno 2027") == "2027-06-01"\n    assert _normalise_italian_date("2 1 aprile 2026") == "2026-04-21"\n    assert _normalise_italian_date("Dal 10.12.202") == ""\n    assert _normalise_italian_date("14 agosto 204") == ""\n    with pytest.raises(RuntimeError, match="unexpected date lexeme"):\n        _normalise_italian_date("10-12-2026")\n''', encoding="utf-8")

source_test = ROOT / "tests/test_source_registry.py"
text = source_test.read_text(encoding="utf-8")
source_test.write_text(replace_once(text, "assert len(pages) == 42", "assert len(pages) == 43", "verified page denominator"), encoding="utf-8")
coverage_test = ROOT / "tests/test_source_population_coverage.py"
text = coverage_test.read_text(encoding="utf-8")
for old, new, label in [
    ('assert report["verified_authority_count"] == 42', 'assert report["verified_authority_count"] == 43', "coverage verified authorities"),
    ('assert report["register_scope_count"] == 43', 'assert report["register_scope_count"] == 44', "coverage register scopes"),
    ('assert report["complete_register_scope_count"] == 41', 'assert report["complete_register_scope_count"] == 42', "coverage complete scopes"),
]:
    text = replace_once(text, old, new, label)
coverage_test.write_text(text, encoding="utf-8")

# Correct source documentation to the final byte-pinned parser facts.
doc_path = ROOT / "docs/sources/gorizia-operational-check-2026-09-13.md"
doc = doc_path.read_text(encoding="utf-8")
old_blank = 'The pinned DOCX also contains exactly one positively reviewed source row with a blank `Data scadenza iscrizione`: `“ MAROLLI COSTRUZIONI SRL”`, MONFALCONE (GO) Viale San Marco, 13/B, `C.F./P.I. 01218760310`, listing date `29 dicembre 2022` (section 2, source row 9). The parser permits a blank expiry only for this exact reviewed name/office/identifier/listing tuple, preserves the blank raw and normalised expiry, and fails closed on any additional blank-expiry row; publication in the listed series is retained as the only positive status evidence.'
new_blank = 'The pinned DOCX contains exactly two positively reviewed registration signatures with a blank `Data scadenza iscrizione`: `“ MAROLLI COSTRUZIONI SRL”`, MONFALCONE (GO) Viale San Marco, 13/B, `C.F./P.I. 01218760310`, listing date `29 dicembre 2022`; and `PEVERE LOGISTICA SRL`, GORIZIA Via Gregorcic snc, `00546290313`, listing date `30 luglio 2026`. The parser permits blank expiry only for this exact reviewed two-signature set, validates the observed set rather than a loose row count, preserves blank raw and normalised expiry values, and fails closed on any missing or additional signature; publication in the listed series is retained as the only positive status evidence.'
doc = replace_once(doc, old_blank, new_blank, "blank-expiry documentation")
doc = replace_once(doc, '`[blank]`; `24.06.2025`; `21.04.2026`; `17.02.2026`; `17.02.2026`; `[blank]`; `14.04.2026`; `[blank]`; `01.04.2026`; `[blank]`.', '`[blank]`; `24.06.2025`; `21.04.2026`; `17.02.2026`; `17.02.2026`; `14.04.2026`; `[blank]`; `[blank]`; `01.04.2026`; `[blank]`.', "applicant date sequence")
doc = replace_once(doc, "Subject to the byte-pinned parser-validation gate, the current Gorizia parser candidate is:", "The byte-pinned transactional parser validation completed successfully, including two independent downloads of each official attachment, exact SHA-256 checks and the full repository test suite. The validated Gorizia parser output is:", "parser-validation status")
doc_path.write_text(doc, encoding="utf-8")

# Permanent public portal gate.
pages_workflow = ROOT / ".github/workflows/public-pages.yml"
workflow = pages_workflow.read_text(encoding="utf-8")
for old, new, label in [
    ("      - 'src/white_list_archive/parsers/frosinone_tables.py'\n", "      - 'src/white_list_archive/parsers/frosinone_tables.py'\n      - 'src/white_list_archive/parsers/gorizia_tables.py'\n", "Pages parser trigger"),
    ("assert reg['meta']['record_count'] == 32543", "assert reg['meta']['record_count'] == 32670", "Pages record count"),
    ("'forli-cesena','frosinone'}", "'forli-cesena','frosinone','gorizia'}", "Pages authority set"),
    ("'forli-cesena-ordinary','frosinone-ordinary'", "'forli-cesena-ordinary','frosinone-ordinary','gorizia-ordinary'", "Pages register set"),
    ("assert reg['meta']['authority_count'] == 33", "assert reg['meta']['authority_count'] == 34", "Pages authority count"),
    ("assert reg['meta']['register_count'] == 34", "assert reg['meta']['register_count'] == 35", "Pages register count"),
    ("assert pref['meta']['published_count'] == 33", "assert pref['meta']['published_count'] == 34", "Pages published count"),
    ("assert pref['meta']['mapped_count'] == 42", "assert pref['meta']['mapped_count'] == 43", "Pages mapped count"),
]:
    workflow = replace_once(workflow, old, new, label)
workflow = replace_once(workflow, "          assert len(frosinone) == 1 and frosinone[0]['mapped'] and frosinone[0]['published'] and frosinone[0]['series_count'] == 2\n", "          assert len(frosinone) == 1 and frosinone[0]['mapped'] and frosinone[0]['published'] and frosinone[0]['series_count'] == 2\n          gorizia = [x for x in pref['prefectures'] if x['authority_key'] == 'gorizia']\n          assert len(gorizia) == 1 and gorizia[0]['mapped'] and gorizia[0]['published'] and gorizia[0]['series_count'] == 2\n", "Pages Gorizia row")
pages_workflow.write_text(workflow, encoding="utf-8")

print({"verified_pages": len(pages), "source_series": len(series), "gorizia_sources": 2, "candidate_records": 32670, "candidate_authorities": 34, "candidate_registers": 35, "candidate_mapped": 43})

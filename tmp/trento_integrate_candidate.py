from __future__ import annotations

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


# 1. Add the two byte-pinned publication inputs. Fail closed if Trento is already integrated.
config_path = ROOT / "data/publication/multi_prefecture_pilot.json"
config = json.loads(config_path.read_text(encoding="utf-8"))
sources = config["sources"]
if any(source.get("authority_key") == "trento" for source in sources):
    raise RuntimeError("Trento is already present in publication config")

authority = "Commissariato del Governo per la Provincia di Trento"
sources.extend(
    [
        {
            "authority_key": "trento",
            "authority_name": authority,
            "register_key": "trento-ordinary",
            "register_name": "White List ordinaria",
            "reference_date": "2026-09-11",
            "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/trento/white-list-elenco-imprese-iscritte",
            "last_source_update": "2026-09-11",
            "last_source_update_basis": "dedicated official registered-company page updated 11 September 2026 and exposing the current edition; exact bytes repeat-fetched and SHA-256 pinned during parser validation on 14 September 2026",
            "source_key": "trento-listed",
            "parser": "trento_listed",
            "population_scope": "listed",
            "resource_url": "https://prefettura.interno.gov.it/sites/default/files/86/2026-09/imprese-iscritte-11-settembre-2026.pdf",
            "sha256": "b831570c01220b8709ebf9c4dbdfe856aba37a21c46353cf7bc9eedb5965c8af",
            "expected_source_rows": 1366,
            "notes": "Byte-pinned 289-page registered-company PDF. The fail-closed parser freezes 3,208 physical table rows and 3,020 statutory-section rows, then conservatively groups repeated section memberships into exactly 1,366 public observations (699 listed; 667 renewal/update in progress). Reviewed split-table geometry, 172 continuation fragments, source text variants, one malformed date and identifier exceptions remain source-bound without inferential repair.",
        },
        {
            "authority_key": "trento",
            "authority_name": authority,
            "register_key": "trento-ordinary",
            "register_name": "White List ordinaria",
            "reference_date": "2026-09-10",
            "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/trento/white-list-elenco-imprese-richiedenti",
            "last_source_update": "2026-09-10",
            "last_source_update_basis": "dedicated official requesting-company page updated 10 September 2026 and exposing the current edition; exact bytes repeat-fetched and SHA-256 pinned during parser validation on 14 September 2026",
            "source_key": "trento-applicants",
            "parser": "trento_applicants",
            "population_scope": "applicant",
            "resource_url": "https://prefettura.interno.gov.it/sites/default/files/86/2026-09/imprese-richiedenti-10-settembre-2026.pdf",
            "sha256": "9f36797e3e11834c979f9b5f5d58d693e19fa2456c69ce5859628d4e56a056c0",
            "expected_source_rows": 98,
            "notes": "Byte-pinned 22-page requesting-company PDF. Exhaustive source review freezes 117 physical rows, 17 continuation fragments and exactly 98 logical applicant observations; all 98 source Esito cells are blank and therefore classify as pending on positive complete-population evidence. One reviewed application-date cell also carries a separately preserved integration date.",
        },
    ]
)
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 2. Refresh the already-qualified Trento source-series rows without changing inventory cardinality.
replace_once(
    "data/source_registry/source_series_inventory.csv",
    'trento-applicants,trento,WL-REGIME-L190-2012,applicant,all,periodic_attachment,https://prefettura.interno.gov.it/it/prefetture/trento/white-list-elenco-imprese-richiedenti,direct_series_page_resolved,2026-09-07,"Dedicated applicant page exposes the current list, updated 1 September 2026."',
    'trento-applicants,trento,WL-REGIME-L190-2012,applicant,all,periodic_attachment,https://prefettura.interno.gov.it/it/prefetture/trento/white-list-elenco-imprese-richiedenti,direct_series_page_resolved,2026-09-14,"Dedicated official applicant page directly revalidated 14 September 2026; it exposes ELENCO IMPRESE RICHIEDENTI AL 10 SETTEMBRE 2026. The byte-pinned 22-page PDF yields exactly 98 pending observations from the complete audited source population; exact provenance and finite parser invariants are documented in docs/sources/trento-operational-check-2026-09-14.md."',
)
replace_once(
    "data/source_registry/source_series_inventory.csv",
    'trento-listed,trento,WL-REGIME-L190-2012,listed,all,linked_series_page,https://prefettura.interno.gov.it/it/prefetture/trento/evidenza/white-list,landing_page_resolved,2026-09-07,Official landing page explicitly exposes the registered-company White List resource.',
    'trento-listed,trento,WL-REGIME-L190-2012,listed,all,periodic_attachment,https://prefettura.interno.gov.it/it/prefetture/trento/white-list-elenco-imprese-iscritte,direct_series_page_resolved,2026-09-14,"Dedicated official registered-company page directly revalidated 14 September 2026; it exposes ELENCO IMPRESE ISCRITTE ALL\'11 SETTEMBRE 2026. The byte-pinned 289-page PDF yields exactly 1,366 grouped public observations from 3,020 statutory-section rows; exact provenance, grouping evidence and fail-closed anomaly handling are documented in docs/sources/trento-operational-check-2026-09-14.md."',
)

# 3. Promote only the public-source coverage layer. Canonical DB and durable evidence remain separate controls.
coverage_path = ROOT / "data/monitoring/national_coverage.json"
coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
matches = [item for item in coverage["prefectures"] if item.get("authority_key") == "trento"]
if len(matches) != 1:
    raise RuntimeError(f"Expected one Trento coverage row, found {len(matches)}")
row = matches[0]
if row.get("source_verified") is not True or row.get("population_scopes_complete") is not True:
    raise RuntimeError("Trento pre-integration source/population evidence is not in the expected positive state")
if row.get("canonical_integration_validated") is not False or row.get("durable_evidence_verified") is not False:
    raise RuntimeError("Trento infrastructure boundary drifted before public integration")
row.update(
    {
        "current_edition_identified": True,
        "capture_implemented": True,
        "parser_implemented": True,
        "parser_validated": True,
        "company_observations_loaded": True,
        "observation_layer": "public_source_observations",
        "public_export_enabled": True,
        "latest_source_reference_date": "2026-09-11",
        "last_successful_investigation_on": "2026-09-14",
        "unresolved_issue": [
            "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
        ],
        "actionable_issue": False,
        "coverage_status": "VALIDATED",
        "completion_evidence": [
            "docs/sources/trento-operational-check-2026-09-14.md",
            "src/white_list_archive/parsers/trento_tables.py",
            "tests/test_trento_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        "known_content_sha256": [
            "b831570c01220b8709ebf9c4dbdfe856aba37a21c46353cf7bc9eedb5965c8af",
            "9f36797e3e11834c979f9b5f5d58d693e19fa2456c69ce5859628d4e56a056c0",
        ],
        "evidence": [
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/trento-operational-check-2026-09-14.md",
        ],
        "last_completed_coverage_stage": "VALIDATED",
    }
)
coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 4. Bind the audited parser family into the recursively closed public registry with an explicit adapter.
registry_path = "src/white_list_archive/publishing/public_national_registry.py"
replace_once(
    registry_path,
    "from white_list_archive.parsers.perugia_tables import PARSERS as PERUGIA_PARSERS\n",
    "from white_list_archive.parsers.perugia_tables import PARSERS as PERUGIA_PARSERS\nfrom white_list_archive.parsers.trento_tables import parse_trento_applicants, parse_trento_listed\n",
)
replace_once(
    registry_path,
    'GORIZIA_PARSERS = {\n    "gorizia_listed": parse_gorizia_listed,\n    "gorizia_applicants": parse_gorizia_applicants,\n}\n',
    'GORIZIA_PARSERS = {\n    "gorizia_listed": parse_gorizia_listed,\n    "gorizia_applicants": parse_gorizia_applicants,\n}\nTRENTO_PARSERS = {\n    "trento_listed": parse_trento_listed,\n    "trento_applicants": parse_trento_applicants,\n}\n',
)
adapter = '''\n\ndef _adapt_trento_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    """Project audited Trento evidence onto the recursively closed public contract."""\n    adapted: list[dict[str, Any]] = []\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get("source_fields")\n        if not isinstance(fields, dict):\n            raise RuntimeError("Trento source_fields must be a mapping")\n        if parser_name == "trento_listed":\n            expected = {\n                "sections", "source_memberships", "name_variants",\n                "registered_office_variants", "secondary_office_variants",\n                "identifier_raw_variants", "listing_date_raw", "expiry_date_raw",\n                "update_raw", "identifier_source_evidence", "reviewed_date_exception",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f"Trento listed source-field drift: {sorted(fields)!r}")\n            for key in (\n                "sections", "name_variants", "registered_office_variants",\n                "secondary_office_variants", "identifier_raw_variants",\n                "identifier_source_evidence",\n            ):\n                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):\n                    raise RuntimeError(f"Trento listed source-list type drift: {key}")\n            if not isinstance(fields["source_memberships"], list) or any(not isinstance(value, dict) for value in fields["source_memberships"]):\n                raise RuntimeError("Trento listed source-membership type drift")\n            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw", "update_raw")):\n                raise RuntimeError("Trento listed raw scalar type drift")\n            if type(fields["reviewed_date_exception"]) is not bool:\n                raise RuntimeError("Trento listed reviewed-evidence flag type drift")\n            record["source_fields"] = {\n                "sections": list(fields["sections"]),\n                "registered_office_variants": list(fields["registered_office_variants"]),\n                "secondary_office_variants": list(fields["secondary_office_variants"]),\n                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],\n                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],\n                "in_aggiornamento": fields["update_raw"],\n            }\n        elif parser_name == "trento_applicants":\n            expected = {\n                "activities_raw", "application_date_raw", "integration_date_raw",\n                "outcome_raw", "source_page", "source_table", "source_table_row",\n                "continuation_fragments", "reviewed_application_date_exception",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f"Trento applicant source-field drift: {sorted(fields)!r}")\n            if any(not isinstance(fields[key], str) for key in ("activities_raw", "application_date_raw", "integration_date_raw", "outcome_raw")):\n                raise RuntimeError("Trento applicant raw scalar type drift")\n            if any(type(fields[key]) is not int for key in ("source_page", "source_table", "source_table_row")):\n                raise RuntimeError("Trento applicant source-locator type drift")\n            if not isinstance(fields["continuation_fragments"], list) or any(not isinstance(value, dict) for value in fields["continuation_fragments"]):\n                raise RuntimeError("Trento applicant continuation evidence type drift")\n            if type(fields["reviewed_application_date_exception"]) is not bool:\n                raise RuntimeError("Trento applicant reviewed-evidence flag type drift")\n            record["source_fields"] = {\n                "requested_activities_source": fields["activities_raw"],\n                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],\n            }\n        else:\n            raise RuntimeError(f"Unexpected Trento parser: {parser_name!r}")\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n'''
replace_once(registry_path, "\n\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n", adapter + "\n\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n")
replace_once(
    registry_path,
    '        or PERUGIA_PARSERS.get(cfg["parser"])\n',
    '        or PERUGIA_PARSERS.get(cfg["parser"])\n        or TRENTO_PARSERS.get(cfg["parser"])\n',
)
replace_once(
    registry_path,
    '    if cfg["parser"] in PERUGIA_PARSERS:\n        batch = _adapt_perugia_public_fields(batch, cfg["parser"])\n',
    '    if cfg["parser"] in PERUGIA_PARSERS:\n        batch = _adapt_perugia_public_fields(batch, cfg["parser"])\n    if cfg["parser"] in TRENTO_PARSERS:\n        batch = _adapt_trento_public_fields(batch, cfg["parser"])\n',
)

# 5. Extend browser acceptance with exact Trento denominators and reviewed source anomalies.
browser = "tests/public_portal_browser.cjs"
replace_once(
    browser,
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Perugia'));\n",
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Perugia'));\n      assert.ok(labels.includes('White List ordinaria · Commissariato del Governo per la Provincia di Trento'));\n",
)
replace_once(browser, "      assert.equal(stats.total,40734);\n", "      assert.equal(stats.total,42198);\n")
replace_once(
    browser,
    "'gorizia','napoli','padova','perugia'].includes(r.authority_key)",
    "'gorizia','napoli','padova','perugia','trento'].includes(r.authority_key)",
)
perugia_tail = "      assert.equal(perugia.filter(r=>r.source_key==='perugia-applicants'&&r.name==='BORGIONI PREFABBRICATI S.R.L.'&&r.source_status==='other_or_unknown'&&r.outcome_raw==='25/03/2026').length,1);\n"
trento_block = perugia_tail + """      const trento=registry.records.filter(r=>r.authority_key==='trento');
      assert.equal(trento.length,1464);
      assert.equal(trento.filter(r=>r.source_key==='trento-listed').length,1366);
      assert.equal(trento.filter(r=>r.source_key==='trento-applicants').length,98);
      assert.deepEqual(statusCounts(trento),{listed:699,pending:98,renewal_update_in_progress:667});
      assert.equal(trento.filter(r=>r.source_key==='trento-listed'&&r.name==='BUTTERINI PIETRO TRASPORTI S.R.L.'&&r.identifier_field_raw==='006281590229'&&r.identifiers.length===0).length,1);
      assert.equal(trento.filter(r=>r.source_key==='trento-listed'&&r.source_fields&&Array.isArray(r.source_fields.listing_date_raw_variants)&&r.source_fields.listing_date_raw_variants.includes('14.04.206')&&r.observed_listing_date==='').length,1);
      assert.equal(trento.filter(r=>r.source_key==='trento-applicants'&&r.name==='ROMANI DE MOLL S.R.L. IMPRESA SOCIALE'&&r.application_date==='2026-06-29'&&r.source_fields.application_date_raw_variants.includes('29.06.2026 (integrata il 02.07.2026)')).length,1);
"""
replace_once(browser, perugia_tail, trento_block)

print("Trento candidate transaction applied")
print("TRN_CANDIDATE_RECORDS=1464")
print("NATIONAL_CANDIDATE_RECORDS=42198")
print("NATIONAL_CANDIDATE_PUBLISHED=38")
print("NATIONAL_CANDIDATE_REGISTERS=39")
print("NATIONAL_CANDIDATE_MAPPED=44")

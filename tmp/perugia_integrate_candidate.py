from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LISTED_SHA = "c9cd39452fb2f751c2b9e105c10ecf0b9e57569006138af7f766d6851748029f"
APPLICANT_SHA = "003e2ee6614302b1a1f8a504baae2b0c5d38752c70cfb509f693e1b4c1374f14"
REFERENCE_DATE = "2026-09-03"
LANDING_PAGE = "https://prefettura.interno.gov.it/it/prefetture/perugia/evidenza/white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-delle-imprese-iscritte-white_list_perugia_0.pdf"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-delle-imprese-richiedenti-l-iscrizione_0.pdf"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_verified_primary_pages() -> None:
    path = ROOT / "data/source_registry/verified_primary_pages.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    if any(line.startswith("perugia,") for line in lines):
        raise RuntimeError("Perugia verified-primary-page row unexpectedly already exists")
    anchor = next((i for i, line in enumerate(lines) if line.startswith("pesaro-e-urbino,")), None)
    if anchor is None:
        raise RuntimeError("Pesaro verified-primary-page insertion anchor missing")
    lines.insert(anchor, f"perugia,{LANDING_PAGE},2026-09-14,verified")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    payload = load_json(path)
    sources = payload["sources"]
    if any(source.get("authority_key") == "perugia" for source in sources):
        raise RuntimeError("Perugia publication source unexpectedly already exists")
    common = {
        "authority_key": "perugia",
        "authority_name": "Prefettura di Perugia",
        "register_key": "perugia-ordinary",
        "register_name": "White List ordinaria",
        "reference_date": REFERENCE_DATE,
        "source_page_url": LANDING_PAGE,
        "last_source_update": "2026-09-04",
        "last_source_update_basis": "official landing page updated 4 September 2026 and explicitly publishing both current populations at 3 September 2026; exact bytes repeat-fetched and SHA-256 pinned during parser validation on 14 September 2026",
    }
    sources.extend(
        [
            {
                **common,
                "source_key": "perugia-listed",
                "parser": "perugia_listed",
                "population_scope": "listed",
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_source_rows": 1016,
                "notes": "Byte-pinned 224-page registered-company PDF. The fail-closed parser freezes 1,909 physical rows and 1,854 statutory-section rows, yielding exactly 1,016 company observations (674 listed; 342 renewal/update in progress). Seven malformed date-field cases and five source chronology inversions remain source-bound and are never corrected inferentially.",
            },
            {
                **common,
                "source_key": "perugia-applicants",
                "parser": "perugia_applicants",
                "population_scope": "applicant",
                "resource_url": APPLICANT_URL,
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 1213,
                "notes": "Byte-pinned 184-page requesting-company PDF. Exact continuation evidence yields 1,213 logical observations: 1,036 explicit positive outcomes, 176 pending rows and one other/unknown bare-date outcome. Reviewed malformed or absent dates and the single blank company-name source row are preserved without invention.",
            },
        ]
    )
    dump_json(path, payload)


def update_series_inventory() -> None:
    path = ROOT / "data/source_registry/source_series_inventory.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    if any(line.startswith("perugia-") for line in lines):
        raise RuntimeError("Perugia source-series row unexpectedly already exists")
    anchor = next((i for i, line in enumerate(lines) if line.startswith("pesaro-urbino-combined,")), None)
    if anchor is None:
        raise RuntimeError("Pesaro source-series insertion anchor missing")
    rows = [
        "perugia-applicants,perugia,WL-REGIME-L190-2012,applicant,all,periodic_attachment,"
        f"{LANDING_PAGE},landing_page_resolved,2026-09-14,"
        "Current official landing page directly verified and byte-pinned on 14 September 2026; it positively exposes the requesting-company PDF at 3 September 2026. The fail-closed parser yields exactly 1213 logical observations and preserves the finite reviewed anomaly population documented in docs/sources/perugia-operational-check-2026-09-14.md.",
        "perugia-listed,perugia,WL-REGIME-L190-2012,listed,all,periodic_attachment,"
        f"{LANDING_PAGE},landing_page_resolved,2026-09-14,"
        "Current official landing page directly verified and byte-pinned on 14 September 2026; it positively exposes the registered-company PDF at 3 September 2026. The fail-closed parser yields exactly 1016 grouped observations from 1854 statutory-section rows; exact structure and anomaly evidence are documented in docs/sources/perugia-operational-check-2026-09-14.md.",
    ]
    lines[anchor:anchor] = rows
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_coverage_ledger() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    payload = load_json(path)
    rows = payload.get("prefectures", [])
    matches = [row for row in rows if row.get("authority_key") == "perugia"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one Perugia ledger row, found {len(matches)}")
    row = matches[0]
    expected_prestate = {
        "source_verified": False,
        "current_edition_identified": None,
        "capture_implemented": False,
        "parser_implemented": False,
        "parser_validated": False,
        "company_observations_loaded": False,
        "observation_layer": None,
        "canonical_integration_validated": False,
        "public_export_enabled": False,
        "durable_evidence_verified": False,
        "population_scopes_complete": False,
        "coverage_status": "SOURCE_IDENTIFIED",
    }
    drift = {key: (row.get(key), value) for key, value in expected_prestate.items() if row.get(key) != value}
    if drift:
        raise RuntimeError(f"Perugia coverage-ledger pre-state drift: {drift!r}")
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
            "latest_source_reference_date": REFERENCE_DATE,
            "last_successful_investigation_on": "2026-09-14",
            "coverage_status": "VALIDATED",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "completion_evidence": [
                "docs/sources/perugia-operational-check-2026-09-14.md",
                "src/white_list_archive/parsers/perugia_tables.py",
                "tests/test_perugia_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/perugia-operational-check-2026-09-14.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    dump_json(path, payload)


def update_public_registry() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    import_anchor = "from white_list_archive.parsers.padova_tables import PARSERS as PADOVA_PARSERS\n"
    if "PERUGIA_PARSERS" not in text:
        if import_anchor not in text:
            raise RuntimeError("Padova parser import anchor missing")
        text = text.replace(import_anchor, import_anchor + "from white_list_archive.parsers.perugia_tables import PARSERS as PERUGIA_PARSERS\n", 1)

    if "def _adapt_perugia_public_fields" not in text:
        anchor = "def _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n"
        if anchor not in text:
            raise RuntimeError("_parse_source anchor missing")
        adapter = '''def _adapt_perugia_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    """Project audited Perugia evidence onto the recursively closed public contract."""\n    adapted: list[dict[str, Any]] = []\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get("source_fields")\n        if not isinstance(fields, dict):\n            raise RuntimeError("Perugia source_fields must be a mapping")\n        if parser_name == "perugia_listed":\n            expected = {\n                "sections", "source_memberships", "name_variants",\n                "registered_office_variants", "secondary_office_variants",\n                "identifier_raw_variants", "listing_date_raw", "expiry_date_raw",\n                "update_raw", "reviewed_date_exception",\n                "reviewed_chronology_inversion",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f"Perugia listed source-field drift: {sorted(fields)!r}")\n            for key in ("sections", "name_variants", "registered_office_variants", "secondary_office_variants", "identifier_raw_variants"):\n                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):\n                    raise RuntimeError(f"Perugia listed source-list type drift: {key}")\n            if not isinstance(fields["source_memberships"], list) or any(not isinstance(value, dict) for value in fields["source_memberships"]):\n                raise RuntimeError("Perugia listed source-membership type drift")\n            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw", "update_raw")):\n                raise RuntimeError("Perugia listed raw scalar type drift")\n            if type(fields["reviewed_date_exception"]) is not bool or type(fields["reviewed_chronology_inversion"]) is not bool:\n                raise RuntimeError("Perugia listed reviewed-evidence flag type drift")\n            record["source_fields"] = {\n                "sections": list(fields["sections"]),\n                "registered_office_variants": list(fields["registered_office_variants"]),\n                "secondary_office_variants": list(fields["secondary_office_variants"]),\n                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],\n                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],\n                "in_aggiornamento": fields["update_raw"],\n            }\n        elif parser_name == "perugia_applicants":\n            expected = {\n                "activities_raw", "application_date_raw", "outcome_raw",\n                "source_page", "source_table_row", "continuation_fragments",\n                "reviewed_blank_company_name", "reviewed_application_date_exception",\n                "reviewed_missing_decision_date", "reviewed_bare_outcome",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f"Perugia applicant source-field drift: {sorted(fields)!r}")\n            if any(not isinstance(fields[key], str) for key in ("activities_raw", "application_date_raw", "outcome_raw")):\n                raise RuntimeError("Perugia applicant raw scalar type drift")\n            if type(fields["source_page"]) is not int or type(fields["source_table_row"]) is not int:\n                raise RuntimeError("Perugia applicant source-locator type drift")\n            if not isinstance(fields["continuation_fragments"], list) or any(not isinstance(value, dict) for value in fields["continuation_fragments"]):\n                raise RuntimeError("Perugia applicant continuation evidence type drift")\n            for key in ("reviewed_blank_company_name", "reviewed_application_date_exception", "reviewed_missing_decision_date", "reviewed_bare_outcome"):\n                if type(fields[key]) is not bool:\n                    raise RuntimeError(f"Perugia applicant reviewed-evidence flag type drift: {key}")\n            record["source_fields"] = {\n                "requested_activities_source": fields["activities_raw"],\n                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],\n            }\n        else:\n            raise RuntimeError(f"Unexpected Perugia parser: {parser_name!r}")\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n\n\n'''
        text = text.replace(anchor, adapter + anchor, 1)

    parser_anchor = "        or PADOVA_PARSERS.get(cfg[\"parser\"])\n"
    if "or PERUGIA_PARSERS.get(cfg[\"parser\"])" not in text:
        if parser_anchor not in text:
            raise RuntimeError("Padova parser-chain anchor missing")
        text = text.replace(parser_anchor, parser_anchor + "        or PERUGIA_PARSERS.get(cfg[\"parser\"])\n", 1)

    adapt_anchor = "    if cfg[\"parser\"] in PADOVA_PARSERS:\n        batch = _adapt_padova_public_fields(batch, cfg[\"parser\"])\n"
    if "_adapt_perugia_public_fields(batch" not in text[text.find("def _parse_source"):]:
        if adapt_anchor not in text:
            raise RuntimeError("Padova adapter-chain anchor missing")
        text = text.replace(adapt_anchor, adapt_anchor + "    if cfg[\"parser\"] in PERUGIA_PARSERS:\n        batch = _adapt_perugia_public_fields(batch, cfg[\"parser\"])\n", 1)
    path.write_text(text, encoding="utf-8")


def update_public_pages_workflow() -> None:
    path = ROOT / ".github/workflows/public-pages.yml"
    text = path.read_text(encoding="utf-8")
    if "src/white_list_archive/parsers/perugia_tables.py" not in text:
        anchor = "      - 'src/white_list_archive/parsers/padova_tables.py'\n"
        if anchor not in text:
            raise RuntimeError("Padova workflow path anchor missing")
        text = text.replace(anchor, anchor + "      - 'src/white_list_archive/parsers/perugia_tables.py'\n", 1)
    replacements = {
        "assert reg['meta']['record_count'] == 38505": "assert reg['meta']['record_count'] == 40734",
        "'napoli','padova'}": "'napoli','padova','perugia'}",
        "'napoli-ordinary','padova-ordinary'": "'napoli-ordinary','padova-ordinary','perugia-ordinary'",
        "assert reg['meta']['authority_count'] == 36": "assert reg['meta']['authority_count'] == 37",
        "assert reg['meta']['register_count'] == 37": "assert reg['meta']['register_count'] == 38",
        "assert pref['meta']['published_count'] == 36": "assert pref['meta']['published_count'] == 37",
        "assert pref['meta']['mapped_count'] == 43": "assert pref['meta']['mapped_count'] == 44",
    }
    for old, new in replacements.items():
        if old not in text:
            raise RuntimeError(f"Perugia workflow denominator anchor missing: {old}")
        text = text.replace(old, new, 1)
    perugia_assert = "          perugia = [x for x in pref['prefectures'] if x['authority_key'] == 'perugia']\n          assert len(perugia) == 1 and perugia[0]['mapped'] and perugia[0]['published'] and perugia[0]['series_count'] == 2\n"
    padova_assert = "          padova = [x for x in pref['prefectures'] if x['authority_key'] == 'padova']\n          assert len(padova) == 1 and padova[0]['mapped'] and padova[0]['published'] and padova[0]['series_count'] == 2\n"
    if perugia_assert not in text:
        if padova_assert not in text:
            raise RuntimeError("Padova prefecture workflow assertion anchor missing")
        text = text.replace(padova_assert, padova_assert + perugia_assert, 1)
    path.write_text(text, encoding="utf-8")


def update_browser_test() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    label = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Perugia'));\n"
    padova_label = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Padova'));\n"
    if label not in text:
        if padova_label not in text:
            raise RuntimeError("Padova browser label anchor missing")
        text = text.replace(padova_label, padova_label + label, 1)
    if "assert.equal(stats.total,38505);" not in text:
        raise RuntimeError("Browser total anchor missing")
    text = text.replace("assert.equal(stats.total,38505);", "assert.equal(stats.total,40734);", 1)
    exclusion = "'frosinone','gorizia','napoli','padova'].includes"
    if exclusion not in text:
        raise RuntimeError("Browser previous-baseline exclusion anchor missing")
    text = text.replace(exclusion, "'frosinone','gorizia','napoli','padova','perugia'].includes", 1)
    block = """      const perugia=registry.records.filter(r=>r.authority_key==='perugia');
      assert.equal(perugia.length,2229);
      assert.equal(perugia.filter(r=>r.source_key==='perugia-listed').length,1016);
      assert.equal(perugia.filter(r=>r.source_key==='perugia-applicants').length,1213);
      assert.deepEqual(statusCounts(perugia),{listed:1710,other_or_unknown:1,pending:176,renewal_update_in_progress:342});
      assert.equal(perugia.filter(r=>r.source_key==='perugia-listed'&&r.source_fields&&Array.isArray(r.source_fields.expiry_date_raw_variants)&&r.source_fields.expiry_date_raw_variants.includes('1 8/11/2026')&&r.observed_expiry_date==='').length,1);
      assert.equal(perugia.filter(r=>r.source_key==='perugia-applicants'&&r.name===''&&r.identifier_field_raw==='03522900541').length,1);
      assert.equal(perugia.filter(r=>r.source_key==='perugia-applicants'&&r.name==='BORGIONI PREFABBRICATI S.R.L.'&&r.source_status==='other_or_unknown'&&r.outcome_raw==='25/03/2026').length,1);
"""
    if "const perugia=registry.records.filter" not in text:
        anchor = "      assert.equal(padova.filter(r=>r.name==='CLEAN SRL'&&r.source_key==='padova-applicants'&&r.identifier_field_raw==='02027230289'&&r.application_date==='2026-01-14').length,2);\n"
        if anchor not in text:
            raise RuntimeError("Padova browser evidence anchor missing")
        text = text.replace(anchor, anchor + block, 1)
    path.write_text(text, encoding="utf-8")


def update_source_note() -> None:
    path = ROOT / "docs/sources/perugia-operational-check-2026-09-14.md"
    text = path.read_text(encoding="utf-8")
    old_scope = "This note records the current official Prefettura di Perugia White List publication boundary and the completed source-structure audit used to design a fail-closed parser. It does not yet claim parser validation, company-observation loading or national/public integration."
    new_scope = "This note records the current official Prefettura di Perugia White List publication boundary, the completed source-structure audit and the fail-closed parser evidence approved for public-source integration."
    if old_scope not in text:
        raise RuntimeError("Perugia source-note scope anchor missing")
    text = text.replace(old_scope, new_scope, 1)
    old_end = "Parser implementation, semantic tests, parser-family/source-registry binding, company-observation loading and national/public integration are **not yet completed** at this checkpoint. No Perugia record is public from this branch. No `NOT_PUBLISHED` or completeness conclusion is inferred from search failure."
    if old_end not in text:
        raise RuntimeError("Perugia source-note closing anchor missing")
    validated = '''Parser implementation and semantic tests are complete. Dedicated parser-validation run `34876295250` completed successfully on 14 September 2026 after two independent acquisitions of each official PDF, exact byte/size/SHA-256 checks, semantic tests and complete parsing of all 408 source pages. The validation artifact reports exactly **2,229 distinct record locators**: 1,016 listed-series observations and 1,213 applicant-series observations.

The listed validation also freezes five exact source chronology inversions without correcting them: P.B.M. – POLIMER BITUMEN MODIFIERS DI LEONARDO BACCARELLI E C. S.A.S. (23/06/2025 → 22/06/2025), TECNOTADDEI S.R.L. (23/06/2025 → 22/06/2025), SELLANI ALBERTO Impresa individuale (23/06/2025 → 22/06/2025), SOPRA IL MURO SOCIETA’ COOPERATIVA SOCIALE (07/07/2027 → 06/07/2027), and R.B. S.R.L. (12/11/2025 → 11/11/2025). These values remain exactly as published.

The public integration boundary remains fail-closed: both source SHA-256 values, page counts, physical/logical row denominators, section counts, status distributions, continuation populations and reviewed anomalies must match. Canonical hosted-database integration and independent durable-evidence verification remain separate controls under issue #16 and are not asserted by this parser validation. No `NOT_PUBLISHED`, legal-status or completeness conclusion is inferred from search failure.'''
    text = text.replace(old_end, validated, 1)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    update_verified_primary_pages()
    update_publication_config()
    update_series_inventory()
    update_coverage_ledger()
    update_public_registry()
    update_public_pages_workflow()
    update_browser_test()
    update_source_note()
    print("Perugia integration candidate transaction applied")


if __name__ == "__main__":
    main()

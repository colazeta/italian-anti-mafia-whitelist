from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LISTED_SHA = "d140451c7a091e7df497f49465177ba012422917d2031c24df676e76dd909289"
APPLICANT_SHA = "b2cce4c2d34db016a7b84ac83f71032acdf319c020e1bf881d923ef1d45601a3"
REFERENCE_DATE = "2026-08-14"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/75/2026-08/elenco-imprese-iscritte.pdf"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/75/2026-08/elenco-imprese-richiedenti.pdf"
LISTED_PAGE = "https://prefettura.interno.gov.it/it/prefetture/padova/white-list-elenco-imprese-iscritte"
APPLICANT_PAGE = "https://prefettura.interno.gov.it/it/prefetture/padova/white-list-elenco-imprese-richiedenti"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    payload = load_json(path)
    sources = payload["sources"]
    sources[:] = [s for s in sources if s.get("authority_key") != "padova"]
    common = {
        "authority_key": "padova",
        "authority_name": "Prefettura di Padova",
        "register_key": "padova-ordinary",
        "register_name": "White List ordinaria",
        "reference_date": REFERENCE_DATE,
        "last_source_update": "2026-08-17",
        "last_source_update_basis": "official series page last updated 17 August 2026; exact PDF bytes repeat-fetched, byte-identical and SHA-256 pinned during parser validation on 14 September 2026",
    }
    sources.extend(
        [
            {
                **common,
                "source_page_url": LISTED_PAGE,
                "source_key": "padova-listed",
                "parser": "padova_listed",
                "population_scope": "listed",
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_source_rows": 831,
                "notes": "Byte-pinned 105-page listed-company PDF. The fail-closed parser yields exactly 831 observations (581 listed; 250 renewal/update in progress), preserves two reviewed non-calendar expiry values as raw evidence without date inference, and freezes the single source chronology inversion exactly as published.",
            },
            {
                **common,
                "source_page_url": APPLICANT_PAGE,
                "source_key": "padova-applicants",
                "parser": "padova_applicants",
                "population_scope": "applicant",
                "resource_url": APPLICANT_URL,
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 174,
                "notes": "Byte-pinned 17-page applicant PDF. The dedicated official publication positively defines the applicant population; the fail-closed parser yields exactly 174 pending observations, with one exact source-bound company-name recovery and two adjacent identical source rows preserved as separate observations.",
            },
        ]
    )
    dump_json(path, payload)


def update_series_inventory() -> None:
    path = ROOT / "data/source_registry/source_series_inventory.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    seen = set()
    for line in lines:
        if line.startswith("padova-applicants,"):
            out.append(
                "padova-applicants,padova,WL-REGIME-L190-2012,applicant,all,periodic_attachment,"
                f"{APPLICANT_PAGE},direct_series_page_resolved,2026-09-14,"
                "Dedicated official applicant page positively defines the applicant population; the current byte-pinned PDF yields exactly 174 pending source observations under the fail-closed parser. Exact identity and reviewed extraction exceptions are documented in docs/sources/padova-operational-check-2026-09-14.md."
            )
            seen.add("applicants")
        elif line.startswith("padova-listed,"):
            out.append(
                "padova-listed,padova,WL-REGIME-L190-2012,listed,all,periodic_attachment,"
                f"{LISTED_PAGE},direct_series_page_resolved,2026-09-14,"
                "Dedicated official registered-company page exposes the current byte-pinned PDF; the fail-closed parser yields exactly 831 source observations. Exact identity, status semantics and reviewed source anomalies are documented in docs/sources/padova-operational-check-2026-09-14.md."
            )
            seen.add("listed")
        else:
            out.append(line)
    if seen != {"applicants", "listed"}:
        raise RuntimeError(f"Padova source-series rows missing: {seen!r}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def update_coverage_ledger() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    payload = load_json(path)
    matches = [row for row in payload if row.get("authority_key") == "padova"] if isinstance(payload, list) else [row for row in payload.get("authorities", []) if row.get("authority_key") == "padova"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one Padova ledger row, found {len(matches)}")
    row = matches[0]
    if row.get("source_verified") is not True or row.get("population_scopes_complete") is not True:
        raise RuntimeError("Padova ledger pre-state lacks positive source/population evidence")
    if row.get("canonical_integration_validated") is not False or row.get("durable_evidence_verified") is not False:
        raise RuntimeError("Padova canonical/durable evidence boundary changed unexpectedly")
    row.update(
        {
            "current_edition_identified": True,
            "capture_implemented": True,
            "parser_implemented": True,
            "parser_validated": True,
            "company_observations_loaded": True,
            "observation_layer": "public_source_observations",
            "public_export_enabled": True,
            "latest_source_reference_date": REFERENCE_DATE,
            "last_successful_investigation_on": "2026-09-14",
            "coverage_status": "VALIDATED",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "completion_evidence": [
                "docs/sources/padova-operational-check-2026-09-14.md",
                "src/white_list_archive/parsers/padova_tables.py",
                "tests/test_padova_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/padova-operational-check-2026-09-14.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    dump_json(path, payload)


def update_public_registry() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    import_anchor = "from white_list_archive.parsers.napoli_tables import PARSERS as NAPOLI_PARSERS\n"
    if "PADOVA_PARSERS" not in text:
        if import_anchor not in text:
            raise RuntimeError("Napoli parser import anchor missing")
        text = text.replace(import_anchor, import_anchor + "from white_list_archive.parsers.padova_tables import PARSERS as PADOVA_PARSERS\n", 1)

    if "def _adapt_padova_public_fields" not in text:
        anchor = "def _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n"
        if anchor not in text:
            raise RuntimeError("_parse_source anchor missing")
        adapter = '''def _adapt_padova_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    """Project audited Padova evidence onto the recursively closed public contract."""\n    adapted: list[dict[str, Any]] = []\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get("source_fields")\n        if not isinstance(fields, dict):\n            raise RuntimeError("Padova source_fields must be a mapping")\n        if parser_name == "padova_listed":\n            expected = {\n                "sections", "section_cells_raw", "listing_date_raw", "expiry_date_raw",\n                "note_raw", "source_page", "source_table_row",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f"Padova listed source-field drift: {sorted(fields)!r}")\n            if not isinstance(fields["sections"], list) or any(not isinstance(value, str) for value in fields["sections"]):\n                raise RuntimeError("Padova listed section-field type drift")\n            if not isinstance(fields["section_cells_raw"], list) or any(not isinstance(value, str) for value in fields["section_cells_raw"]):\n                raise RuntimeError("Padova listed section-cell type drift")\n            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw", "note_raw")):\n                raise RuntimeError("Padova listed raw scalar type drift")\n            if type(fields["source_page"]) is not int or type(fields["source_table_row"]) is not int:\n                raise RuntimeError("Padova listed source-locator type drift")\n            record["source_fields"] = {\n                "sections": list(fields["sections"]),\n                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],\n                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],\n            }\n        elif parser_name == "padova_applicants":\n            expected = {\n                "sections", "section_cells_raw", "application_date_raw", "protocol_raw",\n                "note_raw", "source_page", "source_table_row",\n                "reviewed_name_recovery", "reviewed_source_duplicate",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f"Padova applicant source-field drift: {sorted(fields)!r}")\n            if not isinstance(fields["sections"], list) or any(not isinstance(value, str) for value in fields["sections"]):\n                raise RuntimeError("Padova applicant section-field type drift")\n            if not isinstance(fields["section_cells_raw"], list) or any(not isinstance(value, str) for value in fields["section_cells_raw"]):\n                raise RuntimeError("Padova applicant section-cell type drift")\n            if any(not isinstance(fields[key], str) for key in ("application_date_raw", "protocol_raw", "note_raw")):\n                raise RuntimeError("Padova applicant raw scalar type drift")\n            if type(fields["source_page"]) is not int or type(fields["source_table_row"]) is not int:\n                raise RuntimeError("Padova applicant source-locator type drift")\n            if type(fields["reviewed_name_recovery"]) is not bool or type(fields["reviewed_source_duplicate"]) is not bool:\n                raise RuntimeError("Padova applicant reviewed-evidence flag type drift")\n            record["source_fields"] = {\n                "sections": list(fields["sections"]),\n                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],\n            }\n        else:\n            raise RuntimeError(f"Unexpected Padova parser: {parser_name!r}")\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n\n\n'''
        text = text.replace(anchor, adapter + anchor, 1)

    parser_anchor = "        or NAPOLI_PARSERS.get(cfg[\"parser\"])\n"
    if "or PADOVA_PARSERS.get(cfg[\"parser\"])" not in text:
        if parser_anchor not in text:
            raise RuntimeError("Napoli parser-chain anchor missing")
        text = text.replace(parser_anchor, parser_anchor + "        or PADOVA_PARSERS.get(cfg[\"parser\"])\n", 1)

    adapt_anchor = "    if cfg[\"parser\"] in NAPOLI_PARSERS:\n        batch = _adapt_napoli_public_fields(batch, cfg[\"parser\"])\n"
    if "_adapt_padova_public_fields(batch" not in text[text.find("def _parse_source"):]:
        if adapt_anchor not in text:
            raise RuntimeError("Napoli adapter-chain anchor missing")
        text = text.replace(adapt_anchor, adapt_anchor + "    if cfg[\"parser\"] in PADOVA_PARSERS:\n        batch = _adapt_padova_public_fields(batch, cfg[\"parser\"])\n", 1)
    path.write_text(text, encoding="utf-8")


def update_public_pages_workflow() -> None:
    path = ROOT / ".github/workflows/public-pages.yml"
    text = path.read_text(encoding="utf-8")
    if "src/white_list_archive/parsers/padova_tables.py" not in text:
        text = text.replace("      - 'src/white_list_archive/parsers/napoli_tables.py'\n", "      - 'src/white_list_archive/parsers/napoli_tables.py'\n      - 'src/white_list_archive/parsers/padova_tables.py'\n", 1)
    text = text.replace("assert reg['meta']['record_count'] == 37500", "assert reg['meta']['record_count'] == 38505")
    text = text.replace("'gorizia','napoli'}", "'gorizia','napoli','padova'}")
    text = text.replace("'gorizia-ordinary','napoli-ordinary'", "'gorizia-ordinary','napoli-ordinary','padova-ordinary'")
    text = text.replace("assert reg['meta']['authority_count'] == 35", "assert reg['meta']['authority_count'] == 36")
    text = text.replace("assert reg['meta']['register_count'] == 36", "assert reg['meta']['register_count'] == 37")
    text = text.replace("assert pref['meta']['published_count'] == 35", "assert pref['meta']['published_count'] == 36")
    padova_assert = "          padova = [x for x in pref['prefectures'] if x['authority_key'] == 'padova']\n          assert len(padova) == 1 and padova[0]['mapped'] and padova[0]['published'] and padova[0]['series_count'] == 2\n"
    napoli_assert = "          napoli = [x for x in pref['prefectures'] if x['authority_key'] == 'napoli']\n          assert len(napoli) == 1 and napoli[0]['mapped'] and napoli[0]['published'] and napoli[0]['series_count'] == 2\n"
    if padova_assert not in text:
        if napoli_assert not in text:
            raise RuntimeError("Napoli prefecture workflow assertion anchor missing")
        text = text.replace(napoli_assert, napoli_assert + padova_assert, 1)
    path.write_text(text, encoding="utf-8")


def update_browser_test() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    label = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Padova'));\n"
    napoli_label = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Napoli'));\n"
    if label not in text:
        if napoli_label not in text:
            raise RuntimeError("Napoli browser label anchor missing")
        text = text.replace(napoli_label, napoli_label + label, 1)
    text = text.replace("assert.equal(stats.total,37500);", "assert.equal(stats.total,38505);")
    text = text.replace("'frosinone','gorizia','napoli'].includes", "'frosinone','gorizia','napoli','padova'].includes")
    block = """      const padova=registry.records.filter(r=>r.authority_key==='padova');
      assert.equal(padova.length,1005);
      assert.equal(padova.filter(r=>r.source_key==='padova-listed').length,831);
      assert.equal(padova.filter(r=>r.source_key==='padova-applicants').length,174);
      assert.deepEqual(statusCounts(padova),{listed:581,pending:174,renewal_update_in_progress:250});
      assert.equal(padova.filter(r=>r.source_fields&&Array.isArray(r.source_fields.expiry_date_raw_variants)&&r.source_fields.expiry_date_raw_variants.includes('46581,00')&&r.observed_expiry_date==='').length,1);
      assert.equal(padova.filter(r=>r.source_fields&&Array.isArray(r.source_fields.expiry_date_raw_variants)&&r.source_fields.expiry_date_raw_variants.includes('8807/2026')&&r.observed_expiry_date==='').length,1);
      assert.equal(padova.filter(r=>r.name==='NON SOLO ZANZARE SRL'&&r.source_key==='padova-applicants').length,1);
      assert.equal(padova.filter(r=>r.name==='CLEAN SRL'&&r.source_key==='padova-applicants'&&r.identifier_field_raw==='02027230289'&&r.application_date==='2026-01-14').length,2);
"""
    if "const padova=registry.records.filter" not in text:
        anchor = "      assert.equal(napoli.filter(r=>r.source_fields&&Array.isArray(r.source_fields.expiry_date_raw_variants)&&r.source_fields.expiry_date_raw_variants.some(v=>v.startsWith(\"Iscrizione valida per la durata dell'amministrazi\"))&&r.observed_expiry_date==='').length,7);\n"
        if anchor not in text:
            raise RuntimeError("Napoli browser evidence anchor missing")
        text = text.replace(anchor, anchor + block, 1)
    path.write_text(text, encoding="utf-8")


def update_source_note() -> None:
    path = ROOT / "docs/sources/padova-operational-check-2026-09-14.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "This note records the current official-source verification for the Prefettura di Padova ordinary White List. It is an evidence checkpoint only: no parser, row denominator, status distribution, or publication-completeness claim is established here.",
        "This note records the official-source verification and fail-closed parser evidence for the Prefettura di Padova ordinary White List. Publication integration is permitted only for the exact byte-pinned editions and frozen populations documented below.",
    )
    marker = "## Current verification boundary\n"
    if marker not in text:
        raise RuntimeError("Padova source-note boundary heading missing")
    prefix = text.split(marker, 1)[0]
    validated = '''## Parser validation and population boundary

The dedicated Padova parser validation run `34849190341` completed successfully on 14 September 2026 against two independent acquisitions of each official source. The repository CI run `34849190491` on the same head also completed successfully.

The byte-pinned listed PDF contains 105 pages and exactly 831 physical company rows after one repeated header per page is excluded. The parser yields 581 `listed` and 250 `renewal_update_in_progress` observations. Two exact non-calendar expiry values (`46581,00` and `8807/2026`) are retained as raw source evidence while the normalised expiry is left blank; one chronology inversion printed by the source for GEROTTO FEDERICO SRL is preserved without correction.

The byte-pinned applicant PDF contains 17 pages and exactly 174 physical company rows. The parser yields 174 `pending` observations. Applicant row 113 recovers the visibly printed name `NON SOLO ZANZARE SRL` through an exact full-row binding because table extraction loses the company-name cell. Applicant rows 38 and 39 for `CLEAN SRL` are two genuinely distinct physical source rows with identical content and remain two observations; no deduplication is applied.

Across both populations the parser produces exactly 1,005 distinct record locators. Strict identifier extraction accepts only positively evidenced 11-digit VAT/fiscal identifiers or 16-character fiscal codes (including source whitespace normalisation inside explicit slash-delimited components); raw identifier text is retained separately. Section membership is accepted only when the numbered physical section cell contains its own expected section number.

## Publication boundary

The two official series positively establish both listed and applicant populations for the current Padova ordinary White List. The parser is therefore approved for public-source observation integration only when source SHA-256, page counts, row denominators, table width/header invariants, status counts and reviewed exception populations all match the frozen values above. Any drift fails closed. Canonical hosted-database integration and independent durable-evidence verification remain separate controls and are not asserted by this source-parser validation.
'''
    path.write_text(prefix + validated, encoding="utf-8")


def main() -> None:
    update_publication_config()
    update_series_inventory()
    update_coverage_ledger()
    update_public_registry()
    update_public_pages_workflow()
    update_browser_test()
    update_source_note()
    print("Padova integration candidate transaction applied")


if __name__ == "__main__":
    main()

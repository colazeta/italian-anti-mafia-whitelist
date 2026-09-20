from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/ravenna/evidenza/white-list"
RESOURCE = "https://prefettura.interno.gov.it/sites/default/files/64/2026-09/nuova_tabella_unica_17-sett-2026.pdf"
SHA256 = "8d249118ca1fc90cb744a5a630a3c991eee44a963576a031596c9209910ac555"
DOC = "docs/sources/ravenna-operational-check-2026-09-20.md"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one replacement anchor, found {count}")
    return text.replace(old, new, 1)


# 1. Publication source configuration: one official combined series, no invented split.
config_path = ROOT / "data/publication/multi_prefecture_pilot.json"
config = json.loads(config_path.read_text(encoding="utf-8"))
source = {
    "authority_key": "ravenna",
    "authority_name": "Prefettura di Ravenna",
    "approval_mode": "raw_sha256",
    "reference_date": "2026-09-17",
    "last_source_update": "2026-09-17",
    "last_source_update_basis": "dated current official attachment reverified twice on 20 September 2026",
    "register_key": "ravenna-ordinary",
    "register_name": "White List ordinaria",
    "source_page_url": LANDING,
    "source_key": "ravenna-combined",
    "parser": "ravenna_combined",
    "population_scope": "listed_and_applicant",
    "resource_url": RESOURCE,
    "sha256": SHA256,
    "expected_source_rows": 706,
    "notes": (
        "The current official Ravenna surface exposes one combined 29-page table. "
        "The byte-pinned parser yields 706 observations: 430 listed, 212 renewal/update in progress, "
        "63 pending and 1 other/unknown. Pending status requires the positive DATA PRIMA RICHIESTA field "
        "together with an absent listing/renewal date; no separate applicant population is inferred from search failure. "
        "692 observations contain structured identifiers. One reviewed table-boundary extraction miss is repaired only "
        "from the same byte-pinned page text and one malformed date token remains unnormalised."
    ),
}
config["sources"] = [item for item in config["sources"] if item.get("source_key") != "ravenna-combined"] + [source]
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 2. Verified primary page.
pages_path = ROOT / "data/source_registry/verified_primary_pages.csv"
fields, rows = read_csv(pages_path)
rows = [row for row in rows if row["authority_key"] != "ravenna"]
rows.append({
    "authority_key": "ravenna",
    "landing_url": LANDING,
    "verification_date": "2026-09-20",
    "verification_status": "verified",
})
rows.sort(key=lambda row: row["authority_key"])
write_csv(pages_path, fields, rows)

# 3. Combined source-series inventory entry.
series_path = ROOT / "data/source_registry/source_series_inventory.csv"
fields, rows = read_csv(series_path)
rows = [row for row in rows if row["source_series_key"] != "ravenna-combined"]
rows.append({
    "source_series_key": "ravenna-combined",
    "authority_key": "ravenna",
    "regime_code": "WL-REGIME-L190-2012",
    "population_scope": "listed_and_applicant",
    "sector_scope": "all",
    "publication_model": "periodic_attachment",
    "series_url": LANDING,
    "resource_resolution_status": "landing_page_resolved",
    "verified_date": "2026-09-20",
    "notes": (
        "Current official Ravenna page reverified 20 September 2026 exposes exactly one attachment labelled "
        "Nuova tabella unica aggiornata. Two independent cache-bypassed GETs were byte-identical at SHA-256 "
        f"{SHA256}. The combined table positively carries DATA PRIMA RICHIESTA and DATA ISCRIZIONE/RINNOVO fields, "
        "and the fail-closed parser yields 706 observations (430 listed, 212 renewal/update in progress, 63 pending, "
        "1 other/unknown). Exact evidence and reviewed extraction exceptions are documented in "
        "docs/sources/ravenna-operational-check-2026-09-20.md."
    ),
})
rows.sort(key=lambda row: row["source_series_key"])
write_csv(series_path, fields, rows)

# 4. National monitoring state. Public source validation is not canonical hosted-database validation.
coverage_path = ROOT / "data/monitoring/national_coverage.json"
coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
entry = next(item for item in coverage["prefectures"] if item["authority_key"] == "ravenna")
entry.update({
    "official_landing_page": LANDING,
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
    "latest_source_reference_date": "2026-09-17",
    "last_successful_investigation_on": "2026-09-20",
    "actionable_issue": False,
    "coverage_status": "VALIDATED",
    "terminal_reason": None,
    "completion_evidence": [
        DOC,
        "src/white_list_archive/parsers/ravenna_combined.py",
        "tests/test_ravenna_parser_semantics.py",
        "data/publication/multi_prefecture_pilot.json",
    ],
    "known_content_sha256": [SHA256],
    "evidence": [
        "data/source_registry/verified_primary_pages.csv",
        "data/source_registry/source_series_inventory.csv",
        "data/publication/multi_prefecture_pilot.json",
        DOC,
    ],
    "last_completed_coverage_stage": "VALIDATED",
    "unresolved_issue": [
        "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
    ],
})
coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 5. Dataset catalogue counts.
catalog_path = ROOT / "data/catalog.csv"
fields, rows = read_csv(catalog_path)
by_id = {row["dataset_id"]: row for row in rows}
by_id["verified-primary-pages"]["record_count"] = "70"
by_id["source-series-inventory"]["record_count"] = "139"
write_csv(catalog_path, fields, rows)

# 6. Bind the already validated Ravenna parser into the public national builder.
pub_path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
text = pub_path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from white_list_archive.parsers.viterbo_pages import PARSERS as VITERBO_PARSERS\n",
    "from white_list_archive.parsers.viterbo_pages import PARSERS as VITERBO_PARSERS\n"
    "from white_list_archive.parsers.ravenna_combined import PARSERS as RAVENNA_PARSERS\n",
    label="Ravenna public parser import",
)
text = replace_once(
    text,
    "        or VITERBO_PARSERS.get(cfg[\"parser\"])\n",
    "        or VITERBO_PARSERS.get(cfg[\"parser\"])\n"
    "        or RAVENNA_PARSERS.get(cfg[\"parser\"])\n",
    label="Ravenna public parser dispatch",
)
pub_path.write_text(text, encoding="utf-8")

# 7. Registry/completeness tests: Ravenna is a single positively evidenced combined series.
registry_test = ROOT / "tests/test_source_registry.py"
text = registry_test.read_text(encoding="utf-8")
text = text.replace("assert len(pages) == 69", "assert len(pages) == 70", 1)
registry_test.write_text(text, encoding="utf-8")

coverage_test = ROOT / "tests/test_source_population_coverage.py"
text = coverage_test.read_text(encoding="utf-8")
text = text.replace('assert report["verified_authority_count"] == 69', 'assert report["verified_authority_count"] == 70', 1)
text = text.replace('assert report["register_scope_count"] == 72', 'assert report["register_scope_count"] == 73', 1)
text = text.replace('assert report["complete_register_scope_count"] == 72', 'assert report["complete_register_scope_count"] == 73', 1)
if 'covering_series_keys"] == ["ravenna-combined"]' not in text:
    anchor = '''    cremona = [\n        row\n        for row in report["rows"]\n        if row["authority_key"] == "cremona"\n        and row["regime_code"] == "WL-REGIME-L190-2012"\n    ]\n    assert {row["coverage_status"] for row in cremona} == {"COVERED_COMBINED_SERIES"}\n    assert all(row["covering_series_keys"] == ["cremona-combined"] for row in cremona)\n'''
    addition = anchor + '''\n    ravenna = [\n        row\n        for row in report["rows"]\n        if row["authority_key"] == "ravenna"\n        and row["regime_code"] == "WL-REGIME-L190-2012"\n    ]\n    assert {row["population_target"] for row in ravenna} == {"listed", "applicant"}\n    assert {row["coverage_status"] for row in ravenna} == {"COVERED_COMBINED_SERIES"}\n    assert all(row["covering_series_keys"] == ["ravenna-combined"] for row in ravenna)\n'''
    if anchor not in text:
        raise RuntimeError("Ravenna combined-series test anchor drift")
    text = text.replace(anchor, addition, 1)
coverage_test.write_text(text, encoding="utf-8")

# 8. Browser acceptance contract. Keep the original four-Prefecture baseline frozen.
browser_path = ROOT / "tests/public_portal_browser.cjs"
text = browser_path.read_text(encoding="utf-8")
if "White List ordinaria · Prefettura di Ravenna" not in text:
    text = replace_once(
        text,
        "      assert.ok(labels.includes('White List ordinaria · Prefettura di Viterbo'));\n",
        "      assert.ok(labels.includes('White List ordinaria · Prefettura di Viterbo'));\n"
        "      assert.ok(labels.includes('White List ordinaria · Prefettura di Ravenna'));\n",
        label="Ravenna browser label",
    )
text = text.replace("assert.equal(stats.total,71750);", "assert.equal(stats.total,72456);", 1)
text = text.replace("'pordenone','viterbo'].includes(r.authority_key)", "'pordenone','viterbo','ravenna'].includes(r.authority_key)", 1)
if "const ravenna=registry.records.filter(r=>r.authority_key==='ravenna');" not in text:
    anchor = "      assert.equal(viterbo.filter(r=>r.identifiers.length>0).length,258);\n"
    addition = anchor + (
        "      const ravenna=registry.records.filter(r=>r.authority_key==='ravenna');\n"
        "      assert.equal(ravenna.length,706);\n"
        "      assert.equal(ravenna.filter(r=>r.source_key==='ravenna-combined').length,706);\n"
        "      assert.deepEqual(statusCounts(ravenna),{listed:430,other_or_unknown:1,pending:63,renewal_update_in_progress:212});\n"
        "      assert.equal(new Set(ravenna.map(r=>r.record_locator)).size,706);\n"
        "      assert.equal(ravenna.filter(r=>r.identifiers.length>0).length,692);\n"
        "      assert.equal(ravenna.filter(r=>r.source_fields.malformed_date_pairs.includes('application:23/06/026')&&r.application_date==='').length,1);\n"
        "      assert.equal(ravenna.filter(r=>r.source_fields.source_progressive==='1199'&&r.name==='RESOLVE SALVAGE & FIRE (NETHERLANDS) B.V.'&&r.source_fields.reviewed_extraction_repair?.basis==='same_byte_pinned_page_text').length,1);\n"
    )
    if anchor not in text:
        raise RuntimeError("Ravenna browser assertion anchor drift")
    text = text.replace(anchor, addition, 1)
browser_path.write_text(text, encoding="utf-8")

# 9. Candidate Pages workflow. It is validated on the runner and promoted separately so
# the workflow token never needs permission to modify .github/workflows itself.
public_pages = (ROOT / ".github/workflows/public-pages.yml").read_text(encoding="utf-8")
public_pages = public_pages.replace(
    "      - 'src/white_list_archive/parsers/viterbo_pages.py'\n",
    "      - 'src/white_list_archive/parsers/viterbo_pages.py'\n      - 'src/white_list_archive/parsers/ravenna_combined.py'\n",
    1,
)
public_pages = public_pages.replace("assert reg['meta']['record_count'] == 71750", "assert reg['meta']['record_count'] == 72456", 1)
public_pages = public_pages.replace("'pordenone','viterbo'}", "'pordenone','viterbo','ravenna'}", 1)
public_pages = public_pages.replace("'pordenone-ordinary','viterbo-ordinary'", "'pordenone-ordinary','viterbo-ordinary','ravenna-ordinary'", 1)
public_pages = public_pages.replace("assert reg['meta']['authority_count'] == 69", "assert reg['meta']['authority_count'] == 70", 1)
public_pages = public_pages.replace("assert reg['meta']['register_count'] == 72", "assert reg['meta']['register_count'] == 73", 1)
public_pages = public_pages.replace("assert pref['meta']['published_count'] == 69", "assert pref['meta']['published_count'] == 70", 1)
public_pages = public_pages.replace("assert pref['meta']['mapped_count'] == 69", "assert pref['meta']['mapped_count'] == 70", 1)
if "ravenna_records = [r for r in reg['records'] if r['authority_key'] == 'ravenna']" not in public_pages:
    anchor = "          assert len({r['record_locator'] for r in viterbo_records}) == 260\n"
    addition = anchor + (
        "          ravenna = [x for x in pref['prefectures'] if x['authority_key'] == 'ravenna']\n"
        "          assert len(ravenna) == 1 and ravenna[0]['mapped'] and ravenna[0]['published'] and ravenna[0]['series_count'] == 1\n"
        "          ravenna_records = [r for r in reg['records'] if r['authority_key'] == 'ravenna']\n"
        "          assert len(ravenna_records) == 706\n"
        "          assert all(r['source_key'] == 'ravenna-combined' for r in ravenna_records)\n"
        "          assert sum(r['source_status'] == 'listed' for r in ravenna_records) == 430\n"
        "          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in ravenna_records) == 212\n"
        "          assert sum(r['source_status'] == 'pending' for r in ravenna_records) == 63\n"
        "          assert sum(r['source_status'] == 'other_or_unknown' for r in ravenna_records) == 1\n"
        "          assert sum(bool(r['identifiers']) for r in ravenna_records) == 692\n"
        "          assert len({r['record_locator'] for r in ravenna_records}) == 706\n"
    )
    if anchor not in public_pages:
        raise RuntimeError("Ravenna public Pages assertion anchor drift")
    public_pages = public_pages.replace(anchor, addition, 1)
(ROOT / "tmp/ravenna-public-pages-candidate.yml").write_text(public_pages, encoding="utf-8")

# 10. Permanent evidence note.
doc_path = ROOT / DOC
doc_path.parent.mkdir(parents=True, exist_ok=True)
doc_path.write_text(f'''# Ravenna operational source check — 20 September 2026

## Current official publication

- Authority: Prefettura di Ravenna.
- Verified landing page: {LANDING}
- The landing page returned HTTP 200 in the source probe and exposed exactly one current attachment labelled **Nuova tabella unica aggiornata**.
- Current attachment: {RESOURCE}
- Attachment date represented by the official file name: **17 September 2026**.
- Two independent cache-bypassed GETs returned 2,235,879 bytes each and were byte-identical.
- SHA-256: `{SHA256}`.
- PDF extent: 29 pages.

## Population model

Ravenna publishes one combined current table rather than distinct listed-company and applicant attachments. The table itself positively exposes `DATA PRIMA RICHIESTA`, `DATA ISCRIZIONE/RINNOVO`, `NOTE` and statutory sections I–X. The approved publication series is therefore `ravenna-combined` with population scope `listed_and_applicant`; no separate applicant publication is inferred from search results or from an absent second attachment.

The complete audited source boundary is **706 logical rows**. The permanent fail-closed parser produces exactly:

- **430** `listed`;
- **212** `renewal_update_in_progress`;
- **63** `pending`;
- **1** `other_or_unknown`;
- **692/706** records with at least one structurally valid identifier;
- **706/706** unique record locators;
- **0** dropped source rows.

`pending` is assigned only where the row positively contains a first-application date while the registration/renewal field is absent. The two explicit renewal-note spellings are classified as renewal/update in progress. The remaining explicit judicial-control note is retained as `other_or_unknown` rather than receiving an inferred legal effect.

## Reviewed source anomalies

One table-extraction boundary miss affects progressive 1199 on page 26. The table extractor leaves the company-name cell blank while the same byte-pinned page text contains `RESOLVE SALVAGE & FIRE (NETHERLANDS) B.V.`. The parser repairs only this exact reviewed signature, and fails closed if the page number, row shape, address, application date, section marker or same-page text signature changes. This is an extraction repair from the identical source bytes, not an inferred company identity.

One malformed application-date token, `23/06/026`, is preserved in provenance and deliberately left unnormalised. Fourteen rows lack a structurally valid identifier after conservative extraction; their raw company identity remains unchanged. No digit padding, truncation or identifier reconstruction is performed.

## Integration contract

- Parser: `src/white_list_archive/parsers/ravenna_combined.py` (`ravenna_combined`, version 1).
- Parser semantic tests: `tests/test_ravenna_parser_semantics.py`.
- Source registry: `data/source_registry/source_series_inventory.csv` and `verified_primary_pages.csv`.
- Publication configuration: `data/publication/multi_prefecture_pilot.json`.
- Public observation layer: `public_source_observations`.
- Hosted-database canonical integration remains **not validated**; public source validation must not be represented as durable-evidence or canonical-database validation.

The expected public national candidate after Ravenna is **72,456 records / 70 mapped and published authorities / 73 registers**, subject to the national builder, browser acceptance and Pages gates.
''', encoding="utf-8")

print("Ravenna public integration materialised: expected 72456 / 70 / 73 / 70")

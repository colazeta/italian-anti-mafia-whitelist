from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/chieti/evidenza/white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/82/2026-09/elenco-iscritti-white-list-18-settembre-2026.doc"
APPLICANTS_URL = "https://prefettura.interno.gov.it/sites/default/files/82/2026-09/elenco-richiedenti-iscrizione-in-white-list-18-settembre-2026.doc"
LISTED_SHA = "09c9b3ae1b1f4145c2a3795738a8d80d872c9816752cedb31b34cd730d801ddd"
APPLICANTS_SHA = "2628230c417cf7b961d4a22490ba04f1b548c512782bd19a211890e11df54dc1"


def read_csv(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows, list(rows[0])


def write_csv(path: Path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"{label}: expected one replacement target, got {text.count(old)}")
    return text.replace(old, new)


def main() -> None:
    p = ROOT / "data/source_registry/verified_primary_pages.csv"
    rows, fields = read_csv(p)
    if not any(r["authority_key"] == "chieti" for r in rows):
        rows.append({"authority_key": "chieti", "landing_url": LANDING, "verification_date": "2026-09-18", "verification_status": "verified"})
    rows.sort(key=lambda r: r["authority_key"])
    write_csv(p, rows, fields)

    p = ROOT / "data/source_registry/source_series_inventory.csv"
    rows, fields = read_csv(p)
    additions = [
        {"source_series_key":"chieti-listed","authority_key":"chieti","regime_code":"WL-REGIME-L190-2012","population_scope":"listed","sector_scope":"all","publication_model":"periodic_attachment","series_url":"https://prefettura.interno.gov.it/it/prefetture/chieti/white-list-albo-iscritti","resource_resolution_status":"direct_series_page_resolved","verified_date":"2026-09-18","notes":"Current official registered-company page directly revalidated 18 September 2026; its live attachment is explicitly labelled Elenco Iscritti White List - Agg. 18 Settembre 2026. Two independent cache-bypassed captures are byte-identical and the fail-closed legacy Word parser yields 759 grouped observations from 1,352 activity-sector rows. Exact provenance and reviewed source anomalies are documented in docs/sources/chieti-operational-check-2026-09-18.md."},
        {"source_series_key":"chieti-applicants","authority_key":"chieti","regime_code":"WL-REGIME-L190-2012","population_scope":"applicant","sector_scope":"all","publication_model":"periodic_attachment","series_url":"https://prefettura.interno.gov.it/it/prefetture/chieti/elenco-imprese-richiedenti-liscrizione-nelle-white-list","resource_resolution_status":"direct_series_page_resolved","verified_date":"2026-09-18","notes":"Current official applicant page directly revalidated 18 September 2026; its live attachment is explicitly labelled Elenco Richiedenti Iscrizione in White List - Agg. 18 Settembre 2026. Two independent cache-bypassed captures are byte-identical and the fail-closed legacy Word parser yields all 177 source observations, preserving explicit archive, rejection and transferred-competence outcomes rather than treating them as pending. Exact provenance is documented in docs/sources/chieti-operational-check-2026-09-18.md."},
    ]
    keys = {r["source_series_key"] for r in rows}
    rows.extend(r for r in additions if r["source_series_key"] not in keys)
    rows.sort(key=lambda r: r["source_series_key"])
    write_csv(p, rows, fields)

    p = ROOT / "data/publication/multi_prefecture_pilot.json"
    cfg = json.loads(p.read_text(encoding="utf-8"))
    new_sources = [
        {"source_key":"chieti-listed","parser":"chieti_legacy_listed","authority_key":"chieti","authority_name":"Prefettura di Chieti","register_key":"chieti-ordinary","register_name":"White List ordinaria","population_scope":"listed","reference_date":"2026-09-18","source_page_url":LANDING,"resource_url":LISTED_URL,"sha256":LISTED_SHA,"expected_source_rows":759,"expected_sector_rows":1352,"last_source_update":"2026-09-18","last_source_update_basis":"current official source label and two byte-identical cache-bypassed captures","approval_mode":"raw_sha256"},
        {"source_key":"chieti-applicants","parser":"chieti_legacy_applicants","authority_key":"chieti","authority_name":"Prefettura di Chieti","register_key":"chieti-ordinary","register_name":"White List ordinaria","population_scope":"applicant","reference_date":"2026-09-18","source_page_url":LANDING,"resource_url":APPLICANTS_URL,"sha256":APPLICANTS_SHA,"expected_source_rows":177,"last_source_update":"2026-09-18","last_source_update_basis":"current official source label and two byte-identical cache-bypassed captures","approval_mode":"raw_sha256"},
    ]
    existing = {s["source_key"] for s in cfg["sources"]}
    cfg["sources"].extend(s for s in new_sources if s["source_key"] not in existing)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    p = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    entries = data["prefectures"]
    row = next(r for r in entries if r["authority_key"] == "chieti")
    row.update({
        "source_verified": True,
        "current_edition_identified": True,
        "capture_implemented": True,
        "parser_implemented": True,
        "parser_validated": True,
        "company_observations_loaded": True,
        "observation_layer": "public_source_observations",
        "public_export_enabled": True,
        "population_scopes_complete": True,
        "latest_source_reference_date": "2026-09-18",
        "last_successful_investigation_on": "2026-09-18",
        "coverage_status": "VALIDATED",
        "actionable_issue": False,
        "terminal_reason": None,
        "known_content_sha256": [LISTED_SHA, APPLICANTS_SHA],
        "completion_evidence": ["docs/sources/chieti-operational-check-2026-09-18.md", "src/white_list_archive/parsers/chieti_legacy_doc.py", "tests/test_chieti_parser_semantics.py", "data/publication/multi_prefecture_pilot.json"],
        "evidence": ["data/source_registry/verified_primary_pages.csv", "data/source_registry/source_series_inventory.csv", "data/publication/multi_prefecture_pilot.json", "docs/sources/chieti-operational-check-2026-09-18.md"],
        "last_completed_coverage_stage": "VALIDATED",
    })
    row["unresolved_issue"] = ["Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    p = ROOT / "data/catalog.csv"
    text = p.read_text(encoding="utf-8")
    text = replace_once(text, "verified_primary_page,54,false", "verified_primary_page,55,false", "catalog verified count")
    text = replace_once(text, "source_series,107,false", "source_series,109,false", "catalog series count")
    p.write_text(text, encoding="utf-8")

    p = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = p.read_text(encoding="utf-8")
    text = replace_once(text, "from white_list_archive.parsers.laquila_tables import PARSERS as LAQUILA_PARSERS\n", "from white_list_archive.parsers.laquila_tables import PARSERS as LAQUILA_PARSERS\nfrom white_list_archive.parsers.chieti_legacy_doc import PARSERS as CHIETI_PARSERS\n", "Chieti parser import")
    text = replace_once(text, "        or LAQUILA_PARSERS.get(cfg[\"parser\"])\n", "        or LAQUILA_PARSERS.get(cfg[\"parser\"])\n        or CHIETI_PARSERS.get(cfg[\"parser\"])\n", "Chieti parser dispatch")
    p.write_text(text, encoding="utf-8")

    p = ROOT / "tests/test_source_registry.py"
    p.write_text(replace_once(p.read_text(encoding="utf-8"), "assert len(pages) == 54", "assert len(pages) == 55", "verified-pages test"), encoding="utf-8")

    p = ROOT / "tests/test_source_population_coverage.py"
    text = p.read_text(encoding="utf-8")
    for old, new, label in [
        ('assert report["verified_authority_count"] == 54', 'assert report["verified_authority_count"] == 55', 'coverage authority count'),
        ('assert report["register_scope_count"] == 56', 'assert report["register_scope_count"] == 57', 'coverage register count'),
        ('assert report["complete_register_scope_count"] == 56', 'assert report["complete_register_scope_count"] == 57', 'coverage complete count'),
    ]:
        text = replace_once(text, old, new, label)
    p.write_text(text, encoding="utf-8")

    p = ROOT / ".github/workflows/public-pages.yml"
    text = p.read_text(encoding="utf-8")
    replacements = [
        ("      - 'src/white_list_archive/parsers/laquila_tables.py'\n", "      - 'src/white_list_archive/parsers/laquila_tables.py'\n      - 'src/white_list_archive/parsers/chieti_legacy_doc.py'\n", "public trigger"),
        ("sudo apt-get install -y --no-install-recommends poppler-utils;", "sudo apt-get install -y --no-install-recommends poppler-utils antiword;", "public antiword dependency"),
        ("assert reg['meta']['record_count'] == 62286", "assert reg['meta']['record_count'] == 63222", "public record count"),
        ("'messina','laquila'}", "'messina','laquila','chieti'}", "public authority set"),
        ("'messina-ordinary','laquila-ordinary'", "'messina-ordinary','laquila-ordinary','chieti-ordinary'", "public register set"),
        ("assert reg['meta']['authority_count'] == 54", "assert reg['meta']['authority_count'] == 55", "public authority count"),
        ("assert reg['meta']['register_count'] == 56", "assert reg['meta']['register_count'] == 57", "public register count"),
        ("assert pref['meta']['published_count'] == 54", "assert pref['meta']['published_count'] == 55", "public published count"),
        ("assert pref['meta']['mapped_count'] == 54", "assert pref['meta']['mapped_count'] == 55", "public mapped count"),
    ]
    for old, new, label in replacements:
        text = replace_once(text, old, new, label)
    p.write_text(text, encoding="utf-8")

    p = ROOT / "tests/public_portal_browser.cjs"
    text = p.read_text(encoding="utf-8")
    text = replace_once(text, "assert.ok(labels.includes(\"White List ordinaria · Prefettura dell'Aquila\"));", "assert.ok(labels.includes(\"White List ordinaria · Prefettura dell'Aquila\"));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Chieti'));", "browser label")
    text = replace_once(text, "assert.equal(stats.total,62286);", "assert.equal(stats.total,63222);", "browser total")
    text = replace_once(text, "'messina','laquila'].includes(r.authority_key)", "'messina','laquila','chieti'].includes(r.authority_key)", "browser baseline exclusion")
    anchor = "      assert.equal(laquila.filter(r=>r.identifier_field_raw&&r.identifiers.length===0).length,5);"
    block = """
      const chieti=registry.records.filter(r=>r.authority_key==='chieti');
      assert.equal(chieti.length,936);
      assert.equal(chieti.filter(r=>r.source_key==='chieti-listed').length,759);
      assert.equal(chieti.filter(r=>r.source_key==='chieti-applicants').length,177);
      assert.deepEqual(statusCounts(chieti),{cancellation_related:1,expired_observed:10,listed:544,other_or_unknown:7,pending:169,rejected_or_denied:1,renewal_update_in_progress:204});
      assert.equal(new Set(chieti.map(r=>r.record_locator)).size,936);
      assert.equal(chieti.filter(r=>r.identifiers.length>0).length,904);
      assert.equal(chieti.filter(r=>r.source_key==='chieti-listed'&&!r.observed_listing_date&&r.source_fields.listing_date_raw_variants.length>0).length,7);
      assert.equal(chieti.filter(r=>r.source_key==='chieti-listed'&&!r.observed_expiry_date&&r.source_fields.expiry_date_raw_variants.length>0).length,12);
      assert.equal(chieti.filter(r=>r.source_key==='chieti-applicants'&&!r.application_date).length,5);"""
    text = replace_once(text, anchor, anchor + block, "browser Chieti assertions")
    p.write_text(text, encoding="utf-8")

    docs = ROOT / "docs/sources/chieti-operational-check-2026-09-18.md"
    docs.write_text("""# Chieti White List operational check — 18 September 2026

The Prefettura di Chieti official White List surface was revalidated on 18 September 2026. The current registered-company page exposes **Elenco Iscritti White List - Agg. 18 Settembre 2026** and the current applicant page exposes **Elenco Richiedenti Iscrizione in White List - Agg. 18 Settembre 2026**. Both are legacy Word (`.doc`) attachments, parsed through `antiword` table output rather than inferred from rendered prose.

Two independent cache-bypassed GETs of each current attachment were byte-identical: registered companies `09c9b3ae1b1f4145c2a3795738a8d80d872c9816752cedb31b34cd730d801ddd`; applicants `2628230c417cf7b961d4a22490ba04f1b548c512782bd19a211890e11df54dc1`.

The registered attachment contains 1,352 activity-sector rows across ten headings. Exact repeated observations across sectors are grouped conservatively into **759 observations**: 544 `listed`, 204 `renewal_update_in_progress`, 10 `expired_observed`, and one `cancellation_related`. Structured identifier coverage is 731/759. Seven grouped observations retain non-normalised listing-date typography and 12 retain non-normalised expiry-date typography. One registered sector row has a blank company-name cell but an explicit office and identifier; it is retained without inferential filling. Legacy document metadata contains a stale Teramo template title; source identity rests on the Chieti official pages, current attachment links and table content.

The applicant attachment contains **177 observations**, all retained: 169 `pending`, seven `other_or_unknown` for explicit archived or transferred-competence outcomes, and one `rejected_or_denied` for the explicit interdittiva outcome. Structured identifier coverage is 173/177. Five rows have malformed or missing application dates and preserve their raw source values.

Publication is byte-pinned (`raw_sha256`) and fail-closed on activity headings, row/observation denominators, applicant outcome vocabulary, status distributions and identifier coverage. Both listed and applicant populations are positively evidenced.
""", encoding="utf-8")

    tests = ROOT / "tests/test_chieti_parser_semantics.py"
    tests.write_text('''from white_list_archive.parsers.chieti_legacy_doc import _applicant_status, _listed_status, _source_date, _source_identifiers\n\n\ndef test_chieti_dates_are_conservative():\n    assert _source_date("13 ottobre 2026") == "2026-10-13"\n    assert _source_date("27/05/2015") == "2015-05-27"\n    assert _source_date("1° LUGLIO 2019") == "2019-07-01"\n    assert _source_date("23 maggio 20256") == ""\n    assert _source_date("8 febbario 2022") == ""\n\n\ndef test_chieti_identifier_extraction_preserves_only_strict_shapes():\n    assert _source_identifiers("c.f.DLRRRT65S18D763Z p.IVA 01994310694") == ["01994310694", "DLRRRT65S18D763Z"]\n    assert _source_identifiers("p.IVA 003253330695") == []\n\n\ndef test_chieti_statuses_require_positive_source_text():\n    assert _listed_status("") == "listed"\n    assert _listed_status("Richiesta di rinnovo in data 09/07/2026") == "renewal_update_in_progress"\n    assert _listed_status("ISCRIZIONE SCADUTA") == "expired_observed"\n    assert _listed_status("richiesta cancellazione per trasferimento sede legale") == "cancellation_related"\n    assert _applicant_status("IN ISTRUTTORIA") == "pending"\n    assert _applicant_status("") == "pending"\n    assert _applicant_status("Istanza archiviata con D.P. 1") == "other_or_unknown"\n    assert _applicant_status("Istruttoria trasferita per competenza alla Prefettura di Pescara") == "other_or_unknown"\n    assert _applicant_status("Istanza respinta a seguito di informativa interdittiva") == "rejected_or_denied"\n''', encoding="utf-8")


if __name__ == "__main__":
    main()

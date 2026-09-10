from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://prefettura.interno.gov.it/it/prefetture/biella/evidenza/white-list"
SHA = "636389e9980b58b80e3ef5338feca39221db934b6b7ccb0f29b8d286c95dca53"


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"empty CSV: {path}")
    return rows, list(rows[0])


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    publication_path = ROOT / "data/publication/multi_prefecture_pilot.json"
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    assert not any(source["authority_key"] == "biella" for source in publication["sources"])
    publication["sources"].extend(
        [
            {
                "source_key": "biella-listed",
                "parser": "biella_html_listed",
                "authority_key": "biella",
                "authority_name": "Prefettura di Biella",
                "register_key": "biella-ordinary",
                "register_name": "White List ordinaria",
                "population_scope": "listed",
                "reference_date": "2026-08-26",
                "source_page_url": URL,
                "resource_url": URL,
                "sha256": SHA,
                "expected_sector_rows": 234,
                "expected_source_rows": 130,
                "last_source_update": "2026-08-26",
                "last_source_update_basis": "official page Ultimo aggiornamento timestamp and byte-pinned HTML",
                "notes": "The current official landing HTML contains the listed-company table organised across ten White List sections. The parser groups only repeated source rows sharing conservatively normalised identity, listing date, expiry date and mapped source status; conflicting date tuples remain separate. Italian textual/numeric source dates are parsed without changing digits, non-canonical identifiers remain raw, and the single blank expiry is preserved.",
            },
            {
                "source_key": "biella-applicants",
                "parser": "biella_html_applicants",
                "authority_key": "biella",
                "authority_name": "Prefettura di Biella",
                "register_key": "biella-ordinary",
                "register_name": "White List ordinaria",
                "population_scope": "applicant",
                "reference_date": "2026-08-26",
                "source_page_url": URL,
                "resource_url": URL,
                "sha256": SHA,
                "expected_sector_rows": 109,
                "expected_source_rows": 109,
                "last_source_update": "2026-08-26",
                "last_source_update_basis": "official page Ultimo aggiornamento timestamp and byte-pinned HTML",
                "notes": "The current official landing HTML explicitly labels the applicant population and exposes requested activity, application date and outcome. Only source-explicit outcomes are mapped: iscritto/iscritta to listed, update markers to renewal_update_in_progress, and blank/in lavorazione to pending. Two non-canonical identifiers and one blank application date remain raw/blank rather than reconstructed.",
            },
        ]
    )
    publication_path.write_text(json.dumps(publication, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    verified_path = ROOT / "data/source_registry/verified_primary_pages.csv"
    verified, fields = read_csv(verified_path)
    matches = [row for row in verified if row["authority_key"] == "biella"]
    assert len(matches) == 1 and matches[0]["landing_url"] == URL
    matches[0]["verification_date"] = "2026-09-10"
    write_csv(verified_path, verified, fields)

    series_path = ROOT / "data/source_registry/source_series_inventory.csv"
    series, fields = read_csv(series_path)
    by_key = {row["source_series_key"]: row for row in series}
    assert by_key["biella-listed"]["series_url"] == URL
    assert by_key["biella-applicants"]["authority_key"] == "biella"
    by_key["biella-listed"].update(
        {
            "series_url": URL,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": "2026-09-10",
            "notes": "Current official landing HTML verified 10 September 2026; the byte-pinned 26 August 2026 edition embeds the ten-section listed-company table. Exact source identity and parser boundary are documented in docs/sources/biella-operational-check-2026-09-10.md.",
        }
    )
    by_key["biella-applicants"].update(
        {
            "series_url": URL,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": "2026-09-10",
            "notes": "Current official landing HTML verified 10 September 2026 embeds the applicant table through 2026. A dedicated applicant page also exists but was observed to expose an older table, so it is not used as the approved current edition. Exact source identity and parser boundary are documented in docs/sources/biella-operational-check-2026-09-10.md.",
        }
    )
    write_csv(series_path, series, fields)

    registry_path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = registry_path.read_text(encoding="utf-8")
    import_anchor = "from white_list_archive.parsers.avellino_positioned import PARSERS as AVELLINO_PARSERS\nfrom white_list_archive.parsers.pesaro_urbino_combined import PARSERS as PESARO_PARSERS\n"
    assert import_anchor in text and "BIELLA_PARSERS" not in text
    text = text.replace(import_anchor, import_anchor + "from white_list_archive.parsers.biella_html import PARSERS as BIELLA_PARSERS\n", 1)
    dispatch_anchor = "        or AVELLINO_PARSERS.get(cfg[\"parser\"])\n        or PESARO_PARSERS.get(cfg[\"parser\"])\n"
    assert dispatch_anchor in text
    text = text.replace(dispatch_anchor, dispatch_anchor + "        or BIELLA_PARSERS.get(cfg[\"parser\"])\n", 1)
    registry_path.write_text(text, encoding="utf-8")

    monitoring_path = ROOT / "data/monitoring/national_coverage.json"
    monitoring = json.loads(monitoring_path.read_text(encoding="utf-8"))
    matches = [row for row in monitoring["prefectures"] if row["authority_key"] == "biella"]
    assert len(matches) == 1
    row = matches[0]
    row.update(
        {
            "official_landing_page": URL,
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
            "latest_source_reference_date": "2026-08-26",
            "last_successful_source_check_at": "2026-09-10T03:29:00Z",
            "last_attempted_source_check_at": "2026-09-10T03:29:00Z",
            "last_successful_investigation_on": "2026-09-10",
            "monitoring_status": "CURRENT",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/biella-operational-check-2026-09-10.md",
                "src/white_list_archive/parsers/biella_html.py",
                "tests/test_biella_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "docs/sources/biella-operational-check-2026-09-10.md",
                "src/white_list_archive/parsers/biella_html.py",
                "tests/test_biella_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
                "https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/34433478263",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    monitoring_path.write_text(json.dumps(monitoring, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    catalog_path = ROOT / "data/catalog.csv"
    catalog, fields = read_csv(catalog_path)
    matches = [row for row in catalog if row["dataset_id"] == "multi-prefecture-publication-pilot"]
    assert len(matches) == 1 and matches[0]["record_count"] == "17"
    matches[0]["record_count"] = "19"
    write_csv(catalog_path, catalog, fields)

    workflow_path = ROOT / ".github/workflows/public-pages.yml"
    text = workflow_path.read_text(encoding="utf-8")
    parser_anchor = "      - 'src/white_list_archive/parsers/pesaro_urbino_combined.py'\n"
    assert text.count(parser_anchor) == 1
    text = text.replace(parser_anchor, parser_anchor + "      - 'src/white_list_archive/parsers/biella_html.py'\n", 1)
    replacements = {
        "assert reg['meta']['record_count'] == 7345": "assert reg['meta']['record_count'] == 7584",
        "{'cosenza','parma','pistoia','bologna','alessandria','aosta','arezzo','avellino','pesaro-e-urbino'}": "{'cosenza','parma','pistoia','bologna','alessandria','aosta','arezzo','avellino','pesaro-e-urbino','biella'}",
        "'bologna-provincial','bologna-post-sisma','alessandria-ordinary','aosta-ordinary','arezzo-ordinary','avellino-ordinary','pesaro-urbino-ordinary'": "'bologna-provincial','bologna-post-sisma','alessandria-ordinary','aosta-ordinary','arezzo-ordinary','avellino-ordinary','pesaro-urbino-ordinary','biella-ordinary'",
        "assert reg['meta']['authority_count'] == 9": "assert reg['meta']['authority_count'] == 10",
        "assert reg['meta']['register_count'] == 10": "assert reg['meta']['register_count'] == 11",
        "assert pref['meta']['published_count'] == 9": "assert pref['meta']['published_count'] == 10",
    }
    for old, new in replacements.items():
        assert text.count(old) == 1, (old, text.count(old))
        text = text.replace(old, new, 1)
    prefecture_anchor = "          assert len(pesaro) == 1 and pesaro[0]['mapped'] and pesaro[0]['published']\n"
    assert text.count(prefecture_anchor) == 1
    text = text.replace(
        prefecture_anchor,
        prefecture_anchor
        + "          biella = [x for x in pref['prefectures'] if x['authority_key'] == 'biella']\n"
        + "          assert len(biella) == 1 and biella[0]['mapped'] and biella[0]['published']\n",
        1,
    )
    workflow_path.write_text(text, encoding="utf-8")

    browser_path = ROOT / "tests/public_portal_browser.cjs"
    text = browser_path.read_text(encoding="utf-8")
    label_anchor = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Pesaro e Urbino'));\n"
    assert text.count(label_anchor) == 1
    text = text.replace(label_anchor, label_anchor + "      assert.ok(labels.includes('White List ordinaria · Prefettura di Biella'));\n", 1)
    assert text.count("assert.equal(stats.total,7345);") == 1
    text = text.replace("assert.equal(stats.total,7345);", "assert.equal(stats.total,7584);", 1)
    baseline_old = "!['alessandria','aosta','arezzo','avellino','pesaro-e-urbino'].includes(r.authority_key)"
    baseline_new = "!['alessandria','aosta','arezzo','avellino','pesaro-e-urbino','biella'].includes(r.authority_key)"
    assert text.count(baseline_old) == 1
    text = text.replace(baseline_old, baseline_new, 1)
    stats_anchor = "      assert.deepEqual(statusCounts(pesaro),{listed:406,renewal_update_in_progress:78});\n"
    assert text.count(stats_anchor) == 1
    biella_block = """      const biella=registry.records.filter(r=>r.authority_key==='biella');
      assert.equal(biella.length,239);
      assert.equal(biella.filter(r=>r.source_key==='biella-listed').length,130);
      assert.equal(biella.filter(r=>r.source_key==='biella-applicants').length,109);
      assert.deepEqual(statusCounts(biella),{listed:213,pending:12,renewal_update_in_progress:14});
"""
    text = text.replace(stats_anchor, stats_anchor + biella_block, 1)
    browser_path.write_text(text, encoding="utf-8")

    doc_path = ROOT / "docs/sources/biella-operational-check-2026-09-10.md"
    assert not doc_path.exists()
    doc_path.write_text(
        f"""# Biella White List operational check — 10 September 2026

## Current official source

The authoritative surface used for this publication is the Prefettura di Biella White List landing page:

- {URL}
- official visible update: **26 August 2026, 09:43**
- byte identity verified from a GitHub-hosted runner on 10 September 2026: `{SHA}`

The current HTML itself contains two explicitly labelled populations: the table of companies requesting registration and the listed-company table organised across the ten statutory White List sections. A separate applicant page also exists, but the observed table there stopped in 2023 while the embedded landing-page table contains applications through 2026. The separate page is therefore retained only as discovery evidence, not selected as the current approved edition.

## Parser validation

The byte-pinned source was parsed with `biella_html_applicants` and `biella_html_listed` in Actions run 34433478263. The validated boundary is:

- applicants: **109 source rows / 109 public observations**;
- applicant statuses: **93 listed, 12 pending, 4 renewal/update in progress**;
- applicant identifiers: **107 canonical, 2 raw-only**; one application date is blank;
- listed table: **234 source sector rows / 130 public observations** after source-backed sector grouping;
- listed statuses: **120 listed, 10 renewal/update in progress**;
- listed identifiers: **90 canonical, 40 raw-only**; one expiry date is blank;
- no source-date row was dropped.

Sector repetition is grouped only when a conservatively normalised source identity, listing date, expiry date and mapped source status all agree. Conflicting date tuples remain distinct observations. Typography-equivalent dates such as `23-nov-20` and `23/11/2020` may resolve to the same date, but source digits are never repaired. Non-canonical identifiers remain available only in the raw source field.

## Evidence boundary

This validates the **public source-observation layer**. It does not claim nationally deduplicated legal entities, canonical hosted-database integration or independent durable-evidence recovery. Those infrastructure gates remain governed separately under issue #16 and do not justify withholding these directly source-backed observations from the experimental public registry.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LANDING = "https://prefettura.interno.gov.it/it/prefetture/brindisi/evidenza/white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/23/2026-09/white-list-elenco-imprese-iscritte_1.pdf"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/23/2026-09/white_list_della_provincia_di_brindisi-elenco_delle_imprese_richiedenti_l-iscrizione_0.pdf"
LISTED_SHA = "11d33d62f5e40139d4869e5f39752b1a69686bb064e46446161929fd84eeb06a"
APPLICANT_SHA = "1153781d3bf17b6cfc6513c90f8e083edf3a432fe6be382c4a1ffde9845f9e1b"
LISTED_SEMANTIC = "589cce1b755a50c3629d3bc5034bbe5b566c3d24dd08c3bfe4fb9e1cff83b20e"
APPLICANT_SEMANTIC = "9b1f6767a921c140a8ef3c2b4339a876d91829201ef0b51464ae137886df22b5"
REFERENCE_DATE = "2026-09-08"
CHECKED_AT = "2026-09-11T08:35:05Z"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_public_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    keys = {source["source_key"] for source in data["sources"]}
    assert "brindisi-listed" not in keys and "brindisi-applicants" not in keys
    data["sources"].extend([
        {
            "source_key": "brindisi-listed",
            "parser": "brindisi_listed",
            "authority_key": "brindisi",
            "authority_name": "Prefettura di Brindisi",
            "register_key": "brindisi-ordinary",
            "register_name": "White List ordinaria",
            "population_scope": "listed",
            "reference_date": REFERENCE_DATE,
            "source_page_url": LANDING,
            "resource_url": LISTED_URL,
            "sha256": LISTED_SHA,
            "expected_source_rows": 385,
            "expected_sector_rows": 830,
            "last_source_update": REFERENCE_DATE,
            "last_source_update_basis": "official landing page Ultimo aggiornamento marker and current attachment identity reverified 11 September 2026",
            "notes": "Current byte-pinned registered-company publication. The source repeats firms across ten White List sections: 830 reviewed sector rows are grouped only where identity, dates, status and source note agree, yielding 385 public source-backed observations. Three reviewed malformed expiry tokens remain raw and are never repaired. Exact boundaries are documented in docs/sources/brindisi-operational-check-2026-09-11.md."
        },
        {
            "source_key": "brindisi-applicants",
            "parser": "brindisi_applicants",
            "authority_key": "brindisi",
            "authority_name": "Prefettura di Brindisi",
            "register_key": "brindisi-ordinary",
            "register_name": "White List ordinaria",
            "population_scope": "applicant",
            "reference_date": REFERENCE_DATE,
            "source_page_url": LANDING,
            "resource_url": APPLICANT_URL,
            "sha256": APPLICANT_SHA,
            "expected_source_rows": 26,
            "last_source_update": REFERENCE_DATE,
            "last_source_update_basis": "official landing page Ultimo aggiornamento marker and current attachment identity reverified 11 September 2026",
            "notes": "Current byte-pinned applicant publication positively identified by the official landing page as Elenco imprese richiedenti iscrizione. It yields 26 pending observations across three pages. One reviewed application date is blank; non-canonical identifiers remain raw and are never reconstructed. Exact boundaries are documented in docs/sources/brindisi-operational-check-2026-09-11.md."
        }
    ])
    write_json(path, data)


def update_coverage() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [row for row in data["prefectures"] if row["authority_key"] == "brindisi"]
    assert len(rows) == 1
    row = rows[0]
    assert row["source_verified"] is True
    assert row["public_export_enabled"] is False
    row.update({
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
        "last_successful_source_check_at": CHECKED_AT,
        "last_attempted_source_check_at": CHECKED_AT,
        "last_successful_investigation_on": "2026-09-11",
        "monitoring_status": "CURRENT",
        "unresolved_issue": ["Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."],
        "actionable_issue": False,
        "coverage_status": "VALIDATED",
        "terminal_reason": None,
        "completion_evidence": [
            "docs/sources/brindisi-operational-check-2026-09-11.md",
            "src/white_list_archive/parsers/brindisi_tables.py",
            "tests/test_brindisi_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json"
        ],
        "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
        "evidence": [
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/brindisi-operational-check-2026-09-11.md"
        ],
        "last_completed_coverage_stage": "VALIDATED"
    })
    write_json(path, data)


def update_csvs() -> None:
    series_path = ROOT / "data/source_registry/source_series_inventory.csv"
    with series_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    matches = {row["source_series_key"]: row for row in rows if row["source_series_key"] in {"brindisi-listed", "brindisi-applicants"}}
    assert set(matches) == {"brindisi-listed", "brindisi-applicants"}
    matches["brindisi-listed"]["verified_date"] = "2026-09-11"
    matches["brindisi-listed"]["notes"] = (
        "Current official landing page reverified 11 September 2026; it exposes a listed-company PDF and separately an applicant PDF, with page update marker 8 September 2026. "
        "The listed attachment is byte-pinned at 39 pages; 830 section rows yield 385 source-backed public observations after conservative section-repeat grouping. Exact evidence is documented in docs/sources/brindisi-operational-check-2026-09-11.md."
    )
    matches["brindisi-applicants"]["verified_date"] = "2026-09-11"
    matches["brindisi-applicants"]["notes"] = (
        "Current official landing page reverified 11 September 2026 explicitly labels a separate Elenco imprese richiedenti iscrizione attachment. "
        "The byte-pinned three-page attachment yields 26 pending source-backed observations. Exact evidence is documented in docs/sources/brindisi-operational-check-2026-09-11.md."
    )
    with series_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)

    pages_path = ROOT / "data/source_registry/verified_primary_pages.csv"
    with pages_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        page_fields = list(reader.fieldnames or [])
        page_rows = list(reader)
    matches = [row for row in page_rows if row["authority_key"] == "brindisi"]
    assert len(matches) == 1
    matches[0]["landing_url"] = LANDING
    matches[0]["verification_date"] = "2026-09-11"
    matches[0]["verification_status"] = "verified"
    with pages_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=page_fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(page_rows)


def update_registry_binding() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    imp = "from white_list_archive.parsers.barletta_andria_trani_tables import PARSERS as BARLETTA_ANDRIA_TRANI_PARSERS\n"
    assert text.count(imp) == 1
    assert "BRINDISI_PARSERS" not in text
    text = text.replace(imp, imp + "from white_list_archive.parsers.brindisi_tables import PARSERS as BRINDISI_PARSERS\n", 1)
    chain = "        or BARLETTA_ANDRIA_TRANI_PARSERS.get(cfg[\"parser\"])\n    )"
    assert text.count(chain) == 1
    text = text.replace(chain, "        or BARLETTA_ANDRIA_TRANI_PARSERS.get(cfg[\"parser\"])\n        or BRINDISI_PARSERS.get(cfg[\"parser\"])\n    )", 1)
    path.write_text(text, encoding="utf-8")


def update_browser_test() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    label = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Barletta-Andria-Trani'));\n"
    assert text.count(label) == 1
    text = text.replace(label, label + "      assert.ok(labels.includes('White List ordinaria · Prefettura di Brindisi'));\n", 1)
    assert text.count("assert.equal(stats.total,17303);") == 1
    text = text.replace("assert.equal(stats.total,17303);", "assert.equal(stats.total,17714);", 1)
    old_exclusion = "'bari','udine','bergamo','barletta-andria-trani'].includes(r.authority_key)"
    assert text.count(old_exclusion) == 1
    text = text.replace(old_exclusion, "'bari','udine','bergamo','barletta-andria-trani','brindisi'].includes(r.authority_key)", 1)
    anchor = "      assert.deepEqual(statusCounts(barletta),{listed:437,pending:81,renewal_update_in_progress:56});\n"
    assert text.count(anchor) == 1
    text = text.replace(anchor, anchor + (
        "      const brindisi=registry.records.filter(r=>r.authority_key==='brindisi');\n"
        "      assert.equal(brindisi.length,411);\n"
        "      assert.equal(brindisi.filter(r=>r.source_key==='brindisi-listed').length,385);\n"
        "      assert.equal(brindisi.filter(r=>r.source_key==='brindisi-applicants').length,26);\n"
        "      assert.deepEqual(statusCounts(brindisi),{listed:341,pending:26,renewal_update_in_progress:44});\n"
    ), 1)
    path.write_text(text, encoding="utf-8")


def update_operations_test() -> None:
    path = ROOT / "tests/test_operations.py"
    text = path.read_text(encoding="utf-8")
    old = "    # Keep this safety invariant attached to an authority that is still at the\n    # source-identified stage. Barletta-Andria-Trani graduates only after both\n    # positive populations, byte identity and parser boundaries are validated.\n    authority_key = \"brindisi\"\n"
    assert text.count(old) == 1
    new = "    # Keep this safety invariant attached to an authority that is still at the\n    # source-identified stage. Cagliari remains unadvanced while Brindisi graduates\n    # only after positive listed/applicant evidence, byte identity and parser validation.\n    authority_key = \"cagliari\"\n"
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def write_docs() -> None:
    path = ROOT / "docs/sources/brindisi-operational-check-2026-09-11.md"
    assert not path.exists()
    path.write_text(f"""# Brindisi operational source check — 11 September 2026

## Official current publication surface

- Authority: Prefettura di Brindisi.
- Official landing page: {LANDING}
- The live official page was reverified on 11 September 2026 and positively exposes two distinct current populations: `White List - Elenco imprese iscritte` and `White List - Elenco imprese richiedenti iscrizione`.
- The page reports `Ultimo aggiornamento Martedì 8 Settembre 2026, ore 13:16`; the public-source reference date is therefore frozen as **2026-09-08**.
- Listed resource: {LISTED_URL}
- Applicant resource: {APPLICANT_URL}

This treatment does not infer a missing population, status or completeness from search behaviour. Both populations are supported by positive labels on the official surface.

## Capture identity and repeatability

Two independent live captures of each current official attachment were parsed in the same validation run. Both raw bytes and parsed semantics were stable across the two captures.

| Population | Pages | Raw SHA-256 | Semantic SHA-256 | Public observations |
| --- | ---: | --- | --- | ---: |
| Listed | 39 | `{LISTED_SHA}` | `{LISTED_SEMANTIC}` | 385 |
| Applicant | 3 | `{APPLICANT_SHA}` | `{APPLICANT_SEMANTIC}` | 26 |

Raw SHA-256 is used as the publication approval boundary because both repeated captures were byte-identical. Semantic digests remain independent audit evidence.

## Listed-population parser boundary

The current listed PDF contains ten White List sections. The fail-closed parser freezes the section transitions and the following source-sector denominators: I 109, II 55, III 137, IV 52, V 150, VI 155, VII 4, VIII 14, IX 32 and X 122, for **830 source-sector rows**.

The source repeats companies across sections. Rows are grouped only when the same strict source identity (or, if no strict identifier exists, the same cleaned name), listing date, expiry date, status and source note agree. This yields **385 public source-backed observations**: **341 `listed`** and **44 `renewal_update_in_progress`**. The underlying 830 sector rows contain 718 listed and 112 update-in-progress rows.

Three reviewed malformed expiry strings — `0S-03-2027`, `25-03-20270` and `07-04-2027ti` — are preserved in raw provenance while the normalised date remains blank. They are not repaired. Strict identifiers are extracted only when the source contains an 11-digit numeric identifier or a 16-character alphanumeric identifier; malformed lengths are not padded, truncated or inferred. The public listed observations have strict identifier coverage for 383/385 records.

## Applicant-population parser boundary

The current applicant PDF is independently identified by the official page as the applicant population. The parser uses fixed ruled-table geometry and validated header anchors. It freezes page denominators of **10 + 15 + 1 = 26 observations**, all mapped to **`pending`** solely because they belong to the positively identified applicant publication.

One reviewed applicant observation has a blank application date and remains blank. Strict identifier coverage is 25/26, and one source observation legitimately contains two strict identifiers. No identifier or date is reconstructed.

## Publication scope and remaining infrastructure boundary

The validated Brindisi public contribution is therefore **411 source-backed observations** (385 listed-population observations plus 26 applicant observations). This is an observation count, not a count of unique legal entities.

Canonical hosted-database integration and independent durable-evidence verification are not asserted by this expansion and remain governed separately under issue #16. The parser and public build fail closed on source byte drift, page/section denominator drift, unreviewed date typography and applicant geometry drift.
""", encoding="utf-8")


def update_pages_gate() -> None:
    path = ROOT / ".github/workflows/public-pages.yml"
    text = path.read_text(encoding="utf-8")
    parser = "      - 'src/white_list_archive/parsers/barletta_andria_trani_tables.py'\n"
    assert text.count(parser) == 1
    assert "src/white_list_archive/parsers/brindisi_tables.py" not in text
    text = text.replace(parser, parser + "      - 'src/white_list_archive/parsers/brindisi_tables.py'\n", 1)
    assert text.count("assert reg['meta']['record_count'] == 17303") == 1
    text = text.replace("assert reg['meta']['record_count'] == 17303", "assert reg['meta']['record_count'] == 17714", 1)
    authorities = "'udine','bergamo','barletta-andria-trani'}"
    assert text.count(authorities) == 1
    text = text.replace(authorities, "'udine','bergamo','barletta-andria-trani','brindisi'}", 1)
    registers = "'udine-ordinary','bergamo-ordinary','barletta-andria-trani-ordinary'\n          }"
    assert text.count(registers) == 1
    text = text.replace(registers, "'udine-ordinary','bergamo-ordinary','barletta-andria-trani-ordinary','brindisi-ordinary'\n          }", 1)
    assert text.count("assert reg['meta']['authority_count'] == 20") == 1
    text = text.replace("assert reg['meta']['authority_count'] == 20", "assert reg['meta']['authority_count'] == 21", 1)
    assert text.count("assert reg['meta']['register_count'] == 21") == 1
    text = text.replace("assert reg['meta']['register_count'] == 21", "assert reg['meta']['register_count'] == 22", 1)
    assert text.count("assert pref['meta']['published_count'] == 20") == 1
    text = text.replace("assert pref['meta']['published_count'] == 20", "assert pref['meta']['published_count'] == 21", 1)
    anchor = "          barletta = [x for x in pref['prefectures'] if x['authority_key'] == 'barletta-andria-trani']\n          assert len(barletta) == 1 and barletta[0]['mapped'] and barletta[0]['published']\n"
    assert text.count(anchor) == 1
    text = text.replace(anchor, anchor + "          brindisi = [x for x in pref['prefectures'] if x['authority_key'] == 'brindisi']\n          assert len(brindisi) == 1 and brindisi[0]['mapped'] and brindisi[0]['published']\n", 1)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    update_public_config()
    update_coverage()
    update_csvs()
    update_registry_binding()
    update_browser_test()
    update_operations_test()
    write_docs()
    update_pages_gate()


if __name__ == "__main__":
    main()

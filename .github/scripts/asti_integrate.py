from __future__ import annotations

import csv
import json
from pathlib import Path

SOURCE_PAGE = "https://prefettura.interno.gov.it/it/prefetture/asti/white-list-provinciali"
REFERENCE_DATE = "2026-08-03"
VERIFIED_ON = "2026-09-10"
LISTED_SHA = "8c26313c57588745e92600961e7071d4ff2246ab86555e39500f17f59c41c128"
APPLICANT_SHA = "ae5d69a85541dae61ffd67f4983a78831f2a97d096bd752aeb8b93c9a88943a5"


def rewrite_csv(path: str, mutate) -> None:
    p = Path(path)
    with p.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    mutate(rows)
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def bind_parser() -> None:
    path = Path("src/white_list_archive/publishing/public_national_registry.py")
    text = path.read_text(encoding="utf-8")
    import_anchor = "from white_list_archive.parsers.benevento_positioned import PARSERS as BENEVENTO_PARSERS\n"
    chain_anchor = "        or BENEVENTO_PARSERS.get(cfg[\"parser\"])\n"
    assert "ASTI_PARSERS" not in text
    assert text.count(import_anchor) == 1
    assert text.count(chain_anchor) == 1
    text = text.replace(
        import_anchor,
        import_anchor + "from white_list_archive.parsers.asti_positioned import PARSERS as ASTI_PARSERS\n",
    )
    text = text.replace(chain_anchor, chain_anchor + "        or ASTI_PARSERS.get(cfg[\"parser\"])\n")
    path.write_text(text, encoding="utf-8")


def update_publication_config() -> None:
    path = Path("data/publication/multi_prefecture_pilot.json")
    config = json.loads(path.read_text(encoding="utf-8"))
    assert not any(source["source_key"].startswith("asti-") for source in config["sources"])
    common = {
        "authority_key": "asti",
        "authority_name": "Prefettura di Asti",
        "register_key": "asti-ordinary",
        "register_name": "White List ordinaria",
        "reference_date": REFERENCE_DATE,
        "source_page_url": SOURCE_PAGE,
        "last_source_update": REFERENCE_DATE,
        "last_source_update_basis": "explicit current-edition attachment labels and page update timestamp on the official Prefecture page",
    }
    config["sources"].extend(
        [
            {
                **common,
                "source_key": "asti-listed",
                "parser": "asti_listed",
                "population_scope": "listed",
                "resource_url": "https://prefettura.interno.gov.it/sites/default/files/26/2026-09/ditte-iscritte.pdf",
                "sha256": LISTED_SHA,
                "expected_sector_rows": 521,
                "expected_source_rows": 284,
                "notes": "Sections I-X parsed from ruled-table geometry and exact primary-date positions. Only rows sharing the same cleaned identity, dates, raw update text and source status are grouped. CEIT SRL with no listing date and explicit 'In istruttoria' remains pending; malformed expiry values remain raw.",
            },
            {
                **common,
                "source_key": "asti-applicants",
                "parser": "asti_applicants",
                "population_scope": "applicant",
                "resource_url": "https://prefettura.interno.gov.it/sites/default/files/26/2026-09/ditte_in_istruttoria.pdf",
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 17,
                "notes": "17 official applicant observations. Two blank application dates remain blank; the ten-digit JOKKO identifier remains raw. 'Iscritta' maps only to observed listed, 'In istruttoria' to pending, and 'Non iscritta' to other/unknown without inferring rejection or cancellation.",
            },
        ]
    )
    config["verified_at"] = VERIFIED_ON
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_source_registry() -> None:
    def primary(rows):
        matches = [row for row in rows if row["authority_key"] == "asti"]
        assert len(matches) == 1
        matches[0].update(
            {
                "landing_url": SOURCE_PAGE,
                "verification_date": VERIFIED_ON,
                "verification_status": "verified",
            }
        )

    rewrite_csv("data/source_registry/verified_primary_pages.csv", primary)

    def series(rows):
        notes = {
            "asti-listed": "Current official provincial page verified 10 September 2026 explicitly labels the registered-company PDF as updated 3 August 2026. Exact source identity, exceptions and parser boundary are documented in docs/sources/asti-operational-check-2026-09-10.md.",
            "asti-applicants": "Current official provincial page verified 10 September 2026 explicitly labels the applicant-company PDF as updated 3 August 2026. Exact source identity, raw anomalies and parser boundary are documented in docs/sources/asti-operational-check-2026-09-10.md.",
        }
        for key, note in notes.items():
            matches = [row for row in rows if row["source_series_key"] == key]
            assert len(matches) == 1
            matches[0].update(
                {
                    "verified_date": VERIFIED_ON,
                    "resource_resolution_status": "direct_series_page_resolved",
                    "notes": note,
                }
            )

    rewrite_csv("data/source_registry/source_series_inventory.csv", series)


def update_coverage() -> None:
    path = Path("data/monitoring/national_coverage.json")
    coverage = json.loads(path.read_text(encoding="utf-8"))
    matches = [row for row in coverage["prefectures"] if row["authority_key"] == "asti"]
    assert len(matches) == 1
    matches[0].update(
        {
            "current_edition_identified": True,
            "capture_implemented": True,
            "parser_implemented": True,
            "parser_validated": True,
            "company_observations_loaded": True,
            "observation_layer": "public_source_observations",
            "canonical_integration_validated": False,
            "public_export_enabled": True,
            "durable_evidence_verified": False,
            "latest_source_reference_date": REFERENCE_DATE,
            "last_successful_source_check_at": "2026-09-10T06:24:01Z",
            "last_attempted_source_check_at": "2026-09-10T06:24:01Z",
            "last_successful_investigation_on": VERIFIED_ON,
            "monitoring_status": "CURRENT",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/asti-operational-check-2026-09-10.md",
                "src/white_list_archive/parsers/asti_positioned.py",
                "tests/test_asti_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANT_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/asti-operational-check-2026-09-10.md",
            ],
        }
    )
    path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_public_gates() -> None:
    pages = Path(".github/workflows/public-pages.yml")
    text = pages.read_text(encoding="utf-8")
    parser_anchor = "      - 'src/white_list_archive/parsers/benevento_positioned.py'\n"
    assert text.count(parser_anchor) == 1
    text = text.replace(parser_anchor, parser_anchor + "      - 'src/white_list_archive/parsers/asti_positioned.py'\n")
    replacements = {
        "assert reg['meta']['record_count'] == 8522": "assert reg['meta']['record_count'] == 8823",
        "assert set(reg['meta']['authority_counts']) == {'cosenza','parma','pistoia','bologna','alessandria','aosta','arezzo','avellino','pesaro-e-urbino','biella','benevento'}": "assert set(reg['meta']['authority_counts']) == {'cosenza','parma','pistoia','bologna','alessandria','aosta','arezzo','avellino','pesaro-e-urbino','biella','benevento','asti'}",
        "'biella-ordinary','benevento-ordinary'": "'biella-ordinary','benevento-ordinary','asti-ordinary'",
        "assert reg['meta']['authority_count'] == 11": "assert reg['meta']['authority_count'] == 12",
        "assert reg['meta']['register_count'] == 12": "assert reg['meta']['register_count'] == 13",
        "assert pref['meta']['published_count'] == 11": "assert pref['meta']['published_count'] == 12",
    }
    for old, new in replacements.items():
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    anchor = "          benevento = [x for x in pref['prefectures'] if x['authority_key'] == 'benevento']\n          assert len(benevento) == 1 and benevento[0]['mapped'] and benevento[0]['published']\n"
    assert text.count(anchor) == 1
    text = text.replace(
        anchor,
        anchor + "          asti = [x for x in pref['prefectures'] if x['authority_key'] == 'asti']\n          assert len(asti) == 1 and asti[0]['mapped'] and asti[0]['published']\n",
    )
    pages.write_text(text, encoding="utf-8")

    browser = Path("tests/public_portal_browser.cjs")
    text = browser.read_text(encoding="utf-8")
    label_anchor = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Benevento'));\n"
    assert text.count(label_anchor) == 1
    text = text.replace(label_anchor, label_anchor + "      assert.ok(labels.includes('White List ordinaria · Prefettura di Asti'));\n")
    assert text.count("assert.equal(stats.total,8522);") == 1
    text = text.replace("assert.equal(stats.total,8522);", "assert.equal(stats.total,8823);")
    old = "['alessandria','aosta','arezzo','avellino','pesaro-e-urbino','biella','benevento']"
    assert text.count(old) == 1
    text = text.replace(old, "['alessandria','aosta','arezzo','avellino','pesaro-e-urbino','biella','benevento','asti']")
    anchor = "      assert.deepEqual(statusCounts(benevento),{listed:734,pending:204});\n"
    assert text.count(anchor) == 1
    text = text.replace(
        anchor,
        anchor
        + "      const asti=registry.records.filter(r=>r.authority_key==='asti');\n"
        + "      assert.equal(asti.length,301);\n"
        + "      assert.equal(asti.filter(r=>r.source_key==='asti-listed').length,284);\n"
        + "      assert.equal(asti.filter(r=>r.source_key==='asti-applicants').length,17);\n"
        + "      assert.deepEqual(statusCounts(asti),{listed:287,other_or_unknown:1,pending:13});\n",
    )
    browser.write_text(text, encoding="utf-8")


def write_tests_and_docs() -> None:
    Path("tests/test_asti_parser_semantics.py").write_text(
        """from white_list_archive.parsers.asti_positioned import _activity_parts, _status_applicant


def test_asti_applicant_status_mapping_is_source_literal_and_conservative():
    assert _status_applicant('In istruttoria') == 'pending'
    assert _status_applicant('Iscritta il 24.08.2026') == 'listed'
    assert _status_applicant('Non iscritta') == 'other_or_unknown'
    assert _status_applicant('') == 'other_or_unknown'


def test_asti_multi_section_applicant_activity_is_split_without_relabelling():
    activities, sections = _activity_parts('SEZIONE IV Fornitura di ferro lavorato SEZIONE VI Autotrasporto conto terzi')
    assert sections == ['Sezione IV', 'Sezione VI']
    assert activities == ['Fornitura di ferro lavorato', 'Autotrasporto conto terzi']
""",
        encoding="utf-8",
    )
    Path("docs/sources/asti-operational-check-2026-09-10.md").write_text(
        f"""# Asti White List operational check — 10 September 2026

## Official current surface

The official Prefettura di Asti White List page was verified on 10 September 2026: {SOURCE_PAGE}. It explicitly labels both `Elenco imprese iscritte` and `Elenco imprese richiedenti l'iscrizione` as `Aggiornato al 03/08/2026`; the page itself reports its latest update as 3 August 2026. This is positive current-edition evidence for both ordinary White List populations. The September directory component in the attachment URLs is not treated as publication-date evidence.

## Byte-pinned resources

Registered-company resource: `https://prefettura.interno.gov.it/sites/default/files/26/2026-09/ditte-iscritte.pdf`, SHA-256 `{LISTED_SHA}`, 39 pages.

Applicant resource: `https://prefettura.interno.gov.it/sites/default/files/26/2026-09/ditte_in_istruttoria.pdf`, SHA-256 `{APPLICANT_SHA}`, 6 pages.

## Parser boundary and validated output

The registered-company PDF is organised by Sections I-X. `asti_listed` uses ruled-table geometry and the position of the primary registration/renewal date. The audited edition contains 521 sector observations, conservatively grouped into 284 public source observations. One CEIT SRL row has no listing date and explicitly reports `In istruttoria`; it remains pending. Seven malformed expiry values remain raw and are not reconstructed.

The applicant PDF yields 17 source observations. Two application dates are blank and remain blank. The ten-digit JOKKO identifier `0141215742` remains raw and is not padded. Source-explicit outcomes map conservatively: four `Iscritta` observations to listed, twelve `In istruttoria` observations to pending, and one `Non iscritta` observation to `other_or_unknown`.

The combined Asti public contribution is 301 observations: 287 listed, 13 pending and 1 other/unknown.

## Publication gate

Publication pins the exact two resource SHA-256 values and the 521/284/17 denominators. Byte drift, page/layout drift, changed denominators, loss of the explicit pending exception or new invalid non-blank applicant dates fail closed. Canonical hosted-database integration and independent durable-evidence verification remain separate under issue #16 and are not claimed complete here.
""",
        encoding="utf-8",
    )


def main() -> None:
    bind_parser()
    update_publication_config()
    update_source_registry()
    update_coverage()
    update_public_gates()
    write_tests_and_docs()


if __name__ == "__main__":
    main()

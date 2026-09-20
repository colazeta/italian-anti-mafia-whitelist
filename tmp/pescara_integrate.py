from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LISTED_PAGE = "https://prefettura.interno.gov.it/it/prefetture/pescara/evidenza/white-list"
APPLICANT_PAGE = "https://prefettura.interno.gov.it/it/prefetture/pescara/elenco-imprese-richiedenti-liscrizione-nelle-white-list"
LISTED_RESOURCE = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/white-list-2026.doc"
APPLICANT_RESOURCE = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco_richiedenti_white-list_04.09.2026.doc"
LISTED_SHA = "6a8aa832db7d0f55c17d9ed1f8179d9ed46a7c927b5b88d85319f79a1da92239"
APPLICANT_SHA = "2a0f74ab6548ad2418f539aba7fc2eaf0d23998b709b0bc247e512d7b46a578c"


def patch_registry() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    import_line = "from white_list_archive.parsers.pescara_legacy_doc import PARSERS as PESCARA_PARSERS\n"
    import_anchor = "from white_list_archive.parsers.ravenna_combined import PARSERS as RAVENNA_PARSERS\n"
    if import_line not in text:
        if import_anchor not in text:
            raise RuntimeError("Ravenna parser import anchor drift")
        text = text.replace(import_anchor, import_anchor + import_line, 1)
    chain_line = '        or PESCARA_PARSERS.get(cfg["parser"])\n'
    chain_anchor = '        or RAVENNA_PARSERS.get(cfg["parser"])\n'
    if chain_line not in text:
        if chain_anchor not in text:
            raise RuntimeError("Ravenna parser chain anchor drift")
        text = text.replace(chain_anchor, chain_anchor + chain_line, 1)
    path.write_text(text, encoding="utf-8")


def patch_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    existing = [source for source in cfg["sources"] if source.get("authority_key") == "pescara"]
    if existing:
        expected_keys = {"pescara-listed", "pescara-applicants"}
        if {source.get("source_key") for source in existing} != expected_keys:
            raise RuntimeError(f"Unexpected pre-existing Pescara publication sources: {existing!r}")
        return
    common = {
        "authority_key": "pescara",
        "authority_name": "Prefettura di Pescara",
        "register_key": "pescara-ordinary",
        "register_name": "White List ordinaria",
    }
    cfg["sources"].extend(
        [
            {
                **common,
                "source_key": "pescara-listed",
                "parser": "pescara_legacy_listed",
                "population_scope": "listed",
                "reference_date": "2026-09-16",
                "source_page_url": LISTED_PAGE,
                "resource_url": LISTED_RESOURCE,
                "sha256": LISTED_SHA,
                "expected_sector_rows": 1060,
                "expected_source_rows": 607,
                "last_source_update": "2026-09-16",
                "last_source_update_basis": "dated official resource directly repeat-fetched and byte-pinned 21 September 2026",
                "notes": "Byte-pinned legacy Word listed series. Exact full-row grouping yields 607 observations from 1,060 company-by-section rows: 456 listed, 150 renewal/update in progress and one other/unknown source marker. Reviewed malformed identifiers and dates remain raw and uninferred.",
            },
            {
                **common,
                "source_key": "pescara-applicants",
                "parser": "pescara_legacy_applicants",
                "population_scope": "applicant",
                "reference_date": "2026-09-04",
                "source_page_url": APPLICANT_PAGE,
                "resource_url": APPLICANT_RESOURCE,
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 35,
                "last_source_update": "2026-09-04",
                "last_source_update_basis": "dated official resource directly repeat-fetched and byte-pinned 21 September 2026",
                "notes": "Byte-pinned legacy Word applicant series. Thirty-six physical data rows yield 35 observations after one exact reviewed continuation row for CALISTA IMPIANTI SRL; all 35 are source-positive pending applicants. One malformed identifier remains raw-only.",
            },
        ]
    )
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_csv(path: Path, key: str, new_rows: list[dict[str, str]], sort_key: str) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"Cannot infer CSV schema from empty {path}")
    fieldnames = list(rows[0].keys())
    extras = sorted(set().union(*(set(row) for row in new_rows)) - set(fieldnames))
    missing = sorted(set(fieldnames) - set().union(*(set(row) for row in new_rows)))
    if extras or missing:
        raise RuntimeError(f"CSV schema mismatch for {path}: extras={extras}, missing={missing}")
    existing = [row for row in rows if row.get(key) in {new_row[key] for new_row in new_rows}]
    if existing:
        expected = {new_row[key]: new_row for new_row in new_rows}
        if {row[key]: row for row in existing} != expected:
            raise RuntimeError(f"Pre-existing {path.name} Pescara rows differ from candidate")
        return
    rows.extend(new_rows)
    rows.sort(key=lambda row: row[sort_key])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def patch_source_registry() -> None:
    patch_csv(
        ROOT / "data/source_registry/verified_primary_pages.csv",
        "authority_key",
        [
            {
                "authority_key": "pescara",
                "landing_url": LISTED_PAGE,
                "verification_date": "2026-09-21",
                "verification_status": "verified",
            }
        ],
        "authority_key",
    )
    patch_csv(
        ROOT / "data/source_registry/source_series_inventory.csv",
        "source_series_key",
        [
            {
                "source_series_key": "pescara-listed",
                "authority_key": "pescara",
                "register_regime_code": "WL-REGIME-L190-2012",
                "population_scope": "listed",
                "activity_scope": "all",
                "publication_model": "periodic_attachment",
                "landing_url": LISTED_PAGE,
                "resolution_status": "landing_page_resolved",
                "verified_on": "2026-09-21",
                "notes": "Current official Pescara listed landing directly verified 21 September 2026 and positively exposes White list 16/09/2026. Two independent captures of the legacy Word attachment are byte-identical at SHA-256 6a8aa832db7d0f55c17d9ed1f8179d9ed46a7c927b5b88d85319f79a1da92239. Exact full-row grouping yields 607 observations from 1,060 company-by-section rows; raw malformed identifiers/dates and the single nonstandard status token are not repaired by inference.",
            },
            {
                "source_series_key": "pescara-applicants",
                "authority_key": "pescara",
                "register_regime_code": "WL-REGIME-L190-2012",
                "population_scope": "applicant",
                "activity_scope": "all",
                "publication_model": "periodic_attachment",
                "landing_url": APPLICANT_PAGE,
                "resolution_status": "direct_series_page_resolved",
                "verified_on": "2026-09-21",
                "notes": "Current official Pescara applicant page directly verified 21 September 2026 and positively exposes Elenco richiedenti White List - 04.09.2026. Two independent captures are byte-identical at SHA-256 2a0f74ab6548ad2418f539aba7fc2eaf0d23998b709b0bc247e512d7b46a578c. Thirty-six physical rows yield 35 applicant observations after one exact reviewed continuation; no applicant status is inferred from absence.",
            },
        ],
        "source_series_key",
    )


def write_operational_doc() -> None:
    path = ROOT / "docs/sources/pescara-operational-check-2026-09-21.md"
    path.write_text(
        """# Pescara White List operational check — 21 September 2026

## Official publication evidence

The current official Prefettura di Pescara surfaces positively expose both populations. The listed landing is `https://prefettura.interno.gov.it/it/prefetture/pescara/evidenza/white-list` and direct verification exposed **White list 16/09/2026**. The applicant page is `https://prefettura.interno.gov.it/it/prefetture/pescara/elenco-imprese-richiedenti-liscrizione-nelle-white-list` and exposed **Elenco richiedenti White List - 04.09.2026**. A separate client returning HTTP 403 is not negative publication evidence; source identity was established by successful official-site retrieval in the validation runner.

Two independent downloads of each current resource were byte-identical. Both are legacy Microsoft Word/OLE documents and are parsed with `antiword` in fail-closed mode.

| population | resource | bytes | SHA-256 |
|---|---|---:|---|
| listed | `white-list-2026.doc` | 1,967,616 | `6a8aa832db7d0f55c17d9ed1f8179d9ed46a7c927b5b88d85319f79a1da92239` |
| applicants | `elenco_richiedenti_white-list_04.09.2026.doc` | 350,720 | `2a0f74ab6548ad2418f539aba7fc2eaf0d23998b709b0bc247e512d7b46a578c` |

## Listed population

The source contains ten statutory White List sections represented through 13 seven-column table groups and 1,060 physical company×section rows. Exact full-row grouping produces **607 logical observations** and 1,058 unique section memberships; two exact repeated memberships inside the same section are treated as source duplicates rather than additional activities.

The frozen status boundary is **456 listed, 150 renewal/update in progress, and 1 other/unknown**. Only a blank update field maps to `listed`; exact `IN RINNOVO` maps to `renewal_update_in_progress`; the single source token `I` is deliberately retained as `other_or_unknown`. Any new status token fails validation.

Structured identifier coverage is **579/607**. Twenty-eight observations contain source identifiers that do not satisfy accepted 11-digit/16-character shapes and remain raw-only. Seven malformed source date tokens are likewise retained as raw evidence and are not repaired: `21/052024`, `13/07/20222`, `23701/2026`, `09/06/20206`, `22/12/202`, `30707/2024`, `29/10/204`.

## Applicant population

The applicant source contains two six-column table groups, one exact header and **36 physical data rows**. Physical row 6 is a continuation of the preceding `CALISTA IMPIANTI SRL` row: the first fragment contains company/office/identifier while the second carries the requested activity and application date `01.10.2025`. The parser permits that merge only for this exact reviewed owner and shape and therefore emits **35 applicant observations**, all `pending` on positive applicant-source evidence.

Structured identifier coverage is **34/35**; source value `0285069069` remains raw-only. Applicant dates contain no reviewed malformed values. Blank names elsewhere, row-width/header drift, a changed continuation shape, or an unreviewed malformed applicant date fail closed.

## Publication boundary

Pescara contributes **642 observations** to one ordinary register: 607 listed-side observations plus 35 applicant observations. Structured identifier coverage is **613/642**. Parser validation is byte-pinned to the two hashes above. Source anomalies remain provenance and are never silently normalised.
""",
        encoding="utf-8",
    )


def write_test() -> None:
    path = ROOT / "tests/test_pescara_legacy_doc.py"
    path.write_text(
        '''from __future__ import annotations\n\nfrom pathlib import Path\n\nimport pytest\n\nfrom white_list_archive.parsers.pescara_legacy_doc import PARSERS, parse_pescara_listed\n\n\ndef test_pescara_parsers_registered() -> None:\n    assert set(PARSERS) == {"pescara_legacy_listed", "pescara_legacy_applicants"}\n\n\ndef test_pescara_listed_reference_date_fails_closed_before_io() -> None:\n    cfg = {"source_key": "pescara-listed", "authority_key": "pescara", "reference_date": "2026-09-15"}\n    with pytest.raises(RuntimeError, match="reference-date drift"):\n        parse_pescara_listed(Path("does-not-exist.doc"), cfg)\n''',
        encoding="utf-8",
    )


def materialise() -> None:
    patch_registry()
    patch_publication_config()
    patch_source_registry()
    write_operational_doc()
    write_test()


def validate_candidate(registry_path: Path, prefectures_path: Path, output_path: Path) -> None:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    prefectures = json.loads(prefectures_path.read_text(encoding="utf-8"))
    records = [record for record in registry["records"] if record["authority_key"] == "pescara"]
    if len(records) != 642:
        raise RuntimeError(f"Pescara record boundary drift: {len(records)} != 642")
    expectations = {
        "pescara-listed": 607,
        "pescara-applicants": 35,
    }
    for source_key, expected in expectations.items():
        actual = sum(record["source_key"] == source_key for record in records)
        if actual != expected:
            raise RuntimeError(f"{source_key} boundary drift: {actual} != {expected}")
    statuses = {
        "listed": 456,
        "renewal_update_in_progress": 150,
        "other_or_unknown": 1,
        "pending": 35,
    }
    for status, expected in statuses.items():
        actual = sum(record["source_status"] == status for record in records)
        if actual != expected:
            raise RuntimeError(f"Pescara {status} drift: {actual} != {expected}")
    identifiers = sum(bool(record["identifiers"]) for record in records)
    if identifiers != 613:
        raise RuntimeError(f"Pescara identifier coverage drift: {identifiers} != 613")
    rows = [row for row in prefectures["prefectures"] if row["authority_key"] == "pescara"]
    if len(rows) != 1 or not rows[0]["mapped"] or not rows[0]["published"] or rows[0]["series_count"] != 2:
        raise RuntimeError(f"Pescara prefecture summary drift: {rows!r}")
    summary = {
        "registry_records": registry["meta"]["record_count"],
        "authorities_published": registry["meta"]["authority_count"],
        "registers_published": registry["meta"]["register_count"],
        "mapped_prefectures": prefectures["meta"]["mapped_count"],
        "published_prefectures": prefectures["meta"]["published_count"],
        "pescara_records": len(records),
        "pescara_identified_records": identifiers,
        "pescara_status_counts": statuses,
    }
    expected_national = {
        "registry_records": 73098,
        "authorities_published": 71,
        "registers_published": 74,
        "mapped_prefectures": 71,
        "published_prefectures": 71,
    }
    for key, expected in expected_national.items():
        if summary[key] != expected:
            raise RuntimeError(f"National candidate {key} drift: {summary[key]} != {expected}")
    output_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("materialise")
    validate = subparsers.add_parser("validate")
    validate.add_argument("--registry", type=Path, required=True)
    validate.add_argument("--prefectures", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "materialise":
        materialise()
    else:
        validate_candidate(args.registry, args.prefectures, args.output)


if __name__ == "__main__":
    main()

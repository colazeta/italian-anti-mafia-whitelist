from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/piacenza/evidenza/white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/65/2026-09/ditte-white-list-copia_2.zip"
APPLICANTS_URL = "https://prefettura.interno.gov.it/sites/default/files/65/2026-02/elenco_imprese_richiedenti_l-iscrizione_nell-elenco_dei_fornitori-prestatori_di_servizi_ed_esecutori_di_lavori_non_soggetti_a_tentativi_di_infiltrazione_mafiosa-i.zip"
LISTED_SHA = "e53d2f0a1c044efb2b28adf058893c4d482b2262396f936dc17a93a43f7aaea8"
APPLICANTS_SHA = "99e2809359df95497ea921fdc69b2c4e826112ab4cd5d31209b38110a3c4d335"
REFERENCE_DATE = "2026-09-21"
CHECK_AT = "2026-09-21T01:47:36Z"
DOC = "docs/sources/piacenza-operational-check-2026-09-21.md"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def patch_verified_pages() -> int:
    path = ROOT / "data/source_registry/verified_primary_pages.csv"
    fields, rows = read_csv(path)
    matches = [row for row in rows if row["authority_key"] == "piacenza"]
    expected = {
        "authority_key": "piacenza",
        "landing_url": LANDING,
        "verification_date": REFERENCE_DATE,
        "verification_status": "verified",
    }
    if matches and matches != [expected]:
        raise SystemExit(f"Unexpected existing Piacenza primary-page row: {matches!r}")
    if not matches:
        rows.append(expected)
    rows.sort(key=lambda row: row["authority_key"])
    if len({row["authority_key"] for row in rows}) != len(rows):
        raise SystemExit("Duplicate verified primary-page authority key")
    write_csv(path, fields, rows)
    return len(rows)


def patch_series() -> int:
    path = ROOT / "data/source_registry/source_series_inventory.csv"
    fields, rows = read_csv(path)
    expected = {
        "piacenza-listed": {
            "source_series_key": "piacenza-listed",
            "authority_key": "piacenza",
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "listed",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": LANDING,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": REFERENCE_DATE,
            "notes": (
                "Current official Piacenza landing directly verified 21 September 2026 and positively exposes the registered-company ZIP. "
                f"Two independent captures are byte-identical at SHA-256 {LISTED_SHA}. The legacy XLS yields 552 source observations "
                "(455 listed; 97 renewal/update in progress); raw malformed identifiers/dates and the reviewed III.V activity token are not repaired by inference. "
                f"Exact evidence: {DOC}."
            ),
        },
        "piacenza-applicants": {
            "source_series_key": "piacenza-applicants",
            "authority_key": "piacenza",
            "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "applicant",
            "sector_scope": "all",
            "publication_model": "periodic_attachment",
            "series_url": LANDING,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": REFERENCE_DATE,
            "notes": (
                "Current official Piacenza landing directly verified 21 September 2026 and positively exposes the requesting-company ZIP. "
                f"Two independent captures are byte-identical at SHA-256 {APPLICANTS_SHA}. The legacy XLS yields exactly 18 pending applicant observations; "
                "the February path is not interpreted as a legal/publication date or as evidence of incompleteness. "
                f"Exact evidence: {DOC}."
            ),
        },
    }
    existing = {row["source_series_key"]: row for row in rows if row["source_series_key"].startswith("piacenza-")}
    if existing and existing != expected:
        raise SystemExit(f"Unexpected existing Piacenza source-series rows: {existing!r}")
    if not existing:
        rows.extend(expected.values())
    rows.sort(key=lambda row: row["source_series_key"])
    if len({row["source_series_key"] for row in rows}) != len(rows):
        raise SystemExit("Duplicate source-series key")
    write_csv(path, fields, rows)
    return len(rows)


def patch_catalog(page_count: int, series_count: int) -> None:
    path = ROOT / "data/catalog.csv"
    fields, rows = read_csv(path)
    by_id = {row["dataset_id"]: row for row in rows}
    if "verified-primary-pages" not in by_id or "source-series-inventory" not in by_id:
        raise SystemExit("Catalog source-registry rows missing")
    by_id["verified-primary-pages"]["record_count"] = str(page_count)
    by_id["source-series-inventory"]["record_count"] = str(series_count)
    write_csv(path, fields, rows)


def source_config(source_key: str) -> dict:
    common = {
        "authority_key": "piacenza",
        "authority_name": "Prefettura di Piacenza",
        "register_key": "piacenza-ordinary",
        "register_name": "White List ordinaria",
        "reference_date": REFERENCE_DATE,
        "source_page_url": LANDING,
        "last_source_update": REFERENCE_DATE,
        "approval_mode": "raw_sha256",
    }
    if source_key == "piacenza-listed":
        return {
            "source_key": source_key,
            "parser": "piacenza_legacy_listed",
            **common,
            "population_scope": "listed",
            "resource_url": LISTED_URL,
            "sha256": LISTED_SHA,
            "expected_source_rows": 552,
            "last_source_update_basis": "current official mutable resource observed, repeat-fetched and byte-pinned on 21 September 2026; no legal or publication date inferred from page or workbook metadata",
            "notes": "552 source observations; 455 listed and 97 renewal/update in progress; 540 structured identifiers, 12 raw-only identifiers; seven listing and seven expiry date strings preserved raw.",
        }
    if source_key == "piacenza-applicants":
        return {
            "source_key": source_key,
            "parser": "piacenza_legacy_applicants",
            **common,
            "population_scope": "applicant",
            "resource_url": APPLICANTS_URL,
            "sha256": APPLICANTS_SHA,
            "expected_source_rows": 18,
            "last_source_update_basis": "current official mutable resource observed, repeat-fetched and byte-pinned on 21 September 2026; resource path date is not treated as a legal/publication date",
            "notes": "18 source-positive applicant observations, all pending and all with structured identifiers.",
        }
    raise KeyError(source_key)


def patch_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data.get("sources")
    if not isinstance(sources, list):
        raise SystemExit("Publication config has no source list")
    expected = {key: source_config(key) for key in ("piacenza-listed", "piacenza-applicants")}
    existing = {source["source_key"]: source for source in sources if source.get("source_key", "").startswith("piacenza-")}
    if existing and existing != expected:
        raise SystemExit(f"Unexpected existing Piacenza publication config: {existing!r}")
    if not existing:
        sources.extend(expected.values())
    keys = [source["source_key"] for source in sources]
    if len(keys) != len(set(keys)):
        raise SystemExit("Duplicate publication source key")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_monitoring() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in data.get("prefectures", []) if item.get("authority_key") == "piacenza"]
    if len(matches) != 1:
        raise SystemExit(f"Expected one Piacenza monitoring object, got {len(matches)}")
    item = matches[0]
    item.update(
        {
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
            "latest_source_reference_date": REFERENCE_DATE,
            "last_successful_source_check_at": CHECK_AT,
            "last_attempted_source_check_at": CHECK_AT,
            "last_content_change_at": None,
            "last_successful_investigation_on": REFERENCE_DATE,
            "monitoring_status": "CURRENT",
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                DOC,
                "src/white_list_archive/parsers/piacenza_legacy_xls.py",
                "tests/test_piacenza_legacy_xls.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANTS_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                DOC,
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {label} insertion point, got {count}")
    return text.replace(old, new, 1)


def patch_dispatcher() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    import_line = "from white_list_archive.parsers.pescara_legacy_doc import PARSERS as PESCARA_PARSERS\n"
    if "PIACENZA_PARSERS" not in text:
        text = replace_once(
            text,
            import_line,
            import_line + "from white_list_archive.parsers.piacenza_legacy_xls import PARSERS as PIACENZA_PARSERS\n",
            "Piacenza parser import",
        )
    adapter_marker = "\ndef _parse_source(path: Path | dict[str, Path], cfg: dict[str, Any]) -> ParsedBatch:\n"
    if "def _adapt_piacenza_public_fields" not in text:
        adapter = '''\n\ndef _adapt_piacenza_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    adapted: list[dict[str, Any]] = []\n    for original in batch.records:\n        record = dict(original)\n        fields = dict(record.get("source_fields", {}))\n        if parser_name == "piacenza_legacy_listed":\n            registration = fields.pop("registration_number", None)\n            if not isinstance(registration, str) or not registration:\n                raise RuntimeError("Piacenza listed registration-number evidence drift")\n        elif parser_name == "piacenza_legacy_applicants":\n            if "registration_number" in fields:\n                raise RuntimeError("Piacenza applicant unexpected registration-number field")\n        else:\n            raise RuntimeError(f"Unexpected Piacenza parser: {parser_name!r}")\n        record["source_fields"] = fields\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n'''
        text = replace_once(text, adapter_marker, adapter + adapter_marker, "Piacenza public adapter")
    lookup = "        or PESCARA_PARSERS.get(cfg[\"parser\"])\n"
    if "or PIACENZA_PARSERS.get" not in text:
        text = replace_once(text, lookup, lookup + "        or PIACENZA_PARSERS.get(cfg[\"parser\"])\n", "Piacenza parser lookup")
    adaptation = "    if cfg[\"parser\"] in RAVENNA_PARSERS:\n        batch = _adapt_ravenna_public_fields(batch, cfg[\"parser\"])\n"
    if "batch = _adapt_piacenza_public_fields" not in text:
        text = replace_once(
            text,
            adaptation,
            adaptation + "    if cfg[\"parser\"] in PIACENZA_PARSERS:\n        batch = _adapt_piacenza_public_fields(batch, cfg[\"parser\"])\n",
            "Piacenza public adaptation",
        )
    path.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = ROOT / "tests/test_source_registry.py"
    text = path.read_text(encoding="utf-8")
    if "assert len(pages) == 72" not in text:
        text = replace_once(text, "assert len(pages) == 71", "assert len(pages) == 72", "verified-page denominator")
    path.write_text(text, encoding="utf-8")

    path = ROOT / "tests/test_source_population_coverage.py"
    text = path.read_text(encoding="utf-8")
    replacements = {
        'assert report["verified_authority_count"] == 71': 'assert report["verified_authority_count"] == 72',
        'assert report["register_scope_count"] == 74': 'assert report["register_scope_count"] == 75',
        'assert report["complete_register_scope_count"] == 74': 'assert report["complete_register_scope_count"] == 75',
    }
    for old, new in replacements.items():
        if new not in text:
            text = replace_once(text, old, new, old)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    page_count = patch_verified_pages()
    series_count = patch_series()
    if page_count != 72:
        raise SystemExit(f"Verified-page denominator drift: expected 72, got {page_count}")
    if series_count != 143:
        raise SystemExit(f"Source-series denominator drift: expected 143, got {series_count}")
    patch_catalog(page_count, series_count)
    patch_publication_config()
    patch_monitoring()
    patch_dispatcher()
    patch_tests()
    print(json.dumps({"verified_pages": page_count, "source_series": series_count, "candidate_records": 73668, "candidate_authorities": 72, "candidate_registers": 75, "candidate_mapped": 72}, indent=2))


if __name__ == "__main__":
    main()

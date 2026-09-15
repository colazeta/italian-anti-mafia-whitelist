from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/potenza/white-list"
APP = "https://www.utgpotenza.it/_whitelist.php"
RESOURCE = (
    "https://www.utgpotenza.it/data/vis_imprese.php?action=list&jtStartIndex=0&jtPageSize=2000"
    "&jtSorting=ragione_sociale%20ASC&cerca_ragione_sociale=&cerca_sede_legale="
    "&cerca_stato_richiesta=0&cerca_sezione=0"
)
CAPTURE_SHA = "483f71b0481573651dc62e382e3e3e7a45cfd84509ec79f51a07194dbb3af0a6"
# Independently validated on two byte-identical complete captures. For this
# mutable structured source the digest intentionally covers the full parsed
# source semantics before the separately fail-closed public-field projection.
SEMANTIC_SHA = "c033d7b1f2d758f42e9b0a97d70e8f7f2278cb08608db86c2e7b600e1857cb34"


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one replacement in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def update_source_registry() -> None:
    path = ROOT / "data/source_registry/source_series_inventory.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise RuntimeError("Missing source-series header")
        rows = list(reader)
    matches = [row for row in rows if row["source_series_key"] == "potenza-combined"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Potenza source series, found {len(matches)}")
    row = matches[0]
    if row["authority_key"] != "potenza" or row["publication_model"] != "custom_web_application":
        raise RuntimeError(f"Unexpected pre-existing Potenza source-series semantics: {row!r}")
    row.update(
        {
            "population_scope": "listed_and_applicant",
            "sector_scope": "all",
            "series_url": APP,
            "resource_resolution_status": "linked_application_resolved",
            "verified_date": "2026-09-15",
            "notes": (
                "Current official Ministry landing and linked UTG Potenza web application directly revalidated 15 September 2026. "
                "Two independent complete endpoint captures were byte-identical at SHA-256 483f71b0481573651dc62e382e3e3e7a45cfd84509ec79f51a07194dbb3af0a6 and expose exactly 1,034 current public observations: 217 listed, 375 pending and 442 renewal/update in progress. "
                "The mutable web-app response is approved by full parsed source semantics rather than assumed immutable; exact boundary, status evidence and conservative anomaly handling are documented in docs/sources/potenza-operational-check-2026-09-15.md."
            ),
        }
    )
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8")


def update_monitoring() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in data["prefectures"] if item.get("authority_key") == "potenza"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Potenza monitoring entry, found {len(matches)}")
    item = matches[0]
    if item.get("public_export_enabled") or item.get("parser_validated"):
        raise RuntimeError("Potenza monitoring entry is already promoted; refusing duplicate transaction")
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
            "latest_source_reference_date": "2026-09-15",
            "last_successful_investigation_on": "2026-09-15",
            "unresolved_issue": [
                "The combined list response does not expose per-company statutory sections; requested activities remain empty pending positive evidence from the official child section view rather than inference.",
                "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure.",
            ],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/potenza-operational-check-2026-09-15.md",
                "src/white_list_archive/parsers/potenza_webapp.py",
                "tests/test_potenza_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [CAPTURE_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/potenza-operational-check-2026-09-15.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if any(item.get("authority_key") == "potenza" for item in data["sources"]):
        raise RuntimeError("Potenza already exists in publication configuration")
    data["sources"].append(
        {
            "source_key": "potenza-combined",
            "parser": "potenza_combined",
            "authority_key": "potenza",
            "authority_name": "Prefettura di Potenza",
            "register_key": "potenza-ordinary",
            "register_name": "White List ordinaria",
            "population_scope": "listed_and_applicant",
            "reference_date": "2026-09-15",
            "source_page_url": LANDING,
            "resource_url": RESOURCE,
            "sha256": CAPTURE_SHA,
            "expected_source_rows": 1034,
            "approval_mode": "semantic_sha256",
            "semantic_sha256": SEMANTIC_SHA,
            "last_source_update": "2026-09-15",
            "last_source_update_basis": (
                "current mutable official web-application capture directly verified on this date; "
                "the date is an observation/reference boundary only and is not an inferred source-edition, company-decision or legal-effect date"
            ),
            "notes": (
                "Official Ministry landing links the UTG Potenza public White List web application. "
                "Two complete live captures were byte-identical and yielded 1,034 observations. "
                "Because the endpoint is a mutable current web application, publication is fail-closed on the independently approved full parsed source-semantic digest before closed-contract projection; raw capture SHA-256 remains observation provenance."
            ),
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bind_parser_and_adapter() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    replace_exact(
        path,
        "from white_list_archive.parsers.torino_tables import parse_torino_applicants, parse_torino_listed\n",
        "from white_list_archive.parsers.torino_tables import parse_torino_applicants, parse_torino_listed\n"
        "from white_list_archive.parsers.potenza_webapp import PARSERS as POTENZA_PARSERS\n",
    )
    replace_exact(
        path,
        '        or TORINO_PARSERS.get(cfg["parser"])\n',
        '        or TORINO_PARSERS.get(cfg["parser"])\n        or POTENZA_PARSERS.get(cfg["parser"])\n',
    )
    replace_exact(
        path,
        '    for record in batch.records:\n        record["parser_name"] = cfg["parser"]\n        record["parser_version"] = "2" if cfg["parser"] in NAPOLI_PARSERS else "1"\n',
        '    for record in batch.records:\n        record["parser_name"] = cfg["parser"]\n'
        '        record["parser_version"] = "2" if cfg["parser"] in NAPOLI_PARSERS or cfg["parser"] in POTENZA_PARSERS else "1"\n',
    )
    marker = '\n\ndef _adapt_lodi_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n'
    adapter = '''\n\ndef _adapt_potenza_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    """Project approved Potenza source semantics onto the closed public contract."""\n    if parser_name != "potenza_combined":\n        raise RuntimeError(f"Unexpected Potenza parser: {parser_name!r}")\n    adapted: list[dict[str, Any]] = []\n    expected = {\n        "source_id", "ragione_sociale_raw", "indirizzo_sede_legale_raw",\n        "denom_comune_sede_legale_raw", "richiedente", "carica_sociale_rich",\n        "stato_richiesta", "agg_incorso", "iscriz_scaduta", "note",\n        "data_istanza_raw", "data_iscriz_raw", "data_scad_iscriz_raw",\n    }\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get("source_fields")\n        if not isinstance(fields, dict) or set(fields) != expected:\n            observed = sorted(fields) if isinstance(fields, dict) else type(fields).__name__\n            raise RuntimeError(f"Potenza source-field drift: {observed!r}")\n        if any(not isinstance(fields[key], str) for key in expected):\n            raise RuntimeError("Potenza source-field scalar type drift")\n        source_id = fields["source_id"]\n        if not source_id.isdigit() or record.get("record_locator", "").rsplit(":id-", 1)[-1] != source_id:\n            raise RuntimeError("Potenza source-id/locator reconciliation drift")\n        record["source_fields"] = {\n            "physical_locator": f"source-id:{source_id}",\n            "application_date_raw": fields["data_istanza_raw"],\n            "listing_date_raw_variants": [fields["data_iscriz_raw"]] if fields["data_iscriz_raw"] else [],\n            "expiry_date_raw_variants": [fields["data_scad_iscriz_raw"]] if fields["data_scad_iscriz_raw"] else [],\n            "in_aggiornamento": fields["agg_incorso"],\n            "notes": [fields["note"]] if fields["note"] else [],\n        }\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n'''
    replace_exact(path, marker, adapter + marker)
    replace_exact(
        path,
        '        all_records.extend(public_record(record) for record in batch.records)\n',
        '        if cfg["parser"] in POTENZA_PARSERS:\n'
        '            batch = _adapt_potenza_public_fields(batch, cfg["parser"])\n'
        '        all_records.extend(public_record(record) for record in batch.records)\n',
    )


def main() -> None:
    update_source_registry()
    update_monitoring()
    update_publication_config()
    bind_parser_and_adapter()
    print("Potenza national candidate transaction applied to working tree")


if __name__ == "__main__":
    main()

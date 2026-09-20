from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/pordenone/white-list-elenco-ditte-iscritte"
LISTED_BUNDLE_SHA = "bundle:ce7759de3f7bc81c9f79298c8ad427a387446e8d61ff2d9f1c78cb8ad258e4a3"
APPLICANT_SHA = "b8875c9392f9c7273c3c773110d90141eada8aebaa538ae1e3115be27bfdaea1"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-xi-elenco-imprese-richiedenti_edit_0.pdf"
LISTED_RESOURCES = {
    "I": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-i-estrazione-fornitura-etc_0.pdf", "sha256": "f4e6374e5e03daa25daedd49ada730ae39c6b77437e763e3c0308aa0a0c627de"},
    "II": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-ii-confezionamento-fornitura-etc_0.pdf", "sha256": "62d63a080b3025e2ee2f37c3af1d486f12095be8f83e73cae611e2ca56bf84d5"},
    "III": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-iii-noli-a-freddo-di-macchinari.pdf", "sha256": "2204fe651b733e32fe13f001c97fd2c6a93ccd9a846cc9f4ddd40d4f471e6ce9"},
    "IV": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-iv-fornitura-di-ferro-lavorato_0.pdf", "sha256": "55a1edd7bcc52de101536c42091e14e040892cf1122462c36b37a861c48eeb62"},
    "V": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-v-noli-a-caldo_0.pdf", "sha256": "4fcd95954d20ba19ffcfb11e64a911a637056ba2fd794d47c5d3f19171f77803"},
    "VI": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-vi-autotrasporti-per-conto-terzi_1.pdf", "sha256": "62c39abfc260ecacf59b0201867263499643fe5dc36c95500e380fa53deb87aa"},
    "VII": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-vii-guardiania-dei-cantieri.pdf", "sha256": "35c5ef5ddb218e50d1f5a56007f2c1886ac73b6a91c5a13fb37e4b7f4952d2c8"},
    "VIII": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/74/2026-08/sez-viii-servizi-funerari-e-cimiteriali.pdf", "sha256": "cac3354a388d87b3f7ee1fef965f7b9968d2fea4dfcbafa776fc175bee5d96b3"},
    "IX": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-ix-ristorazione-mense-e-catering.pdf", "sha256": "a3b7c0b749be947692cb6ebb031e21e6c2e61913f34c1ad9f4741f3a7b9e96fa"},
    "X": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-x-servizi-ambientali-trasporto-rifiuti-etc_0.pdf", "sha256": "af639b5c55ff31893bfd3906876e0c60e1e6614065efae1e5c7871ac62290c0f"},
}


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one target, found {count}")
    return text.replace(old, new, 1)


def upsert_csv(path: Path, key: str, row: dict[str, str]) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if set(row) != set(fieldnames):
        raise RuntimeError(f"{path}: row/header mismatch")
    matches = [i for i, existing in enumerate(rows) if existing[fieldnames[0]] == key]
    if len(matches) > 1:
        raise RuntimeError(f"{path}: duplicate {key}")
    if matches:
        rows[matches[0]] = row
    else:
        rows.append(row)
    rows.sort(key=lambda value: value[fieldnames[0]])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def update_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data["sources"]
    additions = [
        {
            "authority_key": "pordenone",
            "authority_name": "Prefettura di Pordenone",
            "approval_mode": "raw_sha256",
            "reference_date": "2026-09-20",
            "last_source_update": "2026-09-01",
            "last_source_update_basis": "official publication-page metadata observed on 20 September 2026; reference_date is the independently verified capture boundary and not a company legal-effect date",
            "register_key": "pordenone-ordinary",
            "register_name": "White List ordinaria",
            "source_page_url": LANDING,
            "source_key": "pordenone-provincial-listed",
            "parser": "pordenone-provincial-listed",
            "population_scope": "listed",
            "resource_url": LANDING,
            "sha256": LISTED_BUNDLE_SHA,
            "resources": LISTED_RESOURCES,
            "expected_source_rows": 401,
            "expected_sector_rows": 595,
            "notes": "Ten current official listed-company sector PDFs I-X, each independently captured twice byte-identically on 20 September 2026 and verified by member SHA-256 before parsing. Conservative grouping of 595 physical sector observations yields 401 logical observations: 335 listed, 65 renewal/update in progress and 1 other/unknown. 234/401 logical observations have strict structured identifiers; malformed identifiers/dates and conflicting date/status states are retained without inferential repair.",
        },
        {
            "authority_key": "pordenone",
            "authority_name": "Prefettura di Pordenone",
            "approval_mode": "raw_sha256",
            "reference_date": "2026-09-20",
            "last_source_update": "2026-09-01",
            "last_source_update_basis": "official publication-page metadata observed on 20 September 2026; reference_date is the independently verified capture boundary and not a company legal-effect date",
            "register_key": "pordenone-ordinary",
            "register_name": "White List ordinaria",
            "source_page_url": LANDING,
            "source_key": "pordenone-provincial-applicants",
            "parser": "pordenone-provincial-applicants",
            "population_scope": "applicant",
            "resource_url": APPLICANT_URL,
            "sha256": APPLICANT_SHA,
            "expected_source_rows": 32,
            "notes": "Current official Section XI applicant PDF, independently captured twice byte-identically on 20 September 2026. It yields 32 source-backed observations: 31 pending/in istruttoria and one renewal/update in progress; all 32 have strict structured identifiers and valid application dates. Reviewed missing-name and table-overlap geometry cases remain source-faithful and fail closed on drift.",
        },
    ]
    by_key = {source["source_key"]: source for source in sources}
    for source in additions:
        existing = by_key.get(source["source_key"])
        if existing is not None:
            if existing != source:
                raise RuntimeError(f"publication config drift for {source['source_key']}")
        else:
            sources.append(source)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_inventory() -> None:
    upsert_csv(
        ROOT / "data/source_registry/verified_primary_pages.csv",
        "pordenone",
        {"authority_key": "pordenone", "landing_url": LANDING, "verification_date": "2026-09-20", "verification_status": "verified"},
    )
    common = {
        "authority_key": "pordenone",
        "regime_code": "WL-REGIME-L190-2012",
        "sector_scope": "all",
        "publication_model": "periodic_attachment",
        "series_url": LANDING,
        "resource_resolution_status": "landing_page_resolved",
        "verified_date": "2026-09-20",
    }
    inv = ROOT / "data/source_registry/source_series_inventory.csv"
    upsert_csv(
        inv,
        "pordenone-applicants",
        {
            "source_series_key": "pordenone-applicants",
            **common,
            "population_scope": "applicant",
            "notes": f"Current official Pordenone page positively exposes Section XI as elenco imprese richiedenti. Two independent cache-bypassed captures are byte-identical at SHA-256 {APPLICANT_SHA}; the fail-closed parser yields 32 observations (31 pending, one renewal/update), all with strict identifiers and valid application dates. Exact evidence is documented in docs/sources/pordenone-operational-check-2026-09-20.md.",
        },
    )
    upsert_csv(
        inv,
        "pordenone-listed",
        {
            "source_series_key": "pordenone-listed",
            **common,
            "population_scope": "listed",
            "notes": f"Current official Pordenone page positively exposes Sections I-X as listed-company sector PDFs. All ten resources were independently captured twice byte-identically; bundle identity is {LISTED_BUNDLE_SHA}. The fail-closed parser groups 595 physical sector observations into 401 logical observations (335 listed, 65 renewal/update in progress, one other/unknown). Exact evidence is documented in docs/sources/pordenone-operational-check-2026-09-20.md.",
        },
    )


def update_parser() -> None:
    path = ROOT / "src/white_list_archive/parsers/pordenone_tables.py"
    text = path.read_text(encoding="utf-8")
    if '"sector_rows": len(physical),' not in text:
        text = replace_once(
            text,
            '"physical_sector_observations": len(physical),\n            "public_records": len(records),',
            '"physical_sector_observations": len(physical),\n            "sector_rows": len(physical),\n            "public_records": len(records),',
            "sector diagnostic",
        )
    path.write_text(text, encoding="utf-8")


def update_builder() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    import_marker = """from white_list_archive.parsers.ferrara_tables import (
    PARSERS as FERRARA_PARSERS,
    parse_ferrara_reconstruction_bundle,
)
"""
    pordenone_import = """from white_list_archive.parsers.pordenone_tables import (
    PARSERS as PORDENONE_PARSERS,
    parse_pordenone_listed_bundle,
)
"""
    if pordenone_import not in text:
        text = replace_once(text, import_marker, import_marker + pordenone_import, "parser import")
    if 'PORDENONE_LISTED_PARSER = "pordenone-provincial-listed"' not in text:
        text = replace_once(
            text,
            'FERRARA_RECONSTRUCTION_PARSER = "ferrara-reconstruction-listed"\n',
            'FERRARA_RECONSTRUCTION_PARSER = "ferrara-reconstruction-listed"\nPORDENONE_LISTED_PARSER = "pordenone-provincial-listed"\n',
            "parser constant",
        )
    adapter = """
def _adapt_pordenone_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Pordenone source_fields must be a mapping")
        if parser_name == PORDENONE_LISTED_PARSER:
            expected = {
                "sections", "physical_locators", "physical_sector_observations",
                "name_variants", "office_variants", "secondary_office_variants",
                "listing_date_raw", "expiry_date_raw", "notes",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Pordenone listed source-field drift: {sorted(fields)!r}")
            for key in ("sections", "physical_locators", "name_variants", "office_variants", "secondary_office_variants", "notes"):
                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):
                    raise RuntimeError(f"Pordenone listed source-list type drift: {key}")
            if not fields["sections"] or not fields["physical_locators"]:
                raise RuntimeError("Pordenone listed empty section/provenance evidence")
            if type(fields["physical_sector_observations"]) is not int or fields["physical_sector_observations"] != len(fields["physical_locators"]):
                raise RuntimeError("Pordenone listed physical-sector denominator drift")
            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw")):
                raise RuntimeError("Pordenone listed raw-date type drift")
            record["source_fields"] = {
                "sections": [f"Sezione {value}" for value in fields["sections"]],
                "physical_locators": list(fields["physical_locators"]),
                "notes": list(fields["notes"]),
                "registered_office_variants": list(fields["office_variants"]),
                "secondary_office_variants": list(fields["secondary_office_variants"]),
                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],
                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],
            }
        elif parser_name == "pordenone-provincial-applicants":
            expected = {
                "application_date_raw", "requested_activities_source", "physical_locators",
                "source_row_raw", "source_name_missing",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Pordenone applicant source-field drift: {sorted(fields)!r}")
            if not isinstance(fields["physical_locators"], list) or len(fields["physical_locators"]) != 1 or any(not isinstance(value, str) for value in fields["physical_locators"]):
                raise RuntimeError("Pordenone applicant physical-locator type/cardinality drift")
            if not isinstance(fields["source_row_raw"], list) or any(not isinstance(value, str) for value in fields["source_row_raw"]):
                raise RuntimeError("Pordenone applicant raw-row evidence drift")
            if type(fields["source_name_missing"]) is not bool:
                raise RuntimeError("Pordenone applicant missing-name flag drift")
            if any(not isinstance(fields[key], str) for key in ("application_date_raw", "requested_activities_source")):
                raise RuntimeError("Pordenone applicant source-field scalar drift")
            record["source_fields"] = {
                "physical_locators": list(fields["physical_locators"]),
                "requested_activities_source": fields["requested_activities_source"],
                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],
            }
        else:
            raise RuntimeError(f"Unexpected Pordenone parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)

"""
    marker = "def _parse_source(path: Path | dict[str, Path], cfg: dict[str, Any]) -> ParsedBatch:\n"
    if "def _adapt_pordenone_public_fields" not in text:
        text = replace_once(text, marker, adapter + marker, "public adapter")
    if 'if cfg["parser"] == PORDENONE_LISTED_PARSER:' not in text:
        special = """def _parse_source(path: Path | dict[str, Path], cfg: dict[str, Any]) -> ParsedBatch:
    if cfg["parser"] == PORDENONE_LISTED_PARSER:
        if not isinstance(path, dict):
            raise RuntimeError("Pordenone listed population requires an explicitly acquired source bundle")
        batch = _adapt_pordenone_public_fields(parse_pordenone_listed_bundle(path, cfg), cfg["parser"])
        for record in batch.records:
            record["parser_name"] = cfg["parser"]
            record["parser_version"] = "1"
        return batch
"""
        text = replace_once(text, marker, special, "bundle dispatch")
    if 'or PORDENONE_PARSERS.get(cfg["parser"])' not in text:
        text = replace_once(
            text,
            '        or FERRARA_PARSERS.get(cfg["parser"])\n',
            '        or FERRARA_PARSERS.get(cfg["parser"])\n        or PORDENONE_PARSERS.get(cfg["parser"])\n',
            "scalar dispatch",
        )
    if 'if cfg["parser"] in PORDENONE_PARSERS:' not in text:
        text = replace_once(
            text,
            '    if cfg["parser"] in FERRARA_PARSERS:\n        batch = _adapt_ferrara_public_fields(batch, cfg["parser"])\n',
            '    if cfg["parser"] in FERRARA_PARSERS:\n        batch = _adapt_ferrara_public_fields(batch, cfg["parser"])\n    if cfg["parser"] in PORDENONE_PARSERS:\n        batch = _adapt_pordenone_public_fields(batch, cfg["parser"])\n',
            "scalar adapter",
        )
    path.write_text(text, encoding="utf-8")


def update_monitoring() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [row for row in data["prefectures"] if row.get("authority_key") == "pordenone"]
    if len(matches) != 1:
        raise RuntimeError(f"monitoring Pordenone cardinality drift: {len(matches)}")
    row = matches[0]
    row.update({
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
        "population_scopes_complete": True,
        "latest_source_reference_date": "2026-09-20",
        "last_successful_investigation_on": "2026-09-20",
        "coverage_status": "VALIDATED",
        "terminal_reason": None,
        "actionable_issue": False,
        "completion_evidence": [
            "docs/sources/pordenone-operational-check-2026-09-20.md",
            "src/white_list_archive/parsers/pordenone_tables.py",
            "tests/test_pordenone_public_integration.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        "known_content_sha256": [LISTED_BUNDLE_SHA, *[LISTED_RESOURCES[key]["sha256"] for key in sorted(LISTED_RESOURCES)], APPLICANT_SHA],
        "evidence": [
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/pordenone-operational-check-2026-09-20.md",
        ],
        "last_completed_coverage_stage": "VALIDATED",
        "unresolved_issue": [
            "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
        ],
    })
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_workflow() -> None:
    path = ROOT / ".github/workflows/public-pages.yml"
    text = path.read_text(encoding="utf-8")
    if "'src/white_list_archive/parsers/pordenone_tables.py'" not in text:
        text = replace_once(
            text,
            "      - 'src/white_list_archive/parsers/ferrara_tables.py'\n",
            "      - 'src/white_list_archive/parsers/ferrara_tables.py'\n      - 'src/white_list_archive/parsers/pordenone_tables.py'\n",
            "workflow parser path",
        )
    replacements = [
        ("assert reg['meta']['record_count'] == 71057", "assert reg['meta']['record_count'] == 71490", "record count"),
        ("'siracusa','ferrara'}", "'siracusa','ferrara','pordenone'}", "authority set"),
        ("'ferrara-ordinary','ferrara-reconstruction'\n          }", "'ferrara-ordinary','ferrara-reconstruction','pordenone-ordinary'\n          }", "register set"),
        ("assert reg['meta']['authority_count'] == 67", "assert reg['meta']['authority_count'] == 68", "authority count"),
        ("assert reg['meta']['register_count'] == 70", "assert reg['meta']['register_count'] == 71", "register count"),
        ("assert pref['meta']['published_count'] == 67", "assert pref['meta']['published_count'] == 68", "published count"),
        ("assert pref['meta']['mapped_count'] == 67", "assert pref['meta']['mapped_count'] == 68", "mapped count"),
    ]
    for old, new, label in replacements:
        if new not in text:
            text = replace_once(text, old, new, f"public-pages {label}")
    checks = """          pordenone = [x for x in pref['prefectures'] if x['authority_key'] == 'pordenone']
          assert len(pordenone) == 1 and pordenone[0]['mapped'] and pordenone[0]['published'] and pordenone[0]['series_count'] == 2
          pordenone_records = [r for r in reg['records'] if r['authority_key'] == 'pordenone']
          assert len(pordenone_records) == 433
          assert sum(r['source_key'] == 'pordenone-provincial-listed' for r in pordenone_records) == 401
          assert sum(r['source_key'] == 'pordenone-provincial-applicants' for r in pordenone_records) == 32
          assert sum(r['source_status'] == 'listed' for r in pordenone_records) == 335
          assert sum(r['source_status'] == 'pending' for r in pordenone_records) == 31
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in pordenone_records) == 66
          assert sum(r['source_status'] == 'other_or_unknown' for r in pordenone_records) == 1
          assert sum(bool(r['identifiers']) for r in pordenone_records) == 266
          assert len({r['record_locator'] for r in pordenone_records}) == 433
"""
    if "pordenone_records = [r for r in reg['records']" not in text:
        start = text.find("assert pref['meta']['mapped_count'] == 68")
        end = text.find("\n          PY\n", start)
        if start < 0 or end < 0:
            raise RuntimeError("public workflow Python validation terminator not found")
        text = text[:end] + "\n" + checks + text[end:]
    path.write_text(text, encoding="utf-8")


def write_test() -> None:
    path = ROOT / "tests/test_pordenone_public_integration.py"
    content = """from __future__ import annotations

import json
from pathlib import Path

import pytest

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch
from white_list_archive.publishing.public_national_registry import (
    PORDENONE_LISTED_PARSER,
    _adapt_pordenone_public_fields,
    _bundle_digest,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BUNDLE = "bundle:ce7759de3f7bc81c9f79298c8ad427a387446e8d61ff2d9f1c78cb8ad258e4a3"


def _record(source_fields: dict) -> dict:
    return {"record_locator": "pordenone:test:1", "source_fields": source_fields}


def test_pordenone_publication_config_is_complete_and_single_register() -> None:
    config = json.loads((ROOT / "data/publication/multi_prefecture_pilot.json").read_text(encoding="utf-8"))
    sources = [source for source in config["sources"] if source["authority_key"] == "pordenone"]
    assert [source["source_key"] for source in sources] == ["pordenone-provincial-listed", "pordenone-provincial-applicants"]
    listed, applicants = sources
    assert listed["parser"] == PORDENONE_LISTED_PARSER
    assert listed["expected_source_rows"] == 401
    assert listed["expected_sector_rows"] == 595
    assert set(listed["resources"]) == {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
    assert _bundle_digest({key: member["sha256"] for key, member in listed["resources"].items()}) == EXPECTED_BUNDLE
    assert listed["sha256"] == EXPECTED_BUNDLE
    assert applicants["expected_source_rows"] == 32
    assert applicants["sha256"] == "b8875c9392f9c7273c3c773110d90141eada8aebaa538ae1e3115be27bfdaea1"
    assert {source["register_key"] for source in sources} == {"pordenone-ordinary"}


def test_pordenone_listed_public_adapter_is_closed() -> None:
    fields = {
        "sections": ["I", "III"],
        "physical_locators": ["I:p1:r2", "III:p2:r3"],
        "physical_sector_observations": 2,
        "name_variants": ["EXAMPLE SRL"],
        "office_variants": ["PORDENONE"],
        "secondary_office_variants": [],
        "listing_date_raw": "01/01/2026",
        "expiry_date_raw": "01/01/2027",
        "notes": [],
    }
    batch = ParsedBatch(records=[_record(fields)], diagnostics={"public_records": 1})
    adapted = _adapt_pordenone_public_fields(batch, PORDENONE_LISTED_PARSER)
    assert adapted.records[0]["source_fields"] == {
        "sections": ["Sezione I", "Sezione III"],
        "physical_locators": ["I:p1:r2", "III:p2:r3"],
        "notes": [],
        "registered_office_variants": ["PORDENONE"],
        "secondary_office_variants": [],
        "listing_date_raw_variants": ["01/01/2026"],
        "expiry_date_raw_variants": ["01/01/2027"],
    }


def test_pordenone_applicant_public_adapter_drops_only_diagnostic_row_geometry() -> None:
    fields = {
        "application_date_raw": "29/09/2025",
        "requested_activities_source": "",
        "physical_locators": ["XI:p3:r9"],
        "source_row_raw": ["SEQUALS - VIA CECILIA DANIELI, 7", "", "", "01456650934", "", "29/09/2025", "IN AGGIORNAMENTO"],
        "source_name_missing": True,
    }
    batch = ParsedBatch(records=[_record(fields)], diagnostics={"public_records": 1})
    adapted = _adapt_pordenone_public_fields(batch, "pordenone-provincial-applicants")
    assert adapted.records[0]["source_fields"] == {
        "physical_locators": ["XI:p3:r9"],
        "requested_activities_source": "",
        "application_date_raw_variants": ["29/09/2025"],
    }


def test_pordenone_adapter_fails_closed_on_unreviewed_field() -> None:
    fields = {
        "application_date_raw": "29/09/2025",
        "requested_activities_source": "",
        "physical_locators": ["XI:p3:r9"],
        "source_row_raw": [],
        "source_name_missing": True,
        "invented": "no",
    }
    with pytest.raises(RuntimeError, match="source-field drift"):
        _adapt_pordenone_public_fields(ParsedBatch(records=[_record(fields)], diagnostics={"public_records": 1}), "pordenone-provincial-applicants")
"""
    path.write_text(content, encoding="utf-8")


def main() -> None:
    update_config()
    update_inventory()
    update_parser()
    update_builder()
    update_monitoring()
    update_workflow()
    write_test()


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str, *, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    observed = text.count(old)
    if observed != count:
        raise RuntimeError(f"{path}: expected anchor {count} time(s), found {observed}: {old[:120]!r}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def prepare() -> None:
    parser = ROOT / "src/white_list_archive/parsers/napoli_tables.py"
    replace_exact(
        parser,
        '_validate_cfg(cfg, source_key="napoli-applicants", population_scope="applicants", sha256=_APPLICANT_SHA256)',
        '_validate_cfg(cfg, source_key="napoli-applicants", population_scope="applicant", sha256=_APPLICANT_SHA256)',
    )

    registry = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    replace_exact(
        registry,
        "from white_list_archive.parsers.gorizia_tables import parse_gorizia_applicants, parse_gorizia_listed\nfrom white_list_archive.publishing.public_contract import public_record, validate_registry\n",
        "from white_list_archive.parsers.gorizia_tables import parse_gorizia_applicants, parse_gorizia_listed\nfrom white_list_archive.parsers.napoli_tables import PARSERS as NAPOLI_PARSERS\nfrom white_list_archive.publishing.public_contract import public_record, validate_registry\n",
    )

    adapter = '''\n\ndef _adapt_napoli_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    \"\"\"Project audited Napoli evidence onto the recursively closed public contract.\"\"\"\n    adapted: list[dict[str, Any]] = []\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get(\"source_fields\")\n        if not isinstance(fields, dict):\n            raise RuntimeError(\"Napoli source_fields must be a mapping\")\n        if parser_name == \"napoli_listed\":\n            expected = {\n                \"sections\", \"sections_source_raw\", \"listing_date_raw_variants\",\n                \"expiry_date_raw_variants\", \"in_aggiornamento\", \"source_page\",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f\"Napoli listed source-field drift: {sorted(fields)!r}\")\n            for key in (\"sections\", \"listing_date_raw_variants\", \"expiry_date_raw_variants\"):\n                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):\n                    raise RuntimeError(f\"Napoli listed source-field type drift: {key}\")\n            if not isinstance(fields[\"sections_source_raw\"], str) or not isinstance(fields[\"in_aggiornamento\"], str):\n                raise RuntimeError(\"Napoli listed source-field scalar drift\")\n            if type(fields[\"source_page\"]) is not int:\n                raise RuntimeError(\"Napoli listed source-page type drift\")\n            record[\"source_fields\"] = {\n                \"sections\": list(fields[\"sections\"]),\n                \"listing_date_raw_variants\": list(fields[\"listing_date_raw_variants\"]),\n                \"expiry_date_raw_variants\": list(fields[\"expiry_date_raw_variants\"]),\n                \"in_aggiornamento\": fields[\"in_aggiornamento\"],\n            }\n        elif parser_name == \"napoli_applicants\":\n            expected = {\"requested_activities_source\", \"application_date_raw_variants\", \"source_page\"}\n            if set(fields) != expected:\n                raise RuntimeError(f\"Napoli applicant source-field drift: {sorted(fields)!r}\")\n            if not isinstance(fields[\"requested_activities_source\"], str):\n                raise RuntimeError(\"Napoli applicant requested-activity source drift\")\n            raw_dates = fields[\"application_date_raw_variants\"]\n            if not isinstance(raw_dates, list) or any(not isinstance(value, str) for value in raw_dates):\n                raise RuntimeError(\"Napoli applicant raw-date type drift\")\n            if type(fields[\"source_page\"]) is not int:\n                raise RuntimeError(\"Napoli applicant source-page type drift\")\n            record[\"source_fields\"] = {\n                \"requested_activities_source\": fields[\"requested_activities_source\"],\n                \"application_date_raw_variants\": list(raw_dates),\n            }\n        else:\n            raise RuntimeError(f\"Unexpected Napoli parser: {parser_name!r}\")\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n'''
    replace_exact(
        registry,
        "    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n",
        "    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n" + adapter + "\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n",
    )
    replace_exact(
        registry,
        '        or GORIZIA_PARSERS.get(cfg["parser"])\n    )',
        '        or GORIZIA_PARSERS.get(cfg["parser"])\n        or NAPOLI_PARSERS.get(cfg["parser"])\n    )',
    )
    replace_exact(
        registry,
        '    if cfg["parser"] in GORIZIA_PARSERS:\n        batch = _adapt_gorizia_public_fields(batch, cfg["parser"])\n    for record in batch.records:\n',
        '    if cfg["parser"] in GORIZIA_PARSERS:\n        batch = _adapt_gorizia_public_fields(batch, cfg["parser"])\n    if cfg["parser"] in NAPOLI_PARSERS:\n        batch = _adapt_napoli_public_fields(batch, cfg["parser"])\n    for record in batch.records:\n',
    )
    replace_exact(
        registry,
        '        record["parser_name"] = cfg["parser"]\n        record["parser_version"] = "1"\n',
        '        record["parser_name"] = cfg["parser"]\n        record["parser_version"] = "2" if cfg["parser"] in NAPOLI_PARSERS else "1"\n',
    )

    inventory = ROOT / "data/source_registry/source_series_inventory.csv"
    replace_exact(
        inventory,
        "napoli-applicants,napoli,WL-REGIME-L190-2012,applicant,all,periodic_attachment,https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-richiedenti,direct_series_page_resolved,2026-09-07,Dedicated applicant page exposes the current 1 September 2026 list and defines the applicant population.\n",
        "napoli-applicants,napoli,WL-REGIME-L190-2012,applicant,all,periodic_attachment,https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-richiedenti,direct_series_page_resolved,2026-09-14,Dedicated official applicant page positively defines the applicant population; the current byte-pinned 11 September 2026 PDF yields exactly 2571 source observations under the fail-closed parser. Exact identity and reviewed exceptions are documented in docs/sources/napoli-operational-check-2026-09-13.md.\n",
    )
    replace_exact(
        inventory,
        "napoli-listed,napoli,WL-REGIME-L190-2012,listed,all,periodic_attachment,https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-iscritte,direct_series_page_resolved,2026-09-07,Dedicated registered-company page exposes the current 31 August 2026 list.\n",
        "napoli-listed,napoli,WL-REGIME-L190-2012,listed,all,periodic_attachment,https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-iscritte,direct_series_page_resolved,2026-09-14,Dedicated official registered-company page exposes the current 11 September 2026 PDF; the byte-pinned edition yields exactly 2259 source observations under the fail-closed parser. Exact identity and reviewed exceptions are documented in docs/sources/napoli-operational-check-2026-09-13.md.\n",
    )

    config_path = ROOT / "data/publication/multi_prefecture_pilot.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if any(source.get("authority_key") == "napoli" for source in config["sources"]):
        raise RuntimeError("Napoli is already present in publication configuration")
    config["sources"].extend(
        [
            {
                "authority_key": "napoli",
                "authority_name": "Prefettura di Napoli",
                "register_key": "napoli-ordinary",
                "register_name": "White List ordinaria",
                "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-iscritte",
                "source_key": "napoli-listed",
                "parser": "napoli_listed",
                "population_scope": "listed",
                "reference_date": "2026-09-13",
                "resource_url": "https://prefettura.interno.gov.it/sites/default/files/79/2026-09/whitelistprefnapoli_11_settembre_26.pdf",
                "sha256": "93a8635c0bd9b00587f9cc60c52752061bd239a7c16cb34b64a11e495a0ab4be",
                "expected_source_rows": 2259,
                "last_source_update": "2026-09-11",
                "last_source_update_basis": "dated official resource repeat-fetched and byte-pinned during parser validation on 14 September 2026",
                "notes": "Byte-pinned 60-page listed-company PDF. The fail-closed parser yields 2259 observations and preserves reviewed source anomalies without inferential repair; exact row ownership, status semantics and exception populations are documented in docs/sources/napoli-operational-check-2026-09-13.md.",
            },
            {
                "authority_key": "napoli",
                "authority_name": "Prefettura di Napoli",
                "register_key": "napoli-ordinary",
                "register_name": "White List ordinaria",
                "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-richiedenti",
                "source_key": "napoli-applicants",
                "parser": "napoli_applicants",
                "population_scope": "applicant",
                "reference_date": "2026-09-13",
                "resource_url": "https://prefettura.interno.gov.it/sites/default/files/79/2026-09/ditterichiedenti_wl_11_settembre_26.pdf",
                "sha256": "053be2500b07a7da536c344aede12084dde9b7cf28b4717af99764cbd05e7e6b",
                "expected_source_rows": 2571,
                "last_source_update": "2026-09-11",
                "last_source_update_basis": "dated official resource repeat-fetched and byte-pinned during parser validation on 14 September 2026",
                "notes": "Byte-pinned 215-page applicant PDF. The dedicated official publication positively identifies the applicant population; the fail-closed parser yields 2571 observations and resolves only exact reviewed continuation/name-boundary evidence.",
            },
        ]
    )
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def finalize(registry_path: Path, prefectures_path: Path) -> None:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    prefectures = json.loads(prefectures_path.read_text(encoding="utf-8"))
    napoli = [record for record in registry["records"] if record["authority_key"] == "napoli"]
    listed = [record for record in napoli if record["source_key"] == "napoli-listed"]
    applicants = [record for record in napoli if record["source_key"] == "napoli-applicants"]
    if len(napoli) != 4830 or len(listed) != 2259 or len(applicants) != 2571:
        raise RuntimeError(f"Napoli national denominator drift: total={len(napoli)} listed={len(listed)} applicants={len(applicants)}")
    expected_status = {
        "cancellation_related": 3,
        "listed": 792,
        "other_or_unknown": 30,
        "pending": 2530,
        "rejected_or_denied": 52,
        "renewal_update_in_progress": 1423,
    }
    if dict(sorted(Counter(record["source_status"] for record in napoli).items())) != expected_status:
        raise RuntimeError("Napoli national status distribution drift")
    meta = registry["meta"]
    pmeta = prefectures["meta"]
    if meta["record_count"] != 32670 + len(napoli):
        raise RuntimeError(f"Unexpected generated national record count: {meta['record_count']}")
    if meta["authority_count"] != 35 or meta["register_count"] != 36:
        raise RuntimeError(f"Unexpected generated authority/register counts: {meta['authority_count']}/{meta['register_count']}")
    if pmeta["mapped_count"] != 43 or pmeta["published_count"] != 35:
        raise RuntimeError(f"Unexpected generated mapped/published counts: {pmeta['mapped_count']}/{pmeta['published_count']}")
    napoli_pref = [row for row in prefectures["prefectures"] if row["authority_key"] == "napoli"]
    if len(napoli_pref) != 1 or not napoli_pref[0]["mapped"] or not napoli_pref[0]["published"] or napoli_pref[0]["series_count"] != 2:
        raise RuntimeError(f"Napoli Prefecture directory drift: {napoli_pref!r}")

    browser = ROOT / "tests/public_portal_browser.cjs"
    replace_exact(
        browser,
        "      assert.ok(labels.includes('White List ordinaria · Prefettura di Gorizia'));\n",
        "      assert.ok(labels.includes('White List ordinaria · Prefettura di Gorizia'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Napoli'));\n",
    )
    replace_exact(browser, "      assert.equal(stats.total,32670);\n", f"      assert.equal(stats.total,{meta['record_count']});\n")
    replace_exact(browser, ",'gorizia'].includes(r.authority_key));", ",'gorizia','napoli'].includes(r.authority_key));")
    gorizia_block = """      const gorizia=registry.records.filter(r=>r.authority_key==='gorizia');\n      assert.equal(gorizia.length,127);\n      assert.equal(gorizia.filter(r=>r.source_key==='gorizia-listed').length,117);\n      assert.equal(gorizia.filter(r=>r.source_key==='gorizia-applicants').length,10);\n      assert.deepEqual(statusCounts(gorizia),{listed:86,pending:10,renewal_update_in_progress:31});\n"""
    napoli_block = """      const napoli=registry.records.filter(r=>r.authority_key==='napoli');\n      assert.equal(napoli.length,4830);\n      assert.equal(napoli.filter(r=>r.source_key==='napoli-listed').length,2259);\n      assert.equal(napoli.filter(r=>r.source_key==='napoli-applicants').length,2571);\n      assert.deepEqual(statusCounts(napoli),{cancellation_related:3,listed:792,other_or_unknown:30,pending:2530,rejected_or_denied:52,renewal_update_in_progress:1423});\n      assert.equal(napoli.filter(r=>r.source_fields&&Array.isArray(r.source_fields.listing_date_raw_variants)&&r.source_fields.listing_date_raw_variants.includes('14/0319')&&r.observed_listing_date==='').length,1);\n      assert.equal(napoli.filter(r=>r.source_fields&&Array.isArray(r.source_fields.expiry_date_raw_variants)&&r.source_fields.expiry_date_raw_variants.some(v=>v.startsWith(\"Iscrizione valida per la durata dell'amministrazi\"))&&r.observed_expiry_date==='').length,7);\n"""
    replace_exact(browser, gorizia_block, gorizia_block + napoli_block)

    print(json.dumps({
        "registry_records": meta["record_count"],
        "authorities_published": meta["authority_count"],
        "registers_published": meta["register_count"],
        "mapped_prefectures": pmeta["mapped_count"],
        "published_prefectures": pmeta["published_count"],
        "napoli_records": len(napoli),
        "napoli_status_counts": expected_status,
    }, ensure_ascii=False))


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: napoli_national_candidate.py prepare|finalize [registry prefectures]")
    if sys.argv[1] == "prepare":
        prepare()
    elif sys.argv[1] == "finalize" and len(sys.argv) == 4:
        finalize(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        raise SystemExit("invalid arguments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

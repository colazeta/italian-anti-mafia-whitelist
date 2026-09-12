from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "tmp/bolzano_integration.py"


def run_v1() -> None:
    spec = importlib.util.spec_from_file_location("bolzano_integration_v1", V1)
    if spec is None or spec.loader is None:
        raise SystemExit("Cannot load Bolzano integration v1 helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def adapt_public_contract() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")

    parser_map = (
        "BOLZANO_PARSERS = {\n"
        '    "bolzano_listed": parse_bolzano_listed,\n'
        '    "bolzano_applicants": parse_bolzano_applicants,\n'
        "}\n"
    )
    adapter = '''\n\ndef _adapt_bolzano_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    \"\"\"Map audited parser evidence onto the already-approved public source-field contract.\n\n    The Bolzano parser keeps source-row diagnostics that are useful for review but are\n    deliberately not part of the public contract. This adapter is explicit and fail-closed:\n    an unexpected parser field, type, or row/section cardinality stops publication.\n    \"\"\"\n    adapted: list[dict[str, Any]] = []\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get(\"source_fields\")\n        if not isinstance(fields, dict):\n            raise RuntimeError(\"Bolzano source_fields must be a mapping\")\n        if parser_name == \"bolzano_listed\":\n            expected = {\n                \"listed_sections\",\n                \"listed_source_rows\",\n                \"listing_date_raw\",\n                \"expiry_date_raw\",\n                \"update_raw_values\",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f\"Bolzano listed source-field drift: {sorted(fields)!r}\")\n            sections = fields[\"listed_sections\"]\n            source_rows = fields[\"listed_source_rows\"]\n            updates = fields[\"update_raw_values\"]\n            if (\n                not isinstance(sections, list)\n                or any(type(value) is not int for value in sections)\n                or not isinstance(source_rows, list)\n                or any(type(value) is not int for value in source_rows)\n                or len(sections) != len(source_rows)\n                or not isinstance(updates, list)\n                or any(not isinstance(value, str) for value in updates)\n            ):\n                raise RuntimeError(\"Bolzano listed source-field type/cardinality drift\")\n            listing_raw = fields[\"listing_date_raw\"]\n            expiry_raw = fields[\"expiry_date_raw\"]\n            if not isinstance(listing_raw, str) or not isinstance(expiry_raw, str):\n                raise RuntimeError(\"Bolzano listed raw-date field type drift\")\n            record[\"source_fields\"] = {\n                \"sections\": [f\"Sezione {section}\" for section in sections],\n                \"listing_date_raw_variants\": [listing_raw] if listing_raw else [],\n                \"expiry_date_raw_variants\": [expiry_raw] if expiry_raw else [],\n                \"in_aggiornamento\": \" · \".join(updates),\n            }\n        elif parser_name == \"bolzano_applicants\":\n            expected = {\"source_row\", \"activities_raw\", \"application_date_raw\", \"outcome_raw\"}\n            if set(fields) != expected:\n                raise RuntimeError(f\"Bolzano applicant source-field drift: {sorted(fields)!r}\")\n            if type(fields[\"source_row\"]) is not int:\n                raise RuntimeError(\"Bolzano applicant source-row type drift\")\n            if any(not isinstance(fields[key], str) for key in (\"activities_raw\", \"application_date_raw\", \"outcome_raw\")):\n                raise RuntimeError(\"Bolzano applicant source-field type drift\")\n            if fields[\"outcome_raw\"]:\n                raise RuntimeError(\"Bolzano applicant outcome became nonblank during publication adaptation\")\n            application_raw = fields[\"application_date_raw\"]\n            record[\"source_fields\"] = {\n                \"requested_activities_source\": fields[\"activities_raw\"],\n                \"application_date_raw_variants\": [application_raw] if application_raw else [],\n            }\n        else:\n            raise RuntimeError(f\"Unexpected Bolzano parser: {parser_name!r}\")\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n'''
    if text.count(parser_map) != 1:
        raise SystemExit("Bolzano parser map missing or duplicated after v1 materialisation")
    if "def _adapt_bolzano_public_fields" in text:
        raise SystemExit("Bolzano public adapter already present; refusing duplicate patch")
    text = text.replace(parser_map, parser_map + adapter, 1)

    parse_anchor = "    batch = parser(path, cfg)\n    for record in batch.records:\n"
    parse_replacement = (
        "    batch = parser(path, cfg)\n"
        "    if cfg[\"parser\"] in BOLZANO_PARSERS:\n"
        "        batch = _adapt_bolzano_public_fields(batch, cfg[\"parser\"])\n"
        "    for record in batch.records:\n"
    )
    if text.count(parse_anchor) != 1:
        raise SystemExit("National parser post-parse anchor drift")
    text = text.replace(parse_anchor, parse_replacement, 1)
    path.write_text(text, encoding="utf-8")


def adapt_browser_assertion() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    old = "r.source_fields&&r.source_fields.expiry_date_raw==='16/19/2026'&&r.observed_expiry_date===''"
    new = "r.source_fields&&Array.isArray(r.source_fields.expiry_date_raw_variants)&&r.source_fields.expiry_date_raw_variants.includes('16/19/2026')&&r.observed_expiry_date===''"
    if text.count(old) != 1:
        raise SystemExit("Bolzano browser raw-expiry assertion anchor drift")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    run_v1()
    adapt_public_contract()
    adapt_browser_assertion()


if __name__ == "__main__":
    main()

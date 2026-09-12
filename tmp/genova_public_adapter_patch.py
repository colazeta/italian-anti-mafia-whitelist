from pathlib import Path

path = Path("src/white_list_archive/publishing/public_national_registry.py")
text = path.read_text(encoding="utf-8")

old_call = '''    if cfg["parser"] in BOLZANO_PARSERS:\n        batch = _adapt_bolzano_public_fields(batch, cfg["parser"])\n'''
new_call = old_call + '''    if cfg["parser"] in GENOVA_PARSERS:\n        batch = _adapt_genova_public_fields(batch, cfg["parser"])\n'''
if text.count(old_call) != 1:
    raise SystemExit(f"expected one Genova adapter insertion point, got {text.count(old_call)}")
text = text.replace(old_call, new_call, 1)

marker = "\n\ndef _validate_batch(cfg: dict[str, Any], batch: ParsedBatch) -> None:\n"
if text.count(marker) != 1:
    raise SystemExit(f"expected one validation marker, got {text.count(marker)}")

adapter = '''

def _adapt_genova_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Project audited Genova parser evidence onto the closed public contract.

    The parser deliberately retains source-layout diagnostics that are useful for
    validation but are not public-contract fields. This adapter is exact and
    fail-closed: any new key or type drift stops publication rather than widening
    the public contract.
    """
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Genova source_fields must be a mapping")

        if parser_name == "genova_listed":
            expected = {
                "sections",
                "secondary_office_raw",
                "listing_date_raw",
                "expiry_date_raw",
                "in_aggiornamento",
                "source_locator",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Genova listed source-field drift: {sorted(fields)!r}")
            sections = fields["sections"]
            if not isinstance(sections, list) or any(not isinstance(value, str) for value in sections):
                raise RuntimeError("Genova listed section type drift")
            for key in ("secondary_office_raw", "listing_date_raw", "expiry_date_raw", "in_aggiornamento", "source_locator"):
                if not isinstance(fields[key], str):
                    raise RuntimeError(f"Genova listed source-field type drift: {key}")
            record["source_fields"] = {
                "sections": list(sections),
                "secondary_office_variants": [fields["secondary_office_raw"]] if fields["secondary_office_raw"] else [],
                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],
                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],
                "in_aggiornamento": fields["in_aggiornamento"],
            }
        elif parser_name == "genova_applicants":
            expected = {
                "sections",
                "secondary_office_raw",
                "application_date_raw",
                "source_locator",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Genova applicant source-field drift: {sorted(fields)!r}")
            sections = fields["sections"]
            if not isinstance(sections, list) or any(not isinstance(value, str) for value in sections):
                raise RuntimeError("Genova applicant section type drift")
            for key in ("secondary_office_raw", "application_date_raw", "source_locator"):
                if not isinstance(fields[key], str):
                    raise RuntimeError(f"Genova applicant source-field type drift: {key}")
            record["source_fields"] = {
                "sections": list(sections),
                "secondary_office_variants": [fields["secondary_office_raw"]] if fields["secondary_office_raw"] else [],
                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],
            }
        else:
            raise RuntimeError(f"Unexpected Genova parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)
'''

text = text.replace(marker, adapter + marker, 1)
path.write_text(text, encoding="utf-8")

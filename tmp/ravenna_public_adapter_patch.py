from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one replacement anchor, found {count}")
    return text.replace(old, new, 1)


registry_path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
text = registry_path.read_text(encoding="utf-8")

adapter = r'''
def _adapt_ravenna_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Project audited Ravenna evidence onto the recursively closed public contract.

    The parser intentionally retains review-only extraction evidence. Publication
    exposes only source facts already admitted by the public contract and fails
    closed on any source-field or reviewed-repair drift.
    """
    if parser_name != "ravenna_combined":
        raise RuntimeError(f"Unexpected Ravenna parser: {parser_name!r}")
    base = {
        "source_progressive",
        "company_identity_raw",
        "registered_office_variants",
        "application_date_raw_variants",
        "listing_date_raw_variants",
        "normalised_application_date_variants",
        "normalised_listing_date_variants",
        "note_raw",
        "sections",
        "section_markers",
        "malformed_date_pairs",
    }
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Ravenna source_fields must be a mapping")
        keys = set(fields)
        if keys not in (base, base | {"reviewed_extraction_repair"}):
            raise RuntimeError(f"Ravenna source-field drift: {sorted(keys)!r}")
        for key in (
            "registered_office_variants",
            "application_date_raw_variants",
            "listing_date_raw_variants",
            "normalised_application_date_variants",
            "normalised_listing_date_variants",
            "sections",
            "section_markers",
            "malformed_date_pairs",
        ):
            value = fields[key]
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise RuntimeError(f"Ravenna source-list type drift: {key}")
        for key in ("source_progressive", "company_identity_raw", "note_raw"):
            if not isinstance(fields[key], str):
                raise RuntimeError(f"Ravenna source-scalar type drift: {key}")
        repair = fields.get("reviewed_extraction_repair")
        if repair is not None:
            expected_repair = {
                "field": "company_identity",
                "table_raw": "",
                "page_text_value": "RESOLVE SALVAGE & FIRE (NETHERLANDS) B.V.",
                "basis": "same_byte_pinned_page_text",
            }
            if fields["source_progressive"] != "1199" or repair != expected_repair:
                raise RuntimeError("Ravenna reviewed extraction-repair evidence drift")
        elif fields["source_progressive"] == "1199":
            raise RuntimeError("Ravenna reviewed row 1199 lost extraction-repair evidence")
        record["source_fields"] = {
            "physical_locator": fields["source_progressive"],
            "sections": list(fields["sections"]),
            "registered_office_variants": list(fields["registered_office_variants"]),
            "application_date_raw_variants": list(fields["application_date_raw_variants"]),
            "listing_date_raw_variants": list(fields["listing_date_raw_variants"]),
            "normalised_listing_date_variants": list(fields["normalised_listing_date_variants"]),
            "malformed_date_pairs": list(fields["malformed_date_pairs"]),
            "notes": [fields["note_raw"]] if fields["note_raw"] else [],
        }
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)

'''

if "def _adapt_ravenna_public_fields" not in text:
    anchor = "def _adapt_genova_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n"
    if anchor not in text:
        raise RuntimeError("Ravenna adapter definition anchor drift")
    text = text.replace(anchor, adapter + anchor, 1)

call_anchor = '''    if cfg["parser"] in PORDENONE_PARSERS:
        batch = _adapt_pordenone_public_fields(batch, cfg["parser"])
'''
call_addition = call_anchor + '''    if cfg["parser"] in RAVENNA_PARSERS:
        batch = _adapt_ravenna_public_fields(batch, cfg["parser"])
'''
text = replace_once(text, call_anchor, call_addition, label="Ravenna public adapter dispatch")
registry_path.write_text(text, encoding="utf-8")

browser_path = ROOT / "tests/public_portal_browser.cjs"
text = browser_path.read_text(encoding="utf-8")
old = "      assert.equal(ravenna.filter(r=>r.source_fields.source_progressive==='1199'&&r.name==='RESOLVE SALVAGE & FIRE (NETHERLANDS) B.V.'&&r.source_fields.reviewed_extraction_repair?.basis==='same_byte_pinned_page_text').length,1);\n"
new = (
    "      assert.equal(ravenna.filter(r=>r.source_fields.physical_locator==='1199'&&r.name==='RESOLVE SALVAGE & FIRE (NETHERLANDS) B.V.'&&r.source_status==='pending'&&r.application_date==='2026-02-04'&&r.requested_activities.includes('Sezione X')).length,1);\n"
    "      assert.equal(ravenna.filter(r=>Object.prototype.hasOwnProperty.call(r.source_fields,'source_progressive')||Object.prototype.hasOwnProperty.call(r.source_fields,'reviewed_extraction_repair')).length,0);\n"
)
text = replace_once(text, old, new, label="Ravenna browser public-field assertion")
browser_path.write_text(text, encoding="utf-8")

print("Ravenna public adapter materialised without widening the public contract")

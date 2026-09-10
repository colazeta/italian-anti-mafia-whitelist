"""Explicit, recursively closed publication contract. No internal row is serialised wholesale."""
from __future__ import annotations

from collections import Counter
from typing import Any

# Existing approved company attributes, including source-specific observations.
TEXT_FIELDS = frozenset("record_locator source_key authority_key authority_name register_key register_name population_scope reference_date name registered_office secondary_office identifier_field_raw requested_activities_raw source_status outcome_raw application_date observed_listing_date decision_date registration_date observed_expiry_date primary_date primary_date_label source_page_url resource_url capture_sha256 parser_name parser_version".split())
RECORD_FIELDS = TEXT_FIELDS | {"source_row_ordinal", "identifiers", "requested_activities", "application_dates", "source_fields"}
IDENTIFIER_FIELDS = {"raw_value", "shape", "candidate_schemes", "scheme_assertion", "source_hint"}
SOURCE_LIST_FIELDS = {
    "sections",
    "registered_office_variants",
    "secondary_office_variants",
    "listing_date_raw_variants",
    "application_date_raw_variants",
    "expiry_date_raw_variants",
    "normalised_listing_date_variants",
    "normalised_expiry_date_variants",
    "date_conflict_fields",
    "malformed_date_pairs",
}
SOURCE_FIELDS = SOURCE_LIST_FIELDS | {"provvedimento", "in_aggiornamento", "outcome", "requested_activities_source"}
OUTCOME_FIELDS = {"status", "observed_listing_date", "observed_expiry_date", "renewal_requested", "update_in_progress", "dates"}
DATE_FIELDS = {"raw_value", "date", "parenthesized"}
SOURCE_REPORT_FIELDS = {"source_key", "authority_key", "register_key", "population_scope", "reference_date", "sha256", "parser", "document_checked_at"}
META_FIELDS = {"contract_version", "unit", "generated_at", "record_count", "authority_count", "register_count", "source_count", "authority_counts", "register_counts", "status_counts", "interpretation", "geography_policy", "sources"}


def _keys(value: dict, allowed: set | frozenset, context: str) -> None:
    extra = value.keys() - allowed
    if extra:
        raise ValueError(f"Unapproved public fields in {context}: {sorted(extra)}")


def _strings(value: Any) -> None:
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError("Public string list expected")


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on additions; preserve all already approved values and identities."""
    _keys(record, RECORD_FIELDS, "record")
    for key in TEXT_FIELDS & record.keys():
        if not isinstance(record[key], str):
            raise ValueError(f"Public text expected: {key}")
    if type(record.get("source_row_ordinal")) is not int:
        raise ValueError("Public source row ordinal expected")
    for key in ("requested_activities", "application_dates"):
        if key in record:
            _strings(record[key])
    if not isinstance(record.get("identifiers", []), list):
        raise ValueError("Public identifiers must be a list")
    for identifier in record.get("identifiers", []):
        if isinstance(identifier, str):
            continue
        _keys(identifier, IDENTIFIER_FIELDS, "identifier")
        for key, value in identifier.items():
            if key == "candidate_schemes":
                _strings(value)
            elif value is not None and not isinstance(value, str):
                raise ValueError("Public identifier scalar expected")
    fields = record.get("source_fields", {})
    _keys(fields, SOURCE_FIELDS, "source fields")
    for key, value in fields.items():
        if key in SOURCE_LIST_FIELDS:
            _strings(value)
        elif key == "outcome":
            _keys(value, OUTCOME_FIELDS, "source outcome")
            for name, item in value.items():
                if name == "dates":
                    for date in item:
                        _keys(date, DATE_FIELDS, "source date")
                        if any(type(v) not in (str, bool) for v in date.values()):
                            raise ValueError("Public date scalar expected")
                elif type(item) not in (str, bool, type(None)):
                    raise ValueError("Public outcome scalar expected")
        elif not isinstance(value, str):
            raise ValueError("Public source text expected")
    return {key: record[key] for key in record if key in RECORD_FIELDS}


def validate_registry(registry: dict[str, Any]) -> None:
    _keys(registry, {"meta", "records"}, "registry")
    records, meta = registry["records"], registry["meta"]
    _keys(meta, META_FIELDS, "registry metadata")
    for record in records:
        public_record(record)
    if len({r["record_locator"] for r in records}) != len(records):
        raise ValueError("Duplicate public observation locator")
    for dimension in ("authority", "register", "status"):
        field = "source_status" if dimension == "status" else f"{dimension}_key"
        counts = dict(Counter(r[field] for r in records))
        if counts != meta[f"{dimension}_counts"]:
            raise ValueError(f"Public {dimension} denominator mismatch")
        if dimension != "status" and len(counts) != meta[f"{dimension}_count"]:
            raise ValueError(f"Public {dimension} count mismatch")
    if len(records) != meta["record_count"] or len(meta["sources"]) != meta["source_count"]:
        raise ValueError("Public observation/source count mismatch")
    for source in meta["sources"]:
        _keys(source, SOURCE_REPORT_FIELDS, "source metadata")
    identities = {(s["source_key"], s["reference_date"], s["sha256"]) for s in meta["sources"]}
    if len(identities) != meta["source_count"]:
        raise ValueError("Duplicate published edition")
    observed = {(r["source_key"], r["reference_date"], r["capture_sha256"]) for r in records}
    if identities != observed:
        raise ValueError("Published observations and source editions do not reconcile")

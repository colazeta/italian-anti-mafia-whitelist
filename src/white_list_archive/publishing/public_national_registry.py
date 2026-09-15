from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from white_list_archive.acquisition.national_index import discover_national_index
from white_list_archive.parsers.cosenza_combined_v2 import PARSER_NAME as COSENZA_PARSER_NAME
from white_list_archive.parsers.cosenza_combined_v2 import PARSER_VERSION as COSENZA_PARSER_VERSION
from white_list_archive.parsers.cosenza_combined_v2 import parse_pdf as parse_cosenza
from white_list_archive.parsers.multi_prefecture_tables import PARSERS, ParsedBatch
from white_list_archive.parsers.arezzo_openxml import PARSERS as AREZZO_PARSERS
from white_list_archive.parsers.avellino_positioned import PARSERS as AVELLINO_PARSERS
from white_list_archive.parsers.pesaro_urbino_combined import PARSERS as PESARO_PARSERS
from white_list_archive.parsers.biella_html import PARSERS as BIELLA_PARSERS
from white_list_archive.parsers.benevento_positioned import PARSERS as BENEVENTO_PARSERS
from white_list_archive.parsers.asti_positioned import PARSERS as ASTI_PARSERS
from white_list_archive.parsers.agrigento_positioned import PARSERS as AGRIGENTO_PARSERS
from white_list_archive.parsers.belluno_combined import PARSERS as BELLUNO_PARSERS
from white_list_archive.parsers.ascoli_piceno_labels import PARSERS as ASCOLI_PARSERS
from white_list_archive.parsers.ancona_combined import PARSERS as ANCONA_PARSERS
from white_list_archive.parsers.bari_tables import PARSERS as BARI_PARSERS
from white_list_archive.parsers.udine_positioned import PARSERS as UDINE_PARSERS
from white_list_archive.parsers.bergamo_positioned import PARSERS as BERGAMO_PARSERS
from white_list_archive.parsers.barletta_andria_trani_tables import PARSERS as BARLETTA_ANDRIA_TRANI_PARSERS
from white_list_archive.parsers.brindisi_tables import PARSERS as BRINDISI_PARSERS
from white_list_archive.parsers.cagliari_tables import PARSERS as CAGLIARI_PARSERS
from white_list_archive.parsers.caltanissetta_tables import PARSERS as CALTANISSETTA_PARSERS
from white_list_archive.parsers.crotone_tables import PARSERS as CROTONE_PARSERS
from white_list_archive.parsers.campobasso_openxml import PARSERS as CAMPOBASSO_PARSERS
from white_list_archive.parsers.brescia_openxml import PARSERS as BRESCIA_PARSERS
from white_list_archive.parsers.bolzano_docx import (
    parse_bolzano_applicants,
    parse_bolzano_listed,
)
from white_list_archive.parsers.caserta_tables import PARSERS as CASERTA_PARSERS
from white_list_archive.parsers.catania_openxml import PARSERS as CATANIA_PARSERS
from white_list_archive.parsers.genova_tables import PARSERS as GENOVA_PARSERS
from white_list_archive.parsers.foggia_tables import parse_foggia_applicants, parse_foggia_listed
from white_list_archive.parsers.forli_cesena_combined import parse_forli_cesena_combined
from white_list_archive.parsers.frosinone_tables import parse_frosinone_applicants, parse_frosinone_listed
from white_list_archive.parsers.gorizia_tables import parse_gorizia_applicants, parse_gorizia_listed
from white_list_archive.parsers.napoli_tables import PARSERS as NAPOLI_PARSERS
from white_list_archive.parsers.padova_tables import PARSERS as PADOVA_PARSERS
from white_list_archive.parsers.perugia_tables import PARSERS as PERUGIA_PARSERS
from white_list_archive.parsers.trento_tables import parse_trento_applicants, parse_trento_listed
from white_list_archive.parsers.lodi_sheets import PARSERS as LODI_PARSERS
from white_list_archive.parsers.roma_positioned import PARSERS as ROMA_PARSERS
from white_list_archive.parsers.pisa_tables import PARSERS as PISA_PARSERS
from white_list_archive.parsers.catanzaro_tables import PARSERS as CATANZARO_PARSERS
from white_list_archive.publishing.public_contract import public_record, validate_registry

USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+public national archive)"
BOLZANO_PARSERS = {
    "bolzano_listed": parse_bolzano_listed,
    "bolzano_applicants": parse_bolzano_applicants,
}
FOGGIA_PARSERS = {
    "foggia_listed": parse_foggia_listed,
    "foggia_applicants": parse_foggia_applicants,
}
FORLI_CESENA_PARSERS = {"forli_cesena_combined": parse_forli_cesena_combined}
FROSINONE_PARSERS = {
    "frosinone_listed": parse_frosinone_listed,
    "frosinone_applicants": parse_frosinone_applicants,
}
GORIZIA_PARSERS = {
    "gorizia_listed": parse_gorizia_listed,
    "gorizia_applicants": parse_gorizia_applicants,
}
TRENTO_PARSERS = {
    "trento_listed": parse_trento_listed,
    "trento_applicants": parse_trento_applicants,
}


def _adapt_bolzano_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Map audited parser evidence onto the already-approved public source-field contract.

    The Bolzano parser keeps source-row diagnostics that are useful for review but are
    deliberately not part of the public contract. This adapter is explicit and fail-closed:
    an unexpected parser field, type, or row/section cardinality stops publication.
    """
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Bolzano source_fields must be a mapping")
        if parser_name == "bolzano_listed":
            expected = {
                "listed_sections",
                "listed_source_rows",
                "listing_date_raw",
                "expiry_date_raw",
                "update_raw_values",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Bolzano listed source-field drift: {sorted(fields)!r}")
            sections = fields["listed_sections"]
            source_rows = fields["listed_source_rows"]
            updates = fields["update_raw_values"]
            if (
                not isinstance(sections, list)
                or any(type(value) is not int for value in sections)
                or not isinstance(source_rows, list)
                or any(type(value) is not int for value in source_rows)
                or len(sections) != len(source_rows)
                or not isinstance(updates, list)
                or any(not isinstance(value, str) for value in updates)
            ):
                raise RuntimeError("Bolzano listed source-field type/cardinality drift")
            listing_raw = fields["listing_date_raw"]
            expiry_raw = fields["expiry_date_raw"]
            if not isinstance(listing_raw, str) or not isinstance(expiry_raw, str):
                raise RuntimeError("Bolzano listed raw-date field type drift")
            record["source_fields"] = {
                "sections": [f"Sezione {section}" for section in sections],
                "listing_date_raw_variants": [listing_raw] if listing_raw else [],
                "expiry_date_raw_variants": [expiry_raw] if expiry_raw else [],
                "in_aggiornamento": " · ".join(updates),
            }
        elif parser_name == "bolzano_applicants":
            expected = {"source_row", "activities_raw", "application_date_raw", "outcome_raw"}
            if set(fields) != expected:
                raise RuntimeError(f"Bolzano applicant source-field drift: {sorted(fields)!r}")
            if type(fields["source_row"]) is not int:
                raise RuntimeError("Bolzano applicant source-row type drift")
            if any(not isinstance(fields[key], str) for key in ("activities_raw", "application_date_raw", "outcome_raw")):
                raise RuntimeError("Bolzano applicant source-field type drift")
            if fields["outcome_raw"]:
                raise RuntimeError("Bolzano applicant outcome became nonblank during publication adaptation")
            application_raw = fields["application_date_raw"]
            record["source_fields"] = {
                "requested_activities_source": fields["activities_raw"],
                "application_date_raw_variants": [application_raw] if application_raw else [],
            }
        else:
            raise RuntimeError(f"Unexpected Bolzano parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)
# The Ministry discovery index also lists its website template. This is not a
# territorial authority. Exclude only the evidenced key from the public directory;
# never delete or filter the underlying national-index discovery evidence.
NON_TERRITORIAL_INDEX_KEYS = frozenset({"sito-tipo"})


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _json_value(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback


def _download(url: str, path: Path) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urlopen(request, timeout=90) as response:  # noqa: S310 - URLs are versioned official-source config
        body = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def _semantic_digest(records: list[dict[str, Any]]) -> str:
    """Hash parsed source semantics while excluding capture/runtime provenance.

    This approval mode is reserved for explicitly configured mutable structured
    sources whose raw wrapper bytes can change independently of the published
    table semantics. Raw capture SHA-256 remains attached to every observation.
    """
    ignored = {"capture_sha256", "parser_name", "parser_version"}
    projected = [
        {key: value for key, value in record.items() if key not in ignored}
        for record in records
    ]
    payload = json.dumps(
        projected, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _adapt_cosenza(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    source_records = parse_cosenza(path)
    records: list[dict[str, Any]] = []
    for source in source_records:
        identifiers = _json_value(source.get("identifiers_json"), [])
        activities = _json_value(source.get("requested_activities_json"), [])
        application_dates = _json_value(source.get("application_dates_json"), [])
        outcome = _json_value(source.get("outcome_json"), {})
        row_ordinal = int(source["row_ordinal"])
        app_dates: list[str] = []
        for value in application_dates if isinstance(application_dates, list) else []:
            if isinstance(value, str):
                date_value = value
            elif isinstance(value, dict):
                date_value = str(value.get("date") or value.get("raw_value") or "")
            else:
                date_value = ""
            if date_value:
                app_dates.append(date_value)
        primary_date = str(source.get("observed_listing_date") or "") or (app_dates[0] if app_dates else "")
        primary_label = "Data inserimento osservata" if source.get("observed_listing_date") else "Data presentazione istanza"
        records.append(
            {
                "record_locator": f"{cfg['source_key']}:{cfg['reference_date']}:{row_ordinal}",
                "source_key": cfg["source_key"],
                "authority_key": cfg["authority_key"],
                "authority_name": cfg["authority_name"],
                "register_key": cfg["register_key"],
                "register_name": cfg["register_name"],
                "population_scope": cfg["population_scope"],
                "reference_date": cfg["reference_date"],
                "source_row_ordinal": row_ordinal,
                "name": str(source.get("operator_name_raw") or ""),
                "registered_office": str(source.get("registered_office_raw") or ""),
                "secondary_office": str(source.get("secondary_office_raw") or ""),
                "identifier_field_raw": str(source.get("identifier_field_raw") or ""),
                "identifiers": identifiers if isinstance(identifiers, list) else [],
                "requested_activities": activities if isinstance(activities, list) else [],
                "requested_activities_raw": str(source.get("requested_activities_raw") or ""),
                "source_status": str(source.get("source_status") or "other_or_unknown"),
                "outcome_raw": str(source.get("outcome_raw") or ""),
                "application_date": app_dates[0] if app_dates else "",
                "application_dates": app_dates,
                "observed_listing_date": str(source.get("observed_listing_date") or ""),
                "decision_date": "",
                "registration_date": "",
                "observed_expiry_date": str(source.get("observed_expiry_date") or ""),
                "primary_date": primary_date,
                "primary_date_label": primary_label,
                "source_page_url": cfg["source_page_url"],
                "resource_url": cfg["resource_url"],
                "capture_sha256": cfg["sha256"],
                "parser_name": COSENZA_PARSER_NAME,
                "parser_version": COSENZA_PARSER_VERSION,
                "source_fields": {"outcome": outcome},
            }
        )
    diagnostics = {
        "parser": "cosenza_combined_v2",
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
    }
    return ParsedBatch(records, diagnostics)



def _adapt_foggia_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Project audited Foggia parser evidence onto the closed public contract."""
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Foggia source_fields must be a mapping")
        if parser_name == "foggia_listed":
            expected = {
                "name_variants", "registered_office_variants", "secondary_office_variants",
                "identifier_raw_variants", "sections", "section_heading_raw_variants",
                "listing_date_raw_variants", "expiry_date_raw_variants", "outcome_raw_variants",
                "source_locators", "reviewed_name_reconciliation",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Foggia listed source-field drift: {sorted(fields)!r}")
            list_keys = (
                "name_variants", "registered_office_variants", "secondary_office_variants",
                "identifier_raw_variants", "sections", "section_heading_raw_variants",
                "listing_date_raw_variants", "expiry_date_raw_variants", "outcome_raw_variants",
                "source_locators",
            )
            for key in list_keys:
                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):
                    raise RuntimeError(f"Foggia listed source-field type drift: {key}")
            if not isinstance(fields["reviewed_name_reconciliation"], str):
                raise RuntimeError("Foggia listed reconciliation type drift")
            record["source_fields"] = {
                "registered_office_variants": list(fields["registered_office_variants"]),
                "secondary_office_variants": list(fields["secondary_office_variants"]),
                "sections": list(fields["sections"]),
                "listing_date_raw_variants": list(fields["listing_date_raw_variants"]),
                "expiry_date_raw_variants": list(fields["expiry_date_raw_variants"]),
            }
        elif parser_name == "foggia_applicants":
            expected = {"requested_activities_source", "application_date_raw", "source_locator"}
            if set(fields) != expected:
                raise RuntimeError(f"Foggia applicant source-field drift: {sorted(fields)!r}")
            if any(not isinstance(fields[key], str) for key in expected):
                raise RuntimeError("Foggia applicant source-field type drift")
            application_raw = fields["application_date_raw"]
            record["source_fields"] = {
                "requested_activities_source": fields["requested_activities_source"],
                "application_date_raw_variants": [application_raw] if application_raw else [],
            }
        else:
            raise RuntimeError(f"Unexpected Foggia parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)



def _adapt_frosinone_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Project audited Frosinone evidence onto the closed public source-field contract."""
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Frosinone source_fields must be a mapping")
        if parser_name == "frosinone_listed":
            expected = {
                "source_locator", "continuation_fragments", "identifier_raw",
                "listing_date_raw", "expiry_date_raw", "sections_raw", "note_raw",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Frosinone listed source-field drift: {sorted(fields)!r}")
            scalar_keys = ("source_locator", "identifier_raw", "listing_date_raw", "expiry_date_raw", "sections_raw", "note_raw")
            if any(not isinstance(fields[key], str) for key in scalar_keys):
                raise RuntimeError("Frosinone listed source-field type drift")
            fragments = fields["continuation_fragments"]
            if not isinstance(fragments, list):
                raise RuntimeError("Frosinone listed continuation-fragment type drift")
            for fragment in fragments:
                if not isinstance(fragment, dict) or set(fragment) != {"source_locator", "cells", "before"}:
                    raise RuntimeError("Frosinone listed continuation-fragment shape drift")
                if not isinstance(fragment["source_locator"], str):
                    raise RuntimeError("Frosinone listed continuation locator type drift")
                for key in ("cells", "before"):
                    if not isinstance(fragment[key], list) or len(fragment[key]) != 7 or any(not isinstance(value, str) for value in fragment[key]):
                        raise RuntimeError(f"Frosinone listed continuation {key} drift")
            record["source_fields"] = {
                "sections": [fields["sections_raw"]] if fields["sections_raw"] else [],
                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],
                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],
            }
        elif parser_name == "frosinone_applicants":
            expected = {
                "source_locator", "continuation_fragments", "identifier_raw",
                "sections_raw", "application_date_raw", "outcome_raw",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Frosinone applicant source-field drift: {sorted(fields)!r}")
            scalar_keys = ("source_locator", "identifier_raw", "sections_raw", "application_date_raw", "outcome_raw")
            if any(not isinstance(fields[key], str) for key in scalar_keys):
                raise RuntimeError("Frosinone applicant source-field type drift")
            fragments = fields["continuation_fragments"]
            if not isinstance(fragments, list):
                raise RuntimeError("Frosinone applicant continuation-fragment type drift")
            for fragment in fragments:
                if not isinstance(fragment, dict) or set(fragment) != {"source_locator", "cells", "before"}:
                    raise RuntimeError("Frosinone applicant continuation-fragment shape drift")
                if not isinstance(fragment["source_locator"], str):
                    raise RuntimeError("Frosinone applicant continuation locator type drift")
                for key in ("cells", "before"):
                    if not isinstance(fragment[key], list) or len(fragment[key]) != 7 or any(not isinstance(value, str) for value in fragment[key]):
                        raise RuntimeError(f"Frosinone applicant continuation {key} drift")
            record["source_fields"] = {
                "sections": [fields["sections_raw"]] if fields["sections_raw"] else [],
                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],
            }
        else:
            raise RuntimeError(f"Unexpected Frosinone parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)


def _adapt_gorizia_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Project audited Gorizia evidence onto the closed public source-field contract."""
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Gorizia source_fields must be a mapping")
        if parser_name == "gorizia_listed":
            expected = {"source_rows", "sections", "identifier_raw", "listing_date_raw", "expiry_date_raw", "update_values"}
            if set(fields) != expected:
                raise RuntimeError(f"Gorizia listed source-field drift: {sorted(fields)!r}")
            if not isinstance(fields["source_rows"], list) or any(not isinstance(item, list) or len(item) != 2 or any(type(value) is not int for value in item) for item in fields["source_rows"]):
                raise RuntimeError("Gorizia listed source-row cardinality drift")
            if not isinstance(fields["sections"], list) or any(type(value) is not int for value in fields["sections"]):
                raise RuntimeError("Gorizia listed section type drift")
            if not isinstance(fields["update_values"], list) or any(not isinstance(value, str) for value in fields["update_values"]):
                raise RuntimeError("Gorizia listed update type drift")
            for key in ("identifier_raw", "listing_date_raw", "expiry_date_raw"):
                if not isinstance(fields[key], str):
                    raise RuntimeError(f"Gorizia listed source-field type drift: {key}")
            record["source_fields"] = {
                "sections": [f"Sezione {section}" for section in fields["sections"]],
                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],
                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],
                "in_aggiornamento": " · ".join(value for value in fields["update_values"] if value),
            }
        elif parser_name == "gorizia_applicants":
            expected = {"page", "identifier_raw", "application_date_raw"}
            if set(fields) != expected or type(fields["page"]) is not int or any(not isinstance(fields[key], str) for key in ("identifier_raw", "application_date_raw")):
                raise RuntimeError("Gorizia applicant source-field drift")
            raw = fields["application_date_raw"]
            record["source_fields"] = {"application_date_raw_variants": [raw] if raw else []}
        else:
            raise RuntimeError(f"Unexpected Gorizia parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)

def _adapt_napoli_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Project audited Napoli evidence onto the recursively closed public contract."""
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Napoli source_fields must be a mapping")
        if parser_name == "napoli_listed":
            expected = {
                "sections", "sections_source_raw", "listing_date_raw_variants",
                "expiry_date_raw_variants", "in_aggiornamento", "source_page",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Napoli listed source-field drift: {sorted(fields)!r}")
            for key in ("sections", "listing_date_raw_variants", "expiry_date_raw_variants"):
                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):
                    raise RuntimeError(f"Napoli listed source-field type drift: {key}")
            if not isinstance(fields["sections_source_raw"], str) or not isinstance(fields["in_aggiornamento"], str):
                raise RuntimeError("Napoli listed source-field scalar drift")
            if type(fields["source_page"]) is not int:
                raise RuntimeError("Napoli listed source-page type drift")
            record["source_fields"] = {
                "sections": list(fields["sections"]),
                "listing_date_raw_variants": list(fields["listing_date_raw_variants"]),
                "expiry_date_raw_variants": list(fields["expiry_date_raw_variants"]),
                "in_aggiornamento": fields["in_aggiornamento"],
            }
        elif parser_name == "napoli_applicants":
            expected = {"requested_activities_source", "application_date_raw_variants", "source_page"}
            if set(fields) != expected:
                raise RuntimeError(f"Napoli applicant source-field drift: {sorted(fields)!r}")
            if not isinstance(fields["requested_activities_source"], str):
                raise RuntimeError("Napoli applicant requested-activity source drift")
            raw_dates = fields["application_date_raw_variants"]
            if not isinstance(raw_dates, list) or any(not isinstance(value, str) for value in raw_dates):
                raise RuntimeError("Napoli applicant raw-date type drift")
            if type(fields["source_page"]) is not int:
                raise RuntimeError("Napoli applicant source-page type drift")
            record["source_fields"] = {
                "requested_activities_source": fields["requested_activities_source"],
                "application_date_raw_variants": list(raw_dates),
            }
        else:
            raise RuntimeError(f"Unexpected Napoli parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)

def _adapt_padova_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Project audited Padova evidence onto the recursively closed public contract."""
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Padova source_fields must be a mapping")
        if parser_name == "padova_listed":
            expected = {
                "sections", "section_cells_raw", "listing_date_raw", "expiry_date_raw",
                "note_raw", "source_page", "source_table_row",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Padova listed source-field drift: {sorted(fields)!r}")
            if not isinstance(fields["sections"], list) or any(not isinstance(value, str) for value in fields["sections"]):
                raise RuntimeError("Padova listed section-field type drift")
            if not isinstance(fields["section_cells_raw"], list) or any(not isinstance(value, str) for value in fields["section_cells_raw"]):
                raise RuntimeError("Padova listed section-cell type drift")
            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw", "note_raw")):
                raise RuntimeError("Padova listed raw scalar type drift")
            if type(fields["source_page"]) is not int or type(fields["source_table_row"]) is not int:
                raise RuntimeError("Padova listed source-locator type drift")
            record["source_fields"] = {
                "sections": list(fields["sections"]),
                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],
                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],
            }
        elif parser_name == "padova_applicants":
            expected = {
                "sections", "section_cells_raw", "application_date_raw", "protocol_raw",
                "note_raw", "source_page", "source_table_row",
                "reviewed_name_recovery", "reviewed_source_duplicate",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Padova applicant source-field drift: {sorted(fields)!r}")
            if not isinstance(fields["sections"], list) or any(not isinstance(value, str) for value in fields["sections"]):
                raise RuntimeError("Padova applicant section-field type drift")
            if not isinstance(fields["section_cells_raw"], list) or any(not isinstance(value, str) for value in fields["section_cells_raw"]):
                raise RuntimeError("Padova applicant section-cell type drift")
            if any(not isinstance(fields[key], str) for key in ("application_date_raw", "protocol_raw", "note_raw")):
                raise RuntimeError("Padova applicant raw scalar type drift")
            if type(fields["source_page"]) is not int or type(fields["source_table_row"]) is not int:
                raise RuntimeError("Padova applicant source-locator type drift")
            if type(fields["reviewed_name_recovery"]) is not bool or type(fields["reviewed_source_duplicate"]) is not bool:
                raise RuntimeError("Padova applicant reviewed-evidence flag type drift")
            record["source_fields"] = {
                "sections": list(fields["sections"]),
                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],
            }
        else:
            raise RuntimeError(f"Unexpected Padova parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)


def _adapt_perugia_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Project audited Perugia evidence onto the recursively closed public contract."""
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Perugia source_fields must be a mapping")
        if parser_name == "perugia_listed":
            expected = {
                "sections", "source_memberships", "name_variants",
                "registered_office_variants", "secondary_office_variants",
                "identifier_raw_variants", "listing_date_raw", "expiry_date_raw",
                "update_raw", "reviewed_date_exception",
                "reviewed_chronology_inversion",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Perugia listed source-field drift: {sorted(fields)!r}")
            for key in ("sections", "name_variants", "registered_office_variants", "secondary_office_variants", "identifier_raw_variants"):
                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):
                    raise RuntimeError(f"Perugia listed source-list type drift: {key}")
            if not isinstance(fields["source_memberships"], list) or any(not isinstance(value, dict) for value in fields["source_memberships"]):
                raise RuntimeError("Perugia listed source-membership type drift")
            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw", "update_raw")):
                raise RuntimeError("Perugia listed raw scalar type drift")
            if type(fields["reviewed_date_exception"]) is not bool or type(fields["reviewed_chronology_inversion"]) is not bool:
                raise RuntimeError("Perugia listed reviewed-evidence flag type drift")
            record["source_fields"] = {
                "sections": list(fields["sections"]),
                "registered_office_variants": list(fields["registered_office_variants"]),
                "secondary_office_variants": list(fields["secondary_office_variants"]),
                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],
                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],
                "in_aggiornamento": fields["update_raw"],
            }
        elif parser_name == "perugia_applicants":
            expected = {
                "activities_raw", "application_date_raw", "outcome_raw",
                "source_page", "source_table_row", "continuation_fragments",
                "reviewed_blank_company_name", "reviewed_application_date_exception",
                "reviewed_missing_decision_date", "reviewed_bare_outcome",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Perugia applicant source-field drift: {sorted(fields)!r}")
            if any(not isinstance(fields[key], str) for key in ("activities_raw", "application_date_raw", "outcome_raw")):
                raise RuntimeError("Perugia applicant raw scalar type drift")
            if type(fields["source_page"]) is not int or type(fields["source_table_row"]) is not int:
                raise RuntimeError("Perugia applicant source-locator type drift")
            if not isinstance(fields["continuation_fragments"], list) or any(not isinstance(value, dict) for value in fields["continuation_fragments"]):
                raise RuntimeError("Perugia applicant continuation evidence type drift")
            for key in ("reviewed_blank_company_name", "reviewed_application_date_exception", "reviewed_missing_decision_date", "reviewed_bare_outcome"):
                if type(fields[key]) is not bool:
                    raise RuntimeError(f"Perugia applicant reviewed-evidence flag type drift: {key}")
            record["source_fields"] = {
                "requested_activities_source": fields["activities_raw"],
                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],
            }
        else:
            raise RuntimeError(f"Unexpected Perugia parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)


def _adapt_trento_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Project audited Trento evidence onto the recursively closed public contract."""
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Trento source_fields must be a mapping")
        if parser_name == "trento_listed":
            expected = {
                "sections", "source_memberships", "name_variants",
                "registered_office_variants", "secondary_office_variants",
                "identifier_raw_variants", "listing_date_raw", "expiry_date_raw",
                "update_raw", "identifier_source_evidence", "reviewed_date_exception",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Trento listed source-field drift: {sorted(fields)!r}")
            for key in (
                "sections", "name_variants", "registered_office_variants",
                "secondary_office_variants", "identifier_raw_variants",
                "identifier_source_evidence",
            ):
                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):
                    raise RuntimeError(f"Trento listed source-list type drift: {key}")
            if not isinstance(fields["source_memberships"], list) or any(not isinstance(value, dict) for value in fields["source_memberships"]):
                raise RuntimeError("Trento listed source-membership type drift")
            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw", "update_raw")):
                raise RuntimeError("Trento listed raw scalar type drift")
            if type(fields["reviewed_date_exception"]) is not bool:
                raise RuntimeError("Trento listed reviewed-evidence flag type drift")
            record["source_fields"] = {
                "sections": list(fields["sections"]),
                "registered_office_variants": list(fields["registered_office_variants"]),
                "secondary_office_variants": list(fields["secondary_office_variants"]),
                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],
                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],
                "in_aggiornamento": fields["update_raw"],
            }
        elif parser_name == "trento_applicants":
            expected = {
                "activities_raw", "application_date_raw", "integration_date_raw",
                "outcome_raw", "source_page", "source_table", "source_table_row",
                "continuation_fragments", "reviewed_application_date_exception",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Trento applicant source-field drift: {sorted(fields)!r}")
            if any(not isinstance(fields[key], str) for key in ("activities_raw", "application_date_raw", "integration_date_raw", "outcome_raw")):
                raise RuntimeError("Trento applicant raw scalar type drift")
            if any(type(fields[key]) is not int for key in ("source_page", "source_table", "source_table_row")):
                raise RuntimeError("Trento applicant source-locator type drift")
            if not isinstance(fields["continuation_fragments"], list) or any(not isinstance(value, dict) for value in fields["continuation_fragments"]):
                raise RuntimeError("Trento applicant continuation evidence type drift")
            if type(fields["reviewed_application_date_exception"]) is not bool:
                raise RuntimeError("Trento applicant reviewed-evidence flag type drift")
            record["source_fields"] = {
                "requested_activities_source": fields["activities_raw"],
                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],
            }
        else:
            raise RuntimeError(f"Unexpected Trento parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)


def _adapt_lodi_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Project audited Lodi evidence onto the recursively closed public source-field contract."""
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Lodi source_fields must be a mapping")
        if parser_name == "lodi_listed":
            expected = {
                "sections", "source_memberships", "name_variants",
                "registered_office_variants", "secondary_office_variants",
                "identifier_raw_variants", "listing_date_raw", "expiry_date_raw",
                "update_raw",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Lodi listed source-field drift: {sorted(fields)!r}")
            for key in (
                "sections", "name_variants", "registered_office_variants",
                "secondary_office_variants", "identifier_raw_variants",
            ):
                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):
                    raise RuntimeError(f"Lodi listed source-list type drift: {key}")
            memberships = fields["source_memberships"]
            if not isinstance(memberships, list) or not memberships or any(not isinstance(value, dict) for value in memberships):
                raise RuntimeError("Lodi listed source-membership type/cardinality drift")
            expected_membership = {
                "source_row", "section", "name_raw", "registered_office_raw",
                "secondary_office_raw", "identifier_raw", "listing_date_raw",
                "expiry_date_raw", "update_raw",
            }
            for membership in memberships:
                if set(membership) != expected_membership or type(membership["source_row"]) is not int:
                    raise RuntimeError("Lodi listed source-membership shape drift")
                if any(not isinstance(membership[key], str) for key in expected_membership - {"source_row"}):
                    raise RuntimeError("Lodi listed source-membership scalar drift")
            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw", "update_raw")):
                raise RuntimeError("Lodi listed raw scalar type drift")
            record["source_fields"] = {
                "sections": list(fields["sections"]),
                "registered_office_variants": list(fields["registered_office_variants"]),
                "secondary_office_variants": list(fields["secondary_office_variants"]),
                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],
                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],
                "in_aggiornamento": fields["update_raw"],
            }
        elif parser_name == "lodi_applicants":
            expected = {"source_row", "activities_raw", "application_date_raw", "outcome_raw"}
            if set(fields) != expected or type(fields["source_row"]) is not int:
                raise RuntimeError("Lodi applicant source-field shape drift")
            if any(not isinstance(fields[key], str) for key in ("activities_raw", "application_date_raw", "outcome_raw")):
                raise RuntimeError("Lodi applicant source-field scalar drift")
            record["source_fields"] = {
                "requested_activities_source": fields["activities_raw"],
                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],
            }
        else:
            raise RuntimeError(f"Unexpected Lodi parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)


def _adapt_roma_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:
    """Project audited Roma positioned-PDF evidence onto the closed public source-field contract."""
    adapted: list[dict[str, Any]] = []
    for source_record in batch.records:
        record = dict(source_record)
        fields = record.get("source_fields")
        if not isinstance(fields, dict):
            raise RuntimeError("Roma source_fields must be a mapping")
        sections = record.get("requested_activities")
        if not isinstance(sections, list) or any(not isinstance(value, str) for value in sections):
            raise RuntimeError("Roma requested-activity/section type drift")
        if parser_name == "roma_positioned_listed":
            expected = {
                "source_page", "source_row_on_page", "listing_date_raw",
                "registration_protocol_raw", "expiry_date_raw", "sections_raw",
                "note_raw", "reviewed_header_note_contamination",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Roma listed source-field drift: {sorted(fields)!r}")
            if any(type(fields[key]) is not int for key in ("source_page", "source_row_on_page")):
                raise RuntimeError("Roma listed source-locator type drift")
            if type(fields["reviewed_header_note_contamination"]) is not bool:
                raise RuntimeError("Roma listed reviewed-header flag type drift")
            for key in ("listing_date_raw", "registration_protocol_raw", "expiry_date_raw", "sections_raw", "note_raw"):
                if not isinstance(fields[key], str):
                    raise RuntimeError(f"Roma listed source-field scalar drift: {key}")
            update_raw = fields["note_raw"] if record.get("source_status") == "renewal_update_in_progress" else ""
            record["source_fields"] = {
                "sections": list(sections),
                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],
                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],
                "in_aggiornamento": update_raw,
            }
        elif parser_name == "roma_positioned_applicants":
            expected = {
                "source_page", "source_row_on_page", "application_date_raw",
                "sections_raw", "note_raw",
            }
            if set(fields) != expected:
                raise RuntimeError(f"Roma applicant source-field drift: {sorted(fields)!r}")
            if any(type(fields[key]) is not int for key in ("source_page", "source_row_on_page")):
                raise RuntimeError("Roma applicant source-locator type drift")
            for key in ("application_date_raw", "sections_raw", "note_raw"):
                if not isinstance(fields[key], str):
                    raise RuntimeError(f"Roma applicant source-field scalar drift: {key}")
            record["source_fields"] = {
                "sections": list(sections),
                "requested_activities_source": fields["sections_raw"],
                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],
                "in_aggiornamento": fields["note_raw"],
            }
        else:
            raise RuntimeError(f"Unexpected Roma parser: {parser_name!r}")
        adapted.append(record)
    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)


def _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg["parser"] == "cosenza_combined_v2":
        return _adapt_cosenza(path, cfg)
    parser = (
        PARSERS.get(cfg["parser"])
        or AREZZO_PARSERS.get(cfg["parser"])
        or AVELLINO_PARSERS.get(cfg["parser"])
        or PESARO_PARSERS.get(cfg["parser"])
        or BIELLA_PARSERS.get(cfg["parser"])
        or BENEVENTO_PARSERS.get(cfg["parser"])
        or ASTI_PARSERS.get(cfg["parser"])
        or AGRIGENTO_PARSERS.get(cfg["parser"])
        or BELLUNO_PARSERS.get(cfg["parser"])
        or ASCOLI_PARSERS.get(cfg["parser"])
        or ANCONA_PARSERS.get(cfg["parser"])
        or BARI_PARSERS.get(cfg["parser"])
        or UDINE_PARSERS.get(cfg["parser"])
        or BERGAMO_PARSERS.get(cfg["parser"])
        or BARLETTA_ANDRIA_TRANI_PARSERS.get(cfg["parser"])
        or BRINDISI_PARSERS.get(cfg["parser"])
        or CAGLIARI_PARSERS.get(cfg["parser"])
        or CALTANISSETTA_PARSERS.get(cfg["parser"])
        or CROTONE_PARSERS.get(cfg["parser"])
        or CAMPOBASSO_PARSERS.get(cfg["parser"])
        or BRESCIA_PARSERS.get(cfg["parser"])
        or BOLZANO_PARSERS.get(cfg["parser"])
        or CASERTA_PARSERS.get(cfg["parser"])
        or CATANIA_PARSERS.get(cfg["parser"])
        or GENOVA_PARSERS.get(cfg["parser"])
        or FOGGIA_PARSERS.get(cfg["parser"])
        or FORLI_CESENA_PARSERS.get(cfg["parser"])
        or FROSINONE_PARSERS.get(cfg["parser"])
        or GORIZIA_PARSERS.get(cfg["parser"])
        or NAPOLI_PARSERS.get(cfg["parser"])
        or PADOVA_PARSERS.get(cfg["parser"])
        or PERUGIA_PARSERS.get(cfg["parser"])
        or TRENTO_PARSERS.get(cfg["parser"])
        or LODI_PARSERS.get(cfg["parser"])
        or ROMA_PARSERS.get(cfg["parser"])
        or PISA_PARSERS.get(cfg["parser"])
        or CATANZARO_PARSERS.get(cfg["parser"])
    )
    if parser is None:
        raise KeyError(f"No approved public parser for {cfg['parser']}")
    batch = parser(path, cfg)
    if cfg["parser"] in BOLZANO_PARSERS:
        batch = _adapt_bolzano_public_fields(batch, cfg["parser"])
    if cfg["parser"] in GENOVA_PARSERS:
        batch = _adapt_genova_public_fields(batch, cfg["parser"])
    if cfg["parser"] in FOGGIA_PARSERS:
        batch = _adapt_foggia_public_fields(batch, cfg["parser"])
    if cfg["parser"] in FROSINONE_PARSERS:
        batch = _adapt_frosinone_public_fields(batch, cfg["parser"])
    if cfg["parser"] in GORIZIA_PARSERS:
        batch = _adapt_gorizia_public_fields(batch, cfg["parser"])
    if cfg["parser"] in NAPOLI_PARSERS:
        batch = _adapt_napoli_public_fields(batch, cfg["parser"])
    if cfg["parser"] in PADOVA_PARSERS:
        batch = _adapt_padova_public_fields(batch, cfg["parser"])
    if cfg["parser"] in PERUGIA_PARSERS:
        batch = _adapt_perugia_public_fields(batch, cfg["parser"])
    if cfg["parser"] in TRENTO_PARSERS:
        batch = _adapt_trento_public_fields(batch, cfg["parser"])
    if cfg["parser"] in LODI_PARSERS:
        batch = _adapt_lodi_public_fields(batch, cfg["parser"])
    if cfg["parser"] in ROMA_PARSERS:
        batch = _adapt_roma_public_fields(batch, cfg["parser"])
    for record in batch.records:
        record["parser_name"] = cfg["parser"]
        record["parser_version"] = "2" if cfg["parser"] in NAPOLI_PARSERS else "1"
    return batch


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


def _validate_batch(cfg: dict[str, Any], batch: ParsedBatch) -> None:
    diagnostics = batch.diagnostics
    if cfg.get("expected_source_rows") is not None and diagnostics["public_records"] != int(cfg["expected_source_rows"]):
        raise RuntimeError(
            f"{cfg['source_key']}: expected {cfg['expected_source_rows']} source rows, got {diagnostics['public_records']}"
        )
    if cfg.get("expected_sector_rows") is not None and diagnostics.get("sector_rows") != int(cfg["expected_sector_rows"]):
        raise RuntimeError(
            f"{cfg['source_key']}: expected {cfg['expected_sector_rows']} sector rows, got {diagnostics.get('sector_rows')}"
        )
    if diagnostics.get("dropped_date_rows", 0):
        raise RuntimeError(
            f"{cfg['source_key']}: parser dropped {diagnostics['dropped_date_rows']} rows containing a source date"
        )
    if not batch.records:
        raise RuntimeError(f"{cfg['source_key']}: no public records parsed")


def build_registry(config: dict[str, Any], work_dir: Path) -> dict[str, Any]:
    all_records: list[dict[str, Any]] = []
    source_reports: list[dict[str, Any]] = []
    for cfg in config["sources"]:
        suffix = Path(urlparse(cfg["resource_url"]).path).suffix or ".pdf"
        local_path = work_dir / f"{cfg['source_key']}{suffix}"
        actual_sha = _download(cfg["resource_url"], local_path)
        approval_mode = str(cfg.get("approval_mode") or "raw_sha256")
        if approval_mode not in {"raw_sha256", "semantic_sha256"}:
            raise RuntimeError(f"{cfg['source_key']}: unsupported approval mode {approval_mode!r}")
        if approval_mode == "raw_sha256" and actual_sha != cfg["sha256"]:
            raise RuntimeError(
                f"{cfg['source_key']}: approved source SHA mismatch; expected {cfg['sha256']}, got {actual_sha}"
            )

        # Parsers record the bytes actually inspected. For immutable resources
        # this remains identical to the approved raw hash.
        parse_cfg = dict(cfg)
        parse_cfg["sha256"] = actual_sha
        batch = _parse_source(local_path, parse_cfg)
        _validate_batch(cfg, batch)
        if approval_mode == "semantic_sha256":
            expected_semantic_sha = str(cfg.get("semantic_sha256") or "")
            if not expected_semantic_sha:
                raise RuntimeError(f"{cfg['source_key']}: semantic approval requires semantic_sha256")
            actual_semantic_sha = _semantic_digest(batch.records)
            if actual_semantic_sha != expected_semantic_sha:
                raise RuntimeError(
                    f"{cfg['source_key']}: approved semantic SHA mismatch; "
                    f"expected {expected_semantic_sha}, got {actual_semantic_sha}"
                )
        all_records.extend(public_record(record) for record in batch.records)
        # Build diagnostics remain review evidence, outside the Pages artifact.
        (work_dir / f"{cfg['source_key']}.diagnostics.json").write_text(
            json.dumps(batch.diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        source_reports.append(
            {
                "source_key": cfg["source_key"],
                "authority_key": cfg["authority_key"],
                "register_key": cfg["register_key"],
                "population_scope": cfg["population_scope"],
                "reference_date": cfg["reference_date"],
                "sha256": actual_sha,
                "parser": cfg["parser"],
                "document_checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )

    authority_counts = Counter(record["authority_key"] for record in all_records)
    register_counts = Counter(record["register_key"] for record in all_records)
    status_counts = Counter(record["source_status"] for record in all_records)
    registry = {
        "meta": {
            "contract_version": 3,
            "unit": "source-backed public observation grouped only where the source repeats one entity across sectors",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "record_count": len(all_records),
            "authority_count": len(authority_counts),
            "register_count": len(register_counts),
            "source_count": len(source_reports),
            "authority_counts": dict(authority_counts),
            "register_counts": dict(register_counts),
            "status_counts": dict(status_counts),
            "interpretation": (
                "Records are source-backed observations from approved current editions. Sector-only repetition is grouped for readability, "
                "but the export does not assert a nationally deduplicated canonical LegalEntity."
            ),
            "geography_policy": "Publication does not wait for optional geographic enrichment.",
            "sources": source_reports,
        },
        "records": all_records,
    }
    validate_registry(registry)
    return registry


def _display_list(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = str(item.get("raw_value") or item.get("value") or item.get("label") or item.get("date") or "")
        else:
            text = str(item)
        if _clean(text):
            out.append(_clean(text))
    return " · ".join(out)


def write_registry_csv(registry: dict[str, Any], path: Path) -> None:
    fields = [
        "record_locator",
        "authority_name",
        "register_name",
        "reference_date",
        "name",
        "registered_office",
        "secondary_office",
        "identifiers",
        "requested_activities",
        "source_status",
        "primary_date_label",
        "primary_date",
        "application_date",
        "observed_listing_date",
        "decision_date",
        "registration_date",
        "observed_expiry_date",
        "outcome_raw",
        "source_page_url",
        "resource_url",
        "capture_sha256",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in registry["records"]:
            writer.writerow(
                {
                    **{field: record.get(field, "") for field in fields},
                    "identifiers": _display_list(record.get("identifiers")),
                    "requested_activities": _display_list(record.get("requested_activities")),
                }
            )


def _authority_key_from_url(url: str, jurisdiction: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if "prefetture" in parts:
        idx = parts.index("prefetture")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    folded = unicodedata.normalize("NFKD", jurisdiction).encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_prefecture_index(
    config: dict[str, Any],
    verified_pages: Path,
    source_series: Path,
) -> dict[str, Any]:
    entries = discover_national_index(max_pages=12, timeout=45)
    if len(entries) < 90:
        raise RuntimeError(f"National White List index unexpectedly small: {len(entries)} entries")

    verified = {row["authority_key"]: row for row in _read_csv(verified_pages)}
    series_by_authority: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _read_csv(source_series):
        series_by_authority[row["authority_key"]].append(row)
    published_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in config["sources"]:
        published_sources[source["authority_key"]].append(source)

    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = _authority_key_from_url(entry.white_list_url, entry.jurisdiction_name)
        if key in NON_TERRITORIAL_INDEX_KEYS:
            continue
        item = grouped.setdefault(
            key,
            {
                "authority_key": key,
                "jurisdiction_name": entry.jurisdiction_name,
                "official_white_list_urls": [],
                "national_index_title": entry.title,
            },
        )
        if entry.white_list_url not in item["official_white_list_urls"]:
            item["official_white_list_urls"].append(entry.white_list_url)

    rows: list[dict[str, Any]] = []
    for key, item in grouped.items():
        series = series_by_authority.get(key, [])
        published = published_sources.get(key, [])
        verified_row = verified.get(key)
        # A page's modification date is not the reference date of its attachment.
        last_source_update = max((source.get("reference_date", "") for source in published), default="")
        if published:
            status = "published"
        elif verified_row:
            status = "source_mapped"
        else:
            status = "discovered"
        rows.append(
            {
                **item,
                "mapping_status": status,
                "mapped": bool(verified_row),
                "published": bool(published),
                "series_count": len(series),
                "publication_models": sorted({row["publication_model"] for row in series if row.get("publication_model")}),
                "published_registers": sorted({source["register_name"] for source in published}),
                "last_project_check": verified_row.get("verification_date", "") if verified_row else "",
                "last_source_update": last_source_update,
                "last_source_update_basis": "reference_date of approved published edition" if published else "",
                "verified_primary_page": verified_row.get("landing_url", "") if verified_row else "",
            }
        )
    rows.sort(key=lambda row: row["jurisdiction_name"].casefold())
    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "national_index_url": "https://prefettura.interno.gov.it/it/white-list-nazionale",
            "authority_count": len(rows),
            "published_count": sum(row["published"] for row in rows),
            "mapped_count": sum(row["mapped"] for row in rows),
            "status_counts": dict(Counter(row["mapping_status"] for row in rows)),
        },
        "prefectures": rows,
    }


def write_prefecture_csv(index: dict[str, Any], path: Path) -> None:
    fields = [
        "jurisdiction_name",
        "authority_key",
        "mapping_status",
        "series_count",
        "publication_models",
        "published_registers",
        "last_project_check",
        "last_source_update",
        "verified_primary_page",
        "official_white_list_urls",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in index["prefectures"]:
            writer.writerow(
                {
                    **{field: row.get(field, "") for field in fields},
                    "publication_models": " · ".join(row["publication_models"]),
                    "published_registers": " · ".join(row["published_registers"]),
                    "official_white_list_urls": " · ".join(row["official_white_list_urls"]),
                }
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the public multi-Prefecture pilot registry and national Prefecture index")
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--verified-pages", type=Path, required=True)
    parser.add_argument("--source-series", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--registry-json", type=Path, required=True)
    parser.add_argument("--registry-csv", type=Path, required=True)
    parser.add_argument("--prefectures-json", type=Path, required=True)
    parser.add_argument("--prefectures-csv", type=Path, required=True)
    args = parser.parse_args(argv)

    config = json.loads(args.source_config.read_text(encoding="utf-8"))
    registry = build_registry(config, args.work_dir)
    prefectures = build_prefecture_index(config, args.verified_pages, args.source_series)

    args.registry_json.parent.mkdir(parents=True, exist_ok=True)
    args.registry_json.write_text(json.dumps(registry, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_registry_csv(registry, args.registry_csv)
    args.prefectures_json.write_text(json.dumps(prefectures, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_prefecture_csv(prefectures, args.prefectures_csv)

    print(
        json.dumps(
            {
                "registry_records": registry["meta"]["record_count"],
                "authorities_published": registry["meta"]["authority_count"],
                "registers_published": registry["meta"]["register_count"],
                "status_counts": registry["meta"]["status_counts"],
                "prefectures_in_national_index": prefectures["meta"]["authority_count"],
                "mapped_prefectures": prefectures["meta"]["mapped_count"],
                "published_prefectures": prefectures["meta"]["published_count"],
                "source_diagnostics": registry["meta"]["sources"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

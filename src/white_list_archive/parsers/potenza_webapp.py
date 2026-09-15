from __future__ import annotations

import html
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
PARSER_NAME = "potenza_combined"

_EXPECTED_ROW_KEYS = {
    "id",
    "ragione_sociale",
    "indirizzo_sede_legale",
    "denom_comune_sede_legale",
    "partita_iva_cf",
    "richiedente",
    "carica_sociale_rich",
    "stato_richiesta",
    "note",
    "data_istanza",
    "data_iscriz",
    "data_scad_iscriz",
    "iscriz_scaduta",
    "agg_incorso",
}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NUMERIC_ID = re.compile(r"^[1-9]\d*$")


def _text(value: Any) -> str:
    return html.unescape(_clean(value))


def _strict_date(value: Any, *, source_id: str, field: str) -> str:
    raw = _text(value)
    if not raw:
        return ""
    if not _DATE.fullmatch(raw):
        raise RuntimeError(f"Potenza unsupported {field} typography for source id {source_id}: {raw!r}")
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Potenza invalid {field} for source id {source_id}: {raw!r}") from exc


def _status(row: dict[str, Any], *, source_id: str) -> str:
    source_status = _text(row["stato_richiesta"])
    update_flag = _text(row["agg_incorso"])
    if source_status == "1" and update_flag == "0":
        return "pending"
    if source_status == "2" and update_flag == "0":
        return "listed"
    if source_status == "2" and update_flag == "1":
        return "renewal_update_in_progress"
    raise RuntimeError(
        "Potenza unreviewed status combination for source id "
        f"{source_id}: stato_richiesta={source_status!r}, agg_incorso={update_flag!r}"
    )


def _office(row: dict[str, Any]) -> str:
    street = _text(row["indirizzo_sede_legale"])
    municipality = _text(row["denom_comune_sede_legale"])
    if street and municipality:
        return f"{street}, {municipality}"
    return street or municipality


def parse_potenza_combined(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Potenza source is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("Result") != "OK":
        raise RuntimeError("Potenza endpoint did not return Result='OK'")
    records_raw = payload.get("Records")
    if not isinstance(records_raw, list) or not records_raw:
        raise RuntimeError("Potenza endpoint returned no Records array")
    try:
        total = int(str(payload.get("TotalRecordCount", "")))
    except ValueError as exc:
        raise RuntimeError("Potenza endpoint returned an invalid TotalRecordCount") from exc
    if total != len(records_raw):
        raise RuntimeError(f"Potenza endpoint pagination drift: TotalRecordCount={total}, Records={len(records_raw)}")

    records: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for ordinal, source in enumerate(records_raw, 1):
        if not isinstance(source, dict):
            raise RuntimeError(f"Potenza source row {ordinal} is not an object")
        if set(source) != _EXPECTED_ROW_KEYS:
            missing = sorted(_EXPECTED_ROW_KEYS - set(source))
            extra = sorted(set(source) - _EXPECTED_ROW_KEYS)
            raise RuntimeError(f"Potenza source-schema drift at row {ordinal}: missing={missing!r}, extra={extra!r}")

        source_id = _text(source["id"])
        if not _NUMERIC_ID.fullmatch(source_id):
            raise RuntimeError(f"Potenza invalid source id at row {ordinal}: {source_id!r}")
        if source_id in source_ids:
            raise RuntimeError(f"Potenza duplicate source id: {source_id}")
        source_ids.add(source_id)

        name = _text(source["ragione_sociale"])
        if not name:
            raise RuntimeError(f"Potenza blank company name for source id {source_id}")
        identifier_raw = _text(source["partita_iva_cf"])
        application_date = _strict_date(source["data_istanza"], source_id=source_id, field="data_istanza")
        listing_date = _strict_date(source["data_iscriz"], source_id=source_id, field="data_iscriz")
        expiry_date = _strict_date(source["data_scad_iscriz"], source_id=source_id, field="data_scad_iscriz")
        status = _status(source, source_id=source_id)

        record = _record(
            cfg,
            ordinal,
            name=name,
            office=_office(source),
            identifier_raw=identifier_raw,
            activities=[],
            status=status,
            outcome_raw=_text(source["stato_richiesta"]),
            application_date=application_date,
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data presentazione istanza" if status == "pending" else "Data iscrizione",
            source_fields={
                "source_id": source_id,
                "ragione_sociale_raw": _clean(source["ragione_sociale"]),
                "indirizzo_sede_legale_raw": _clean(source["indirizzo_sede_legale"]),
                "denom_comune_sede_legale_raw": _clean(source["denom_comune_sede_legale"]),
                "richiedente": _text(source["richiedente"]),
                "carica_sociale_rich": _text(source["carica_sociale_rich"]),
                "stato_richiesta": _text(source["stato_richiesta"]),
                "agg_incorso": _text(source["agg_incorso"]),
                "iscriz_scaduta": _text(source["iscriz_scaduta"]),
                "note": _text(source["note"]),
                "data_istanza_raw": _text(source["data_istanza"]),
                "data_iscriz_raw": _text(source["data_iscriz"]),
                "data_scad_iscriz_raw": _text(source["data_scad_iscriz"]),
            },
        )
        # Potenza exposes a stable internal company id. Prefer it to a row-position
        # locator so harmless alphabetical reordering cannot relabel an observation.
        record["record_locator"] = f"{cfg['source_key']}:{cfg['reference_date']}:id-{source_id}"
        records.append(record)

    statuses = Counter(record["source_status"] for record in records)
    diagnostics = {
        "parser": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "public_records": len(records),
        "distinct_source_ids": len(source_ids),
        "status_counts": dict(statuses),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
        "blank_identifier_fields": sum(not record["identifier_field_raw"] for record in records),
        "application_date_coverage": sum(bool(record["application_date"]) for record in records),
        "listing_date_coverage": sum(bool(record["observed_listing_date"]) for record in records),
        "expiry_date_coverage": sum(bool(record["observed_expiry_date"]) for record in records),
        "nonblank_notes": sum(bool(record["source_fields"]["note"]) for record in records),
        "requested_activity_coverage": 0,
    }
    return ParsedBatch(records=records, diagnostics=diagnostics)


PARSERS = {PARSER_NAME: parse_potenza_combined}

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pdfplumber

_DMY_SLASH = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_DMY_DOT = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
_DMY_FLEX = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{4}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AL_YEAR = re.compile(r"20(?:\s?\d){2}")


@dataclass(frozen=True)
class ParsedBatch:
    records: list[dict[str, Any]]
    diagnostics: dict[str, Any]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def _iso_date(value: str) -> str:
    value = _clean(value)
    if _ISO_DATE.fullmatch(value):
        return value
    match = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", value)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        if 1 <= day <= 31 and 1 <= month <= 12:
            return f"{match.group(3)}-{month:02d}-{day:02d}"
        return ""
    match = re.fullmatch(r"(\d{4})-\s*(\d{2})-(\d{2})", value)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return ""


def _identifiers(text: str) -> list[str]:
    values: list[str] = []
    for token in re.split(r"[\s·;,]+", _clean(text)):
        token = re.sub(r"[^A-Za-z0-9]", "", token).upper()
        if ((token.isdigit() and len(token) == 11) or (len(token) == 16 and token.isalnum())) and token not in values:
            values.append(token)
    return values


def _activities(text: str) -> list[str]:
    text = _clean(text).replace("•", " - ")
    parts = [_clean(item) for item in re.split(r"\s+-\s+", text) if _clean(item)]
    return parts or ([text] if text else [])


def _alessandria_activities(text: str) -> list[str]:
    """Preserve Alessandria's numbered source sections without inventing activity labels."""
    text = _clean(text)
    if not text:
        return []
    if "sezione" not in text.casefold():
        return [text]
    numbers = re.findall(r"\d{1,2}", text)
    return [f"Sezione {number}" for number in numbers] or [text]


def _section_activity(section: str) -> str:
    section = _clean(section)
    return re.sub(r"^Sezione\s+[IVX]+\s*-?\s*", "", section, flags=re.I).strip() or section


def _record(
    cfg: dict[str, Any],
    row_ordinal: int,
    *,
    name: str,
    office: str = "",
    secondary: str = "",
    identifier_raw: str = "",
    activities: list[str] | None = None,
    status: str,
    outcome_raw: str = "",
    application_date: str = "",
    listing_date: str = "",
    decision_date: str = "",
    registration_date: str = "",
    expiry_date: str = "",
    primary_date_label: str = "",
    source_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    application_date = _iso_date(application_date)
    listing_date = _iso_date(listing_date)
    decision_date = _iso_date(decision_date)
    registration_date = _iso_date(registration_date)
    expiry_date = _iso_date(expiry_date)
    primary_date = {
        "Data presentazione istanza": application_date,
        "Data iscrizione": listing_date,
        "Data provvedimento": decision_date,
        "Data registrazione": registration_date,
    }.get(primary_date_label, "")
    return {
        "record_locator": f"{cfg['source_key']}:{cfg['reference_date']}:{row_ordinal}",
        "source_key": cfg["source_key"],
        "authority_key": cfg["authority_key"],
        "authority_name": cfg["authority_name"],
        "register_key": cfg["register_key"],
        "register_name": cfg["register_name"],
        "population_scope": cfg["population_scope"],
        "reference_date": cfg["reference_date"],
        "source_row_ordinal": row_ordinal,
        "name": _clean(name),
        "registered_office": _clean(office),
        "secondary_office": _clean(secondary),
        "identifier_field_raw": _clean(identifier_raw),
        "identifiers": _identifiers(identifier_raw),
        "requested_activities": activities or [],
        "requested_activities_raw": " · ".join(activities or []),
        "source_status": status,
        "outcome_raw": _clean(outcome_raw),
        "application_date": application_date,
        "observed_listing_date": listing_date,
        "decision_date": decision_date,
        "registration_date": registration_date,
        "observed_expiry_date": expiry_date,
        "primary_date": primary_date,
        "primary_date_label": primary_date_label,
        "source_page_url": cfg["source_page_url"],
        "resource_url": cfg["resource_url"],
        "capture_sha256": cfg["sha256"],
        "source_fields": source_fields or {},
    }


def _status_parma(outcome: str) -> str:
    folded = _clean(outcome).casefold()
    if folded == "accolta":
        return "listed"
    if folded == "aggiornamento in corso":
        return "renewal_update_in_progress"
    if folded == "in corso":
        return "pending"
    if "negat" in folded or "interdittiva" in folded:
        return "rejected_or_denied"
    if folded.startswith("scaduta"):
        return "expired_observed"
    if "cancellat" in folded or "scioglimento" in folded:
        return "cancellation_related"
    return "other_or_unknown"


def _table_rows(pdf: pdfplumber.PDF) -> list[tuple[Any, list[str]]]:
    rows: list[tuple[Any, list[str]]] = []
    for page in pdf.pages:
        for table in page.extract_tables():
            for row in table:
                rows.append((page, [_clean(cell) for cell in row]))
    return rows


def parse_parma(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    sector_rows: list[list[str]] = []
    with pdfplumber.open(path) as pdf:
        for _page, row in _table_rows(pdf):
            if len(row) >= 6 and row[0].casefold().startswith("sezione ") and _DMY_SLASH.fullmatch(row[4] or ""):
                sector_rows.append(row[:6])

    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in sector_rows:
        # Keep office in the key: three source cases genuinely vary the office across sectors.
        key = (row[1], row[2], row[3], row[4], row[5])
        group = grouped.setdefault(key, {"row": row, "sections": []})
        if row[0] not in group["sections"]:
            group["sections"].append(row[0])

    records: list[dict[str, Any]] = []
    for group in grouped.values():
        row = group["row"]
        expiry = ""
        match = re.search(r"scaduta(?:\s+il)?\s+(\d{2}/\d{2}/\d{4})", row[5], re.I)
        if match:
            expiry = match.group(1)
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=row[1],
                office=row[2],
                identifier_raw=row[3],
                activities=[_section_activity(section) for section in group["sections"]],
                status=_status_parma(row[5]),
                outcome_raw=row[5],
                application_date=row[4],
                expiry_date=expiry,
                primary_date_label="Data presentazione istanza",
                source_fields={"sections": group["sections"]},
            )
        )

    diagnostics = {
        "parser": "parma_operational",
        "sector_rows": len(sector_rows),
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
    }
    return ParsedBatch(records, diagnostics)


def parse_pistoia_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    sector_rows: list[tuple[str, list[str]]] = []
    current_section = ""
    with pdfplumber.open(path) as pdf:
        for _page, row in _table_rows(pdf):
            if row and row[0].startswith("Sezione ") and not any(row[1:]):
                current_section = row[0]
                continue
            if len(row) >= 7 and _DMY_DOT.fullmatch(row[4] or ""):
                sector_rows.append((current_section, row[:7]))

    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for section, row in sector_rows:
        # Sector PDFs repeat the same entity. Group on identity/date/outcome while retaining
        # any source-level office variation explicitly in source_fields.
        key = (row[0], row[3], row[4], row[5], row[6])
        group = grouped.setdefault(
            key,
            {"row": row, "sections": [], "offices": [], "secondary_offices": []},
        )
        if section and section not in group["sections"]:
            group["sections"].append(section)
        if row[1] and row[1] not in group["offices"]:
            group["offices"].append(row[1])
        if row[2] and row[2] not in group["secondary_offices"]:
            group["secondary_offices"].append(row[2])

    records: list[dict[str, Any]] = []
    for group in grouped.values():
        row = group["row"]
        update = row[6]
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=row[0],
                office=group["offices"][0] if group["offices"] else row[1],
                secondary=group["secondary_offices"][0] if group["secondary_offices"] else row[2],
                identifier_raw=row[3],
                activities=[_section_activity(section) for section in group["sections"]],
                status="renewal_update_in_progress" if update else "listed",
                outcome_raw=update,
                listing_date=row[4],
                expiry_date=row[5],
                primary_date_label="Data iscrizione",
                source_fields={
                    "sections": group["sections"],
                    "registered_office_variants": group["offices"],
                    "secondary_office_variants": group["secondary_offices"],
                },
            )
        )

    diagnostics = {
        "parser": "pistoia_listed",
        "sector_rows": len(sector_rows),
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
    }
    return ParsedBatch(records, diagnostics)


def _status_alessandria_listed(outcome: str) -> str:
    folded = _clean(outcome).casefold()
    if not folded:
        return "listed"
    if "rinnovo" in folded:
        return "renewal_update_in_progress"
    # The current source contains a small number of bare "In istruttoria" notes
    # inside the listed-company document. Preserve that ambiguity rather than
    # silently treating it as a renewal or an applicant record.
    return "other_or_unknown"


def _alessandria_source_date(value: str) -> str:
    """Normalise explicit Alessandria date typography without guessing a source value."""
    raw = _clean(value)
    candidate = re.sub(r"^(\d{1,2})[°º]([./])", r"\1\2", raw)
    # One official cell is extracted as ``202 2``. Removing an embedded numeric
    # layout space preserves the digits visibly present in the source.
    candidate = re.sub(r"(?<=\d)\s+(?=\d)", "", candidate)
    match = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", candidate)
    if not match:
        return ""
    day, month, year = map(int, match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_alessandria_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    sector_rows: list[tuple[str, list[str], str, str]] = []
    current_section = ""
    date_rows = 0
    dropped = 0
    with pdfplumber.open(path) as pdf:
        for _page, row in _table_rows(pdf):
            if row and row[0].upper().startswith("SEZIONE") and not any(row[1:]):
                current_section = row[0]
                continue
            if len(row) < 6 or not (_AL_YEAR.search(row[4] or "") or _AL_YEAR.search(row[5] or "")):
                continue
            date_rows += 1
            if len(row) < 7 or not row[0] or not row[3]:
                dropped += 1
                continue
            listing_date = _alessandria_source_date(row[4])
            expiry_date = _alessandria_source_date(row[5])
            if not listing_date and not expiry_date:
                dropped += 1
                continue
            sector_rows.append((current_section, row[:7], listing_date, expiry_date))

    identities: dict[tuple[str, ...], list[tuple[str, list[str], str, str]]] = {}
    for item in sector_rows:
        _section, row, _listing, _expiry = item
        identities.setdefault((row[0], row[3], row[6]), []).append(item)

    records: list[dict[str, Any]] = []
    conflict_identity_groups = 0
    reconciled_malformed_rows = 0
    for identity_rows in identities.values():
        valid_pairs = {(listing, expiry) for _section, _row, listing, expiry in identity_rows if listing and expiry}
        incomplete = [item for item in identity_rows if not item[2] or not item[3]]
        conflict_fields: list[str] = []
        if len({pair[0] for pair in valid_pairs}) > 1:
            conflict_fields.append("observed_listing_date")
        if len({pair[1] for pair in valid_pairs}) > 1:
            conflict_fields.append("observed_expiry_date")
        if len(valid_pairs) > 1:
            conflict_identity_groups += 1

        if incomplete and len(valid_pairs) != 1:
            # Without one unique complete pair on this exact identity/outcome, an
            # invalid source date cannot be assigned safely. Keep the fail-closed
            # dropped-row signal rather than repairing or choosing a neighbour.
            dropped += len(incomplete)
            incomplete = []

        observations: dict[tuple[str, str], dict[str, Any]] = {}

        def add_to_observation(item: tuple[str, list[str], str, str], pair: tuple[str, str]) -> None:
            section, row, listing, expiry = item
            group = observations.setdefault(
                pair,
                {
                    "row": row,
                    "sections": [],
                    "offices": [],
                    "secondary_offices": [],
                    "listing_raw": [],
                    "expiry_raw": [],
                    "malformed_date_pairs": [],
                },
            )
            if section and section not in group["sections"]:
                group["sections"].append(section)
            if row[1] and row[1] not in group["offices"]:
                group["offices"].append(row[1])
            if row[2] and row[2] not in group["secondary_offices"]:
                group["secondary_offices"].append(row[2])
            if row[4] not in group["listing_raw"]:
                group["listing_raw"].append(row[4])
            if row[5] not in group["expiry_raw"]:
                group["expiry_raw"].append(row[5])
            if not listing or not expiry:
                raw_pair = f"{row[4]} | {row[5]}"
                if raw_pair not in group["malformed_date_pairs"]:
                    group["malformed_date_pairs"].append(raw_pair)

        for item in identity_rows:
            if item in incomplete:
                continue
            listing, expiry = item[2], item[3]
            if listing and expiry:
                add_to_observation(item, (listing, expiry))

        if incomplete and len(valid_pairs) == 1:
            sole_pair = next(iter(valid_pairs))
            for item in incomplete:
                add_to_observation(item, sole_pair)
                reconciled_malformed_rows += 1

        for pair, group in observations.items():
            row = group["row"]
            records.append(
                _record(
                    cfg,
                    len(records) + 1,
                    name=row[0],
                    office=group["offices"][0] if group["offices"] else row[1],
                    secondary=group["secondary_offices"][0] if group["secondary_offices"] else row[2],
                    identifier_raw=row[3],
                    activities=[_section_activity(section) for section in group["sections"]],
                    status=_status_alessandria_listed(row[6]),
                    outcome_raw=row[6],
                    listing_date=pair[0],
                    expiry_date=pair[1],
                    primary_date_label="Data iscrizione",
                    source_fields={
                        "sections": group["sections"],
                        "registered_office_variants": group["offices"],
                        "secondary_office_variants": group["secondary_offices"],
                        "listing_date_raw_variants": group["listing_raw"],
                        "expiry_date_raw_variants": group["expiry_raw"],
                        "normalised_listing_date_variants": [pair[0]],
                        "normalised_expiry_date_variants": [pair[1]],
                        "date_conflict_fields": conflict_fields,
                        "malformed_date_pairs": group["malformed_date_pairs"],
                    },
                )
            )

    return ParsedBatch(
        records,
        {
            "parser": "alessandria_listed",
            "date_rows": date_rows,
            "sector_rows": len(sector_rows),
            "public_records": len(records),
            "dropped_date_rows": dropped,
            "date_conflict_identity_groups": conflict_identity_groups,
            "reconciled_malformed_date_rows": reconciled_malformed_rows,
            "status_counts": dict(Counter(record["source_status"] for record in records)),
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
        },
    )


def parse_alessandria_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    records: list[dict[str, Any]] = []
    date_rows = 0
    dropped = 0
    with pdfplumber.open(path) as pdf:
        for _page, row in _table_rows(pdf):
            if len(row) < 5 or not _DMY_FLEX.fullmatch(row[4] or ""):
                continue
            date_rows += 1
            if len(row) < 6 or not row[0] or not row[2]:
                dropped += 1
                continue
            outcome = row[5]
            folded = outcome.casefold()
            status = (
                "pending"
                if "istruttoria" in folded
                else "rejected_or_denied"
                if "negat" in folded or "rigett" in folded or "dinieg" in folded
                else "other_or_unknown"
            )
            records.append(
                _record(
                    cfg,
                    len(records) + 1,
                    name=row[0],
                    office=row[1],
                    identifier_raw=row[2],
                    activities=_alessandria_activities(row[3]),
                    status=status,
                    outcome_raw=outcome,
                    application_date=row[4],
                    primary_date_label="Data presentazione istanza",
                    source_fields={"requested_activities_source": row[3]},
                )
            )

    return ParsedBatch(
        records,
        {
            "parser": "alessandria_applicants",
            "date_rows": date_rows,
            "public_records": len(records),
            "dropped_date_rows": dropped,
            "status_counts": dict(Counter(record["source_status"] for record in records)),
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
        },
    )


def _fallback_name_at_date(page: Any, date_text: str, *, x1: float = 160.0) -> str:
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    anchors = [word for word in words if _clean(word.get("text")) == date_text]
    if not anchors:
        return ""
    y = (float(anchors[0]["top"]) + float(anchors[0]["bottom"])) / 2
    nearby = [
        word
        for word in words
        if float(word["x0"]) < x1
        and abs(((float(word["top"]) + float(word["bottom"])) / 2) - y) <= 20
    ]
    nearby.sort(key=lambda word: (float(word["top"]), float(word["x0"])))
    return _clean(" ".join(str(word["text"]) for word in nearby))


def parse_pistoia_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    records: list[dict[str, Any]] = []
    date_rows = 0
    recovered_names = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for raw_row in table:
                    row = [_clean(cell) for cell in raw_row]
                    for date_index, value in enumerate(row):
                        if not _DMY_DOT.fullmatch(value or ""):
                            continue
                        date_rows += 1
                        if date_index < 5 or date_index + 1 >= len(row):
                            break
                        name, office, secondary, identifier_raw, activity_text = row[date_index - 5 : date_index]
                        if not name:
                            name = _fallback_name_at_date(page, value)
                            if name:
                                recovered_names += 1
                        if not name or not identifier_raw:
                            break
                        outcome = row[date_index + 1]
                        folded = outcome.casefold()
                        status = (
                            "pending"
                            if "istruttoria" in folded
                            else "rejected_or_denied"
                            if "negat" in folded or "rigett" in folded
                            else "other_or_unknown"
                        )
                        records.append(
                            _record(
                                cfg,
                                len(records) + 1,
                                name=name,
                                office=office,
                                secondary=secondary,
                                identifier_raw=identifier_raw,
                                activities=_activities(activity_text),
                                status=status,
                                outcome_raw=outcome,
                                application_date=value,
                                primary_date_label="Data presentazione istanza",
                            )
                        )
                        break

    diagnostics = {
        "parser": "pistoia_applicants",
        "date_rows": date_rows,
        "public_records": len(records),
        "recovered_names": recovered_names,
        "dropped_date_rows": date_rows - len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
    }
    return ParsedBatch(records, diagnostics)


def _relative_date_rows(
    path: Path,
    cfg: dict[str, Any],
    *,
    listed: bool,
) -> ParsedBatch:
    records: list[dict[str, Any]] = []
    date_rows = 0
    dropped = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for raw_row in table:
                    row = [_clean(cell) for cell in raw_row]
                    for date_index, value in enumerate(row):
                        if not _ISO_DATE.fullmatch(value or ""):
                            continue
                        date_rows += 1
                        if listed:
                            if date_index < 4 or date_index + 3 >= len(row):
                                dropped += 1
                                break
                            name, identifier_raw, office, measure = row[date_index - 4 : date_index]
                            expiry, update, sectors = row[date_index + 1 : date_index + 4]
                            if not name or not identifier_raw:
                                dropped += 1
                                break
                            status = "renewal_update_in_progress" if update.casefold() in {"sì", "si", "yes"} else "listed"
                            records.append(
                                _record(
                                    cfg,
                                    len(records) + 1,
                                    name=name,
                                    office=office,
                                    identifier_raw=identifier_raw,
                                    activities=_activities(sectors),
                                    status=status,
                                    outcome_raw="Aggiornamento in corso" if status == "renewal_update_in_progress" else "",
                                    decision_date=value,
                                    expiry_date=expiry,
                                    primary_date_label="Data provvedimento",
                                    source_fields={"provvedimento": measure, "in_aggiornamento": update},
                                )
                            )
                        else:
                            if date_index < 3 or date_index + 1 >= len(row):
                                dropped += 1
                                break
                            name, identifier_raw, office = row[date_index - 3 : date_index]
                            sectors = row[date_index + 1]
                            if not name or not identifier_raw:
                                dropped += 1
                                break
                            records.append(
                                _record(
                                    cfg,
                                    len(records) + 1,
                                    name=name,
                                    office=office,
                                    identifier_raw=identifier_raw,
                                    activities=_activities(sectors),
                                    status="pending",
                                    outcome_raw="Richiedente iscrizione",
                                    registration_date=value,
                                    primary_date_label="Data registrazione",
                                )
                            )
                        break

    diagnostics = {
        "parser": "bologna_listed" if listed else "bologna_applicants",
        "date_rows": date_rows,
        "public_records": len(records),
        "dropped_date_rows": dropped,
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
    }
    return ParsedBatch(records, diagnostics)


def parse_bologna_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    return _relative_date_rows(path, cfg, listed=True)


def parse_bologna_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    return _relative_date_rows(path, cfg, listed=False)



def _aosta_activities(text: str) -> list[str]:
    """Split only explicit source separators while preserving labels such as I-quater."""
    value = _clean(text)
    if not value:
        return []
    parts = [_clean(item) for item in re.split(r"\s+[–—-]\s+", value) if _clean(item)]
    return parts or [value]


def _status_aosta_applicant(outcome: str) -> str:
    folded = _clean(outcome).casefold()
    if "istruttoria" in folded:
        return "pending"
    if "iscritt" in folded:
        return "listed"
    if "negat" in folded or "dinieg" in folded or "rigett" in folded:
        return "rejected_or_denied"
    if "rinunc" in folded or "cancell" in folded or "revoc" in folded:
        return "cancellation_related"
    return "other_or_unknown"


def parse_aosta_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    records: list[dict[str, Any]] = []
    date_rows = 0
    dropped = 0
    with pdfplumber.open(path) as pdf:
        for _page, row in _table_rows(pdf):
            if len(row) != 8 or not (_DMY_FLEX.fullmatch(row[5] or "") and _DMY_FLEX.fullmatch(row[6] or "")):
                continue
            date_rows += 1
            if not row[0] or not row[3]:
                dropped += 1
                continue
            update = row[7]
            records.append(
                _record(
                    cfg,
                    len(records) + 1,
                    name=row[0],
                    office=row[1],
                    secondary=row[2],
                    identifier_raw=row[3],
                    activities=_aosta_activities(row[4]),
                    status="renewal_update_in_progress" if update else "listed",
                    outcome_raw=update,
                    listing_date=row[5],
                    expiry_date=row[6],
                    primary_date_label="Data iscrizione",
                )
            )
    diagnostics = {
        "parser": "aosta_listed",
        "date_rows": date_rows,
        "public_records": len(records),
        "dropped_date_rows": dropped,
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
    }
    return ParsedBatch(records, diagnostics)


def parse_aosta_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    records: list[dict[str, Any]] = []
    date_rows = 0
    dropped = 0
    with pdfplumber.open(path) as pdf:
        for _page, row in _table_rows(pdf):
            if len(row) != 13 or not _DMY_FLEX.fullmatch(row[9] or ""):
                continue
            date_rows += 1
            if not row[0] or not row[5]:
                dropped += 1
                continue
            outcome = row[12]
            records.append(
                _record(
                    cfg,
                    len(records) + 1,
                    name=row[0],
                    office=row[1],
                    secondary=row[3],
                    identifier_raw=row[5],
                    activities=_aosta_activities(row[6]),
                    status=_status_aosta_applicant(outcome),
                    outcome_raw=outcome,
                    application_date=row[9],
                    primary_date_label="Data presentazione istanza",
                )
            )
    diagnostics = {
        "parser": "aosta_applicants",
        "date_rows": date_rows,
        "public_records": len(records),
        "dropped_date_rows": dropped,
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
    }
    return ParsedBatch(records, diagnostics)


PARSERS: dict[str, Callable[[Path, dict[str, Any]], ParsedBatch]] = {
    "parma_operational": parse_parma,
    "pistoia_listed": parse_pistoia_listed,
    "pistoia_applicants": parse_pistoia_applicants,
    "bologna_listed": parse_bologna_listed,
    "bologna_applicants": parse_bologna_applicants,
    "alessandria_listed": parse_alessandria_listed,
    "alessandria_applicants": parse_alessandria_applicants,
    "aosta_listed": parse_aosta_listed,
    "aosta_applicants": parse_aosta_applicants,
}

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _iso_date, _record

PARSER_VERSION = "1"
_SOURCE_KEY = "forli-cesena-combined"
_AUTHORITY_KEY = "forli-cesena"
_REFERENCE_DATE = "2026-09-11"
_EXPECTED_PAGES = 69
_EXPECTED_RECORDS = 749
_EXPECTED_STATUS_COUNTS = {
    "listed": 401,
    "renewal_update_in_progress": 204,
    "pending": 144,
}
_EXPECTED_ID_KIND_COUNTS = {
    "strict_11_digit": 747,
    "reviewed_10_digit_source_exception": 1,
    "reviewed_blank_identifier_foreign_exception": 1,
}
_EXPECTED_DUPLICATE_STRICT_IDS = {"03690740406": 2, "04581460260": 2}
_EXPECTED_DATED_PROVVEDIMENTO_ROWS = 600
_EXPECTED_CID_ARTIFACT_ROWS = 1
_EXPECTED_SECTIONS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")

_NORMAL_START = re.compile(r"^\s*(\d{11})\s+(.+?)\s*$")
_TEN_DIGIT_EXCEPTION = re.compile(r"^\s*(0543034730)\s+(V8 TRASPORTI\s*&\s*LOGISTICA\s+SRL)\s*$")
_FOREIGN_EXCEPTION = re.compile(r"^\s*(GRUPPO IDRODEMOLIZIONI SRL - SOCIETA['’] ESTERA)\s*$")
_STATUS = re.compile(r"\b(IN\s+AGGIORNAMENTO|AVVIO\s+ISTRUTTORIA)\b", re.I)
_PROVVEDIMENTO = re.compile(
    r"^Provv\.\s*n\.\s*(?P<number>.*?)\s+del\s*(?P<decision>.*?)\s+Scadenza\s*(?P<expiry>.*?)\s*$",
    re.I,
)
_STATUS_DATE = re.compile(r"^(?:DAL\s+|AL\s+)?\d{2}/\d{2}/\d{4}$", re.I)
_SECTION_LINE = re.compile(r"^Sezioni?\.?:\s*(?P<sections>.+?)\s*$", re.I)
_PAGE_FOOTER = re.compile(r"^venerd[iì]\s+11\s+settembre\s+2026\s+Pagina\s+\d+\s+di\s+69$", re.I)

_REVIEWED_CID_ARTIFACT = {
    ("02161921008", "(cid:9)AQUAMET S.R.L. (EX AQUAMET SPA)"): "AQUAMET S.R.L. (EX AQUAMET SPA)",
}


def _validate_cfg(cfg: dict[str, Any]) -> None:
    if cfg.get("source_key") != _SOURCE_KEY:
        raise RuntimeError(f"Forli-Cesena parser/source mismatch: {cfg.get('source_key')!r} != {_SOURCE_KEY!r}")
    if cfg.get("authority_key") != _AUTHORITY_KEY:
        raise RuntimeError("Forli-Cesena parser bound to a non-Forli-Cesena authority")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(
            f"Forli-Cesena reference-date drift: {cfg.get('reference_date')!r} != {_REFERENCE_DATE!r}"
        )


def _record_start(line: str) -> tuple[str, str, str] | None:
    if match := _NORMAL_START.match(line):
        return match.group(1), match.group(2).strip(), "strict_11_digit"
    if match := _TEN_DIGIT_EXCEPTION.match(line):
        return match.group(1), match.group(2).strip(), "reviewed_10_digit_source_exception"
    if match := _FOREIGN_EXCEPTION.match(line):
        return "", match.group(1).strip(), "reviewed_blank_identifier_foreign_exception"
    return None


def _clean_name(identifier_raw: str, name_raw: str) -> tuple[str, bool]:
    reviewed = _REVIEWED_CID_ARTIFACT.get((identifier_raw, name_raw))
    if reviewed is not None:
        return reviewed, True
    if "(cid:" in name_raw.casefold():
        raise RuntimeError(f"Forli-Cesena unreviewed CID extraction artefact in company name: {name_raw!r}")
    return name_raw, False


def _parse_sections(line: str) -> list[str]:
    match = _SECTION_LINE.fullmatch(_clean(line))
    if not match:
        raise RuntimeError(f"Forli-Cesena malformed source section line: {line!r}")
    tokens = tuple(re.findall(r"\b(?:VIII|VII|III|VI|IV|IX|II|V|X|I)\b", match.group("sections")))
    if tokens != _EXPECTED_SECTIONS:
        raise RuntimeError(f"Forli-Cesena section signature drift: {tokens!r} != {_EXPECTED_SECTIONS!r}")
    return [f"Sezione {token}" for token in tokens]


def _parse_provvedimento(line: str, explicit_status: str) -> tuple[str, str, str, str]:
    before, marker, after = line.partition("Provv.")
    if not marker:
        raise RuntimeError(f"Forli-Cesena record without Provv. marker: {line!r}")
    street = _clean(before)
    if not street and explicit_status != "AVVIO ISTRUTTORIA":
        raise RuntimeError(f"Forli-Cesena non-pending row without an address detail: {line!r}")
    tail = "Provv." + after
    tail = _STATUS.sub("", tail).rstrip()
    match = _PROVVEDIMENTO.fullmatch(tail)
    if not match:
        raise RuntimeError(f"Forli-Cesena malformed provvedimento fields: {line!r}")
    number = _clean(match.group("number"))
    decision_raw = _clean(match.group("decision"))
    expiry_raw = _clean(match.group("expiry"))
    decision = _iso_date(decision_raw)
    expiry = _iso_date(expiry_raw)
    if decision_raw and not decision:
        raise RuntimeError(f"Forli-Cesena malformed decision date: {decision_raw!r}")
    if expiry_raw and not expiry:
        raise RuntimeError(f"Forli-Cesena malformed expiry date: {expiry_raw!r}")
    if bool(decision) != bool(expiry):
        raise RuntimeError(
            f"Forli-Cesena asymmetric provvedimento dates: decision={decision_raw!r}, expiry={expiry_raw!r}"
        )
    if explicit_status == "AVVIO ISTRUTTORIA" and (number or decision or expiry):
        raise RuntimeError("Forli-Cesena applicant row unexpectedly carries populated provvedimento fields")
    return street, number, decision, expiry


def _status_from_block(text: str) -> tuple[str, str]:
    tokens = [re.sub(r"\s+", " ", match.group(1).upper()) for match in _STATUS.finditer(text)]
    if len(tokens) > 1:
        raise RuntimeError(f"Forli-Cesena record contains multiple current-status markers: {tokens!r}")
    explicit = tokens[0] if tokens else ""
    if explicit == "AVVIO ISTRUTTORIA":
        return "pending", explicit
    if explicit == "IN AGGIORNAMENTO":
        return "renewal_update_in_progress", explicit
    return "listed", ""


def _parse_record_block(
    page_number: int,
    page_record_number: int,
    identifier_raw: str,
    name_raw: str,
    id_kind: str,
    raw_lines: list[str],
    cfg: dict[str, Any],
    ordinal: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    lines = [line.rstrip() for line in raw_lines if line.strip()]
    if not lines:
        raise RuntimeError("Forli-Cesena empty logical record block")
    body = "\n".join(lines)
    status, explicit_status = _status_from_block(body)

    provv_lines = [line for line in lines if "Provv." in line and "Scadenza" in line]
    section_lines = [line for line in lines if re.search(r"Sezion", line, re.I)]
    if len(provv_lines) != 1:
        raise RuntimeError(
            f"Forli-Cesena p{page_number}:b{page_record_number} expected one provvedimento line, got {len(provv_lines)}"
        )
    if len(section_lines) != 1:
        raise RuntimeError(
            f"Forli-Cesena p{page_number}:b{page_record_number} expected one section line, got {len(section_lines)}"
        )

    street, registration_number, decision_date, expiry_date = _parse_provvedimento(
        provv_lines[0], explicit_status
    )
    sections = _parse_sections(section_lines[0])

    status_date_lines: list[str] = []
    locality_candidates: list[str] = []
    for line in lines[1:]:
        cleaned = _clean(line)
        if line == provv_lines[0] or line == section_lines[0] or _PAGE_FOOTER.fullmatch(cleaned):
            continue
        if _STATUS_DATE.fullmatch(cleaned):
            status_date_lines.append(cleaned)
            continue
        locality_candidates.append(cleaned)
    if len(status_date_lines) > 1:
        raise RuntimeError(
            f"Forli-Cesena p{page_number}:b{page_record_number} multiple status-date lines: {status_date_lines!r}"
        )
    if len(locality_candidates) != 1:
        raise RuntimeError(
            f"Forli-Cesena p{page_number}:b{page_record_number} locality layout drift: {locality_candidates!r}"
        )
    locality = locality_candidates[0]

    if status == "listed" and status_date_lines:
        raise RuntimeError(
            f"Forli-Cesena listed row unexpectedly carries a standalone status date: {status_date_lines!r}"
        )
    if status == "listed" and not (registration_number and decision_date and expiry_date):
        raise RuntimeError("Forli-Cesena listed row lacks populated provvedimento fields")

    name, cid_artifact_reconciled = _clean_name(identifier_raw, name_raw)
    office = _clean(" ".join(part for part in (street, locality) if part))
    source_locator = f"p{page_number}:b{page_record_number}"
    source_fields: dict[str, Any] = {
        "sections": sections,
        "address_detail": street,
        "locality": locality,
        "source_locator": source_locator,
        "transcription_text": " | ".join(_clean(line) for line in lines),
    }
    if explicit_status:
        source_fields["status_marker"] = explicit_status
    if registration_number:
        source_fields["registration_number"] = registration_number
    if decision_date:
        source_fields["decision_date"] = decision_date
    if expiry_date:
        source_fields["expiration_date"] = expiry_date

    record = _record(
        cfg,
        ordinal,
        name=name,
        office=office,
        identifier_raw=identifier_raw,
        activities=sections,
        status=status,
        outcome_raw=explicit_status,
        decision_date=decision_date,
        expiry_date=expiry_date,
        primary_date_label="Data provvedimento" if decision_date else "",
        source_fields=source_fields,
    )
    diagnostics = {
        "id_kind": id_kind,
        "cid_artifact_reconciled": cid_artifact_reconciled,
        "has_status_date": bool(status_date_lines),
        "has_dated_provvedimento": bool(decision_date and expiry_date),
    }
    return record, diagnostics


def parse_forli_cesena_combined(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg)
    records: list[dict[str, Any]] = []
    id_kinds: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    strict_ids: Counter[str] = Counter()
    cid_artifact_rows = 0
    dated_provvedimento_rows = 0
    status_date_rows = 0
    page_record_counts: list[int] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_PAGES:
            raise RuntimeError(f"Forli-Cesena page-count drift: {len(pdf.pages)} != {_EXPECTED_PAGES}")
        ordinal = 0
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=True, x_tolerance=1, y_tolerance=3) or ""
            page_lines = text.splitlines()
            starts: list[tuple[int, str, str, str]] = []
            for line_number, line in enumerate(page_lines):
                start = _record_start(line)
                if start is not None:
                    starts.append((line_number, *start))
            page_record_counts.append(len(starts))
            for page_record_number, item in enumerate(starts, start=1):
                line_number, identifier_raw, name_raw, id_kind = item
                end = starts[page_record_number][0] if page_record_number < len(starts) else len(page_lines)
                ordinal += 1
                record, diag = _parse_record_block(
                    page_number,
                    page_record_number,
                    identifier_raw,
                    name_raw,
                    id_kind,
                    page_lines[line_number:end],
                    cfg,
                    ordinal,
                )
                records.append(record)
                id_kinds[id_kind] += 1
                statuses[record["source_status"]] += 1
                if id_kind == "strict_11_digit":
                    strict_ids[identifier_raw] += 1
                cid_artifact_rows += int(diag["cid_artifact_reconciled"])
                dated_provvedimento_rows += int(diag["has_dated_provvedimento"])
                status_date_rows += int(diag["has_status_date"])

    if len(records) != _EXPECTED_RECORDS:
        raise RuntimeError(f"Forli-Cesena record-count drift: {len(records)} != {_EXPECTED_RECORDS}")
    if dict(statuses) != _EXPECTED_STATUS_COUNTS:
        raise RuntimeError(f"Forli-Cesena status-count drift: {dict(statuses)!r} != {_EXPECTED_STATUS_COUNTS!r}")
    if dict(id_kinds) != _EXPECTED_ID_KIND_COUNTS:
        raise RuntimeError(f"Forli-Cesena identifier-kind drift: {dict(id_kinds)!r} != {_EXPECTED_ID_KIND_COUNTS!r}")
    duplicates = {identifier: count for identifier, count in strict_ids.items() if count > 1}
    if duplicates != _EXPECTED_DUPLICATE_STRICT_IDS:
        raise RuntimeError(
            f"Forli-Cesena duplicate strict-identifier drift: {duplicates!r} != {_EXPECTED_DUPLICATE_STRICT_IDS!r}"
        )
    if dated_provvedimento_rows != _EXPECTED_DATED_PROVVEDIMENTO_ROWS:
        raise RuntimeError(
            f"Forli-Cesena dated-provvedimento drift: {dated_provvedimento_rows} != {_EXPECTED_DATED_PROVVEDIMENTO_ROWS}"
        )
    if cid_artifact_rows != _EXPECTED_CID_ARTIFACT_ROWS:
        raise RuntimeError(
            f"Forli-Cesena reviewed CID-artifact drift: {cid_artifact_rows} != {_EXPECTED_CID_ARTIFACT_ROWS}"
        )

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "forli_cesena_combined",
            "parser_version": PARSER_VERSION,
            "pages": _EXPECTED_PAGES,
            "records": len(records),
            "status_counts": dict(statuses),
            "identifier_kind_counts": dict(id_kinds),
            "duplicate_strict_identifiers": duplicates,
            "dated_provvedimento_rows": dated_provvedimento_rows,
            "status_date_rows": status_date_rows,
            "reviewed_cid_artifact_rows": cid_artifact_rows,
            "page_record_counts": page_record_counts,
        },
    )

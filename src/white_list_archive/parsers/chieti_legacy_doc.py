from __future__ import annotations

import html
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-18"
_EXPECTED_ACTIVITY_LABELS = (
    "AUTOTRASPORTO PER CONTO TERZI",
    "CONFEZIONAMENTO, FORNITURA E TRASPORTO DI CALCESTRUZZO E BITUME",
    "ESTRAZIONE, FORNITURA E TRASPORTO DI TERRA E MATERIALI INERTI",
    "FORNITURA DI FERRO LAVORATO",
    "GUARDIANIA AI CANTIERI",
    "NOLI A CALDO",
    "NOLI A FREDDO DI MACCHINARI",
    "SERVIZI AMBIENTALI, COMPRESE LE ATTIVITA’ DI RACCOLTA, TRASPORTO NAZIONALE E TRANSFRONTALIERO, ANCHE PER CONTO DI TERZI, DI TRATTAMENTO E SMALTIMENTO DI RIFIUTI, NONCHE’ LE ATTIVITA’ DI RISANAMENTO E DI BONIFICA E GLI ALTRI SERVIZI CONNESSI ALLA GESTIONE DEI RIFIUTI",
    "SERVIZI FUNERARI E CIMITERIALI",
    "RISTORAZIONE, GESTIONE DELLE MENSE E CATERING",
)
_EXPECTED_LISTED_SECTOR_ROWS = 1352
_EXPECTED_LISTED_RECORDS = 759
_EXPECTED_LISTED_STATUS_COUNTS = Counter({
    "listed": 544,
    "renewal_update_in_progress": 204,
    "expired_observed": 10,
    "cancellation_related": 1,
})
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 731
_EXPECTED_APPLICANT_ROWS = 177
_EXPECTED_APPLICANT_STATUS_COUNTS = Counter({
    "pending": 169,
    "other_or_unknown": 7,
    "rejected_or_denied": 1,
})
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 173
_EXPECTED_APPLICANT_OUTCOMES = Counter({
    "IN ISTRUTTORIA": 157,
    "": 8,
    "IN ISTRUTTTORIA": 2,
    "IN ISTRITTORIA": 2,
    "Istanza archiviata a seguito trasferimento sede legale a Milano": 1,
    "Istanza archiviata con D.P. 50135 del 29/06/2021": 1,
    "Istanza archiviata con D.P. 6121 del 21/01/2023": 1,
    "Istanza archiviata con D.P. n. 88755 del 5 novembre 2022": 1,
    "Istanza archiviata con D.P. 6120 Del 21/01/2023": 1,
    "Istanza archiviata (cfr.prefettizia 73452 del 14 settembre 2022 a seguito rinuncia interesse società)": 1,
    "Istanza respinta a seguito di informativa interdittiva ex art. 84 commi 3 e 4 del D.L.vo n. 159/2011 e succ. modifiche e integrazioni, adottata con provvedimento prefettizio n. 79847 del 16 settembre 2024": 1,
    "Istruttoria trasferita per competenza alla Prefettura di Pescara, a seguito trasferimento di sede, l’11 dicembre 2023": 1,
})
_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_STRICT_VAT = re.compile(r"(?<!\d)(\d{11})(?!\d)")
_STRICT_CF = re.compile(r"(?<![A-Z0-9])([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])(?![A-Z0-9])", re.I)


def _antiword_docbook(path: Path) -> str:
    executable = shutil.which("antiword")
    if executable is None:
        raise RuntimeError("antiword is required to parse the reviewed Chieti legacy Word sources")
    process = subprocess.run(
        [executable, "-x", "db", str(path)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode:
        raise RuntimeError(
            f"antiword failed for Chieti source {path.name}: "
            f"{process.stderr.decode('utf-8', 'replace').strip()}"
        )
    return process.stdout.decode("utf-8", "replace")


def _source_identifiers(raw: str) -> list[str]:
    values: list[str] = []
    for pattern in (_STRICT_VAT, _STRICT_CF):
        for match in pattern.finditer(raw):
            value = match.group(1).upper()
            if value not in values:
                values.append(value)
    return values


def _source_date(raw: str) -> str:
    value = _clean(raw).casefold().replace("º", "°")
    match = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", value)
    if match is not None:
        day, month, year = map(int, match.groups())
    else:
        match = re.fullmatch(r"(\d{1,2})°?\s+([a-zàèéìòù]+)\s+(\d{4})", value)
        if match is None or match.group(2) not in _MONTHS:
            return ""
        day = int(match.group(1))
        month = _MONTHS[match.group(2)]
        year = int(match.group(3))
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _listed_status(note: str) -> str:
    folded = _clean(note).casefold()
    if "iscrizione scaduta" in folded:
        return "expired_observed"
    if "cancellazione" in folded:
        return "cancellation_related"
    if "istrutt" in folded or (("richiest" in folded or "depositata" in folded) and "rinnovo" in folded):
        return "renewal_update_in_progress"
    return "listed"


def _applicant_status(outcome: str) -> str:
    folded = _clean(outcome).casefold()
    if "trasferita per competenza" in folded or "archiviat" in folded:
        return "other_or_unknown"
    if "respinta" in folded or "interditt" in folded:
        return "rejected_or_denied"
    if not folded or "istrutt" in folded or "istritt" in folded:
        return "pending"
    raise RuntimeError(f"chieti-applicants: unreviewed source outcome: {outcome!r}")


def _listed_rows(docbook: str) -> list[tuple[str, list[str]]]:
    xml = re.sub(r"<!DOCTYPE book PUBLIC.*?docbookx\.dtd\">\s*", "", docbook, flags=re.S)
    root = ET.fromstring(xml)
    chapters = [chapter for chapter in root.findall(".//chapter") if chapter.findall(".//informaltable")]
    if len(chapters) != 1:
        raise RuntimeError(f"chieti-listed: expected one table-bearing chapter, got {len(chapters)}")
    output: list[tuple[str, list[str]]] = []
    labels: list[str] = []
    activity = ""
    for para in chapters[0].findall("./para"):
        table = para.find(".//informaltable")
        if table is None:
            text = _clean("".join(para.itertext()))
            if not text or text == "WHITE LIST" or text.startswith("Prefettura") or "Ufficio Territoriale" in text or "Area 1" in text:
                continue
            activity = re.sub(r"^ATTIVITA[’']:\s*", "", text, flags=re.I)
            labels.append(activity)
            continue
        if not activity:
            raise RuntimeError("chieti-listed: source table appeared before an activity heading")
        groups = table.findall(".//tgroup")
        if len(groups) != 1 or groups[0].get("cols") != "6":
            raise RuntimeError("chieti-listed: table column-count drift")
        for row in table.findall(".//row"):
            cells = [_clean("".join(entry.itertext())) for entry in row.findall("./entry")]
            if len(cells) != 6:
                raise RuntimeError(f"chieti-listed: row column-count drift: {len(cells)}")
            if cells[0].casefold().startswith("ragione sociale"):
                continue
            if any(cells):
                if not cells[2]:
                    raise RuntimeError(f"chieti-listed: missing identifier field in reviewed row: {cells!r}")
                if not cells[0] and cells[2] != "c.f.DSNLSS80H05141P,p.IVA02246800698":
                    raise RuntimeError(f"chieti-listed: unreviewed blank company name: {cells!r}")
                output.append((activity, cells))
    if tuple(labels) != _EXPECTED_ACTIVITY_LABELS:
        raise RuntimeError(f"chieti-listed: activity-heading drift: {labels!r}")
    if len(output) != _EXPECTED_LISTED_SECTOR_ROWS:
        raise RuntimeError(
            f"chieti-listed: sector-row denominator drift; expected {_EXPECTED_LISTED_SECTOR_ROWS}, got {len(output)}"
        )
    return output


def _applicant_rows(docbook: str) -> list[list[str]]:
    paragraphs = re.findall(r"<para>(.*?)</para>", docbook, flags=re.S)
    candidates = [value for value in paragraphs if "\x07" in value]
    if len(candidates) != 1:
        raise RuntimeError(f"chieti-applicants: expected one BEL-delimited table, got {len(candidates)}")
    raw = html.unescape(re.sub(r"<[^>]+>", "", candidates[0]))
    tokens = [_clean(value) for value in raw.split("\x07")]
    if tokens and tokens[-1] == "" and (len(tokens) - 1 - 8) % 8 == 0:
        tokens.pop()
    expected_header = [
        "Ragione Sociale",
        "Sede legale",
        "Sede secondaria con rappresentanza stabile in Italia",
        "Codice fiscale Partita IVA",
        "Attività per cui è richiesta l’iscrizione",
        "Data di presentazione dell’istanza",
        "Esito",
        "",
    ]
    if tokens[:8] != expected_header or (len(tokens) - 8) % 8:
        raise RuntimeError("chieti-applicants: table header/cardinality drift")
    rows: list[list[str]] = []
    for offset in range(8, len(tokens), 8):
        block = tokens[offset:offset + 8]
        if len(block) != 8 or block[-1]:
            raise RuntimeError(f"chieti-applicants: row-separator drift at block {offset // 8}")
        row = block[:7]
        if not row[0]:
            raise RuntimeError(f"chieti-applicants: missing company name at block {offset // 8}")
        rows.append(row)
    if len(rows) != _EXPECTED_APPLICANT_ROWS:
        raise RuntimeError(
            f"chieti-applicants: row denominator drift; expected {_EXPECTED_APPLICANT_ROWS}, got {len(rows)}"
        )
    outcomes = Counter(row[6] for row in rows)
    if outcomes != _EXPECTED_APPLICANT_OUTCOMES:
        raise RuntimeError(f"chieti-applicants: outcome-text drift: {dict(outcomes)!r}")
    return rows


def parse_chieti_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    sector_rows = _listed_rows(_antiword_docbook(path))
    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for activity, row in sector_rows:
        key = tuple(row)
        group = grouped.setdefault(key, {"row": row, "activities": []})
        if activity not in group["activities"]:
            group["activities"].append(activity)
    if len(grouped) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(
            f"{cfg['source_key']}: listed observation denominator drift; expected {_EXPECTED_LISTED_RECORDS}, got {len(grouped)}"
        )

    records: list[dict[str, Any]] = []
    for group in grouped.values():
        row = group["row"]
        status = _listed_status(row[5])
        record = _record(
            cfg,
            len(records) + 1,
            name=row[0],
            office=row[1],
            identifier_raw=row[2],
            activities=list(group["activities"]),
            status=status,
            outcome_raw=row[5],
            listing_date=_source_date(row[3]),
            expiry_date=_source_date(row[4]),
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": list(group["activities"]),
                "listing_date_raw_variants": [row[3]] if row[3] else [],
                "expiry_date_raw_variants": [row[4]] if row[4] else [],
                "in_aggiornamento": row[5] if status == "renewal_update_in_progress" else "",
                "notes": [row[5]] if row[5] and status != "renewal_update_in_progress" else [],
            },
        )
        record["identifiers"] = _source_identifiers(row[2])
        records.append(record)

    status_counts = Counter(record["source_status"] for record in records)
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: listed status drift: {dict(status_counts)!r}")
    coverage = sum(bool(record["identifiers"]) for record in records)
    if coverage != _EXPECTED_LISTED_IDENTIFIER_COVERAGE:
        raise RuntimeError(f"{cfg['source_key']}: listed identifier-coverage drift: {coverage}")
    return ParsedBatch(records, {
        "parser": "chieti_legacy_listed",
        "sector_rows": len(sector_rows),
        "public_records": len(records),
        "status_counts": dict(status_counts),
        "identifier_coverage": coverage,
        "raw_only_identifier_records": len(records) - coverage,
        "malformed_listing_date_records": sum(not record["observed_listing_date"] for record in records),
        "malformed_expiry_date_records": sum(not record["observed_expiry_date"] for record in records),
    })


def parse_chieti_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    rows = _applicant_rows(_antiword_docbook(path))
    records: list[dict[str, Any]] = []
    for row in rows:
        status = _applicant_status(row[6])
        record = _record(
            cfg,
            len(records) + 1,
            name=row[0],
            office=row[1],
            secondary=row[2],
            identifier_raw=row[3],
            activities=[row[4]] if row[4] else [],
            status=status,
            outcome_raw=row[6],
            application_date=_source_date(row[5]),
            primary_date_label="Data presentazione istanza",
            source_fields={
                "requested_activities_source": row[4],
                "application_date_raw_variants": [row[5]] if row[5] else [],
                "notes": [row[6]] if row[6] else [],
            },
        )
        record["identifiers"] = _source_identifiers(row[3])
        records.append(record)

    status_counts = Counter(record["source_status"] for record in records)
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: applicant status drift: {dict(status_counts)!r}")
    coverage = sum(bool(record["identifiers"]) for record in records)
    if coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE:
        raise RuntimeError(f"{cfg['source_key']}: applicant identifier-coverage drift: {coverage}")
    return ParsedBatch(records, {
        "parser": "chieti_legacy_applicants",
        "public_records": len(records),
        "status_counts": dict(status_counts),
        "outcome_counts": dict(Counter(row[6] for row in rows)),
        "identifier_coverage": coverage,
        "raw_only_identifier_records": len(records) - coverage,
        "malformed_or_missing_application_date_records": sum(not record["application_date"] for record in records),
    })


PARSERS = {
    "chieti_legacy_listed": parse_chieti_listed,
    "chieti_legacy_applicants": parse_chieti_applicants,
}

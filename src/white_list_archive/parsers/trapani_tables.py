from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _record

_LISTED_PAGE_COUNT = 41
_APPLICANT_PAGE_COUNT = 44
_PAGE_GEOMETRY = (841.92, 595.32)
_LISTED_TABLE_COUNTS = [0,1,1,1,1,1,2,1,1,1,1,1,1,1,1,1,1,2,1,2,1,1,1,1,1,1,1,2,1,1,1,1,2,1,1,1,1,1,1,1,0]
_APPLICANT_ROW_COUNTS = [3,9,4,3,2,8,8,6,7,6,7,2,5,7,1,4,1,8,7,4,6,4,6,5,11,5,4,5,6,4,6,7,3,1,4,8,3,5,3,4,6,3,7,4]
_EXPECTED_SECTIONS = tuple(f"Sezione {value}" for value in ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"))
_ALLOWED_UPDATE_MARKERS = {"", "In aggiornamento per rinnovo", "In aggiornamento", "*", "*-"}
_ALLOWED_APPLICANT_OUTCOMES = {"In istruttoria", "In Istruttoria"}
_ID_RE = re.compile(r"^(?:\d{11}|[A-Za-z0-9]{16})$")
_DATE_RE = re.compile(r"^(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})$")
_ROMAN = {value: index for index, value in enumerate(("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"), 1)}

_LISTED_CONTINUATIONS = {
    (15, 1, 1): {
        "row": ["SILVESTRO", "", "", "", "", "", "per rinnovo"],
        "previous": {"page": 14, "name": "IMPRESA EDILE DI MANGANO", "identifier": "02249310810", "update_raw": "In aggiornamento"},
        "name": "IMPRESA EDILE DI MANGANO SILVESTRO",
        "update_raw": "In aggiornamento per rinnovo",
    },
    (18, 1, 1): {
        "row": ["MASSIMILIANO S. N.C.", "", "", "", "", "", ""],
        "previous": {"page": 17, "name": "TRIVELLAZIONI AMATO DI AMATO BALDASSARE, COSIMO E", "identifier": "02375070816", "update_raw": ""},
        "name": "TRIVELLAZIONI AMATO DI AMATO BALDASSARE, COSIMO E MASSIMILIANO S. N.C.",
        "update_raw": "",
    },
    (23, 1, 1): {
        "row": ["", "", "", "", "", "", "per rinnovo"],
        "previous": {"page": 22, "name": "EDIL AMBIENTE S.R.L.", "identifier": "02381330816", "update_raw": "In aggiornamento"},
        "name": "EDIL AMBIENTE S.R.L.",
        "update_raw": "In aggiornamento per rinnovo",
    },
    (25, 1, 1): {
        "row": ["VITO ELIO", "", "", "", "", "", ""],
        "previous": {"page": 24, "name": "IMPRESA EDILE STRADALE DI MILOTTA", "identifier": "MLTVTL65L21A176H", "update_raw": ""},
        "name": "IMPRESA EDILE STRADALE DI MILOTTA VITO ELIO",
        "update_raw": "",
    },
    (26, 1, 1): {
        "row": ["VINCENZA MARIA & C.", "", "", "", "", "", ""],
        "previous": {"page": 25, "name": "NUOVA ESIR S.N.C. DI DI GIORGI", "identifier": "01371540814", "update_raw": ""},
        "name": "NUOVA ESIR S.N.C. DI DI GIORGI VINCENZA MARIA & C.",
        "update_raw": "",
    },
    (28, 1, 1): {
        "row": ["", "", "", "", "", "", "per rinnovo"],
        "previous": {"page": 27, "name": "WEDRILL S.R.L.", "identifier": "02836190815", "update_raw": "In aggiornamento"},
        "name": "WEDRILL S.R.L.",
        "update_raw": "In aggiornamento per rinnovo",
    },
    (30, 1, 1): {
        "row": ["ALESSANDRO MILAZZO & C.", "", "", "", "", "", "per rinnovo"],
        "previous": {"page": 29, "name": "DE SIMONE & MILAZZO S.A.S. DI", "identifier": "00060160819", "update_raw": "In aggiornamento"},
        "name": "DE SIMONE & MILAZZO S.A.S. DI ALESSANDRO MILAZZO & C.",
        "update_raw": "In aggiornamento per rinnovo",
    },
    (31, 1, 1): {
        "row": ["", "", "", "", "", "", "per rinnovo"],
        "previous": {"page": 30, "name": "GUDDEMI S.r.l.", "identifier": "02264160819", "update_raw": "In aggiornamento"},
        "name": "GUDDEMI S.r.l.",
        "update_raw": "In aggiornamento per rinnovo",
    },
    (36, 1, 1): {
        "row": ["RESPONSABILITA' LIMITATA SEMPLIFICATA", "", "", "", "", "", ""],
        "previous": {"page": 35, "name": "NUOVA RISTO - SOCIETA' A", "identifier": "02850410818", "update_raw": ""},
        "name": "NUOVA RISTO - SOCIETA' A RESPONSABILITA' LIMITATA SEMPLIFICATA",
        "update_raw": "",
    },
    (39, 1, 1): {
        "row": ["SEMPLIFICATA", "", "", "", "", "", ""],
        "previous": {"page": 38, "name": "ECOPLASTIK - SOCIETA' A RESPONSABILITA' LIMITATA", "identifier": "02605070818", "update_raw": "In aggiornamento per rinnovo"},
        "name": "ECOPLASTIK - SOCIETA' A RESPONSABILITA' LIMITATA SEMPLIFICATA",
        "update_raw": "In aggiornamento per rinnovo",
    },
}
_LISTED_HEADER_FRAGMENT = (
    (34, 1, 1),
    ["", "", "CON RAPPRESENTANZA STABILE IN ITALIA", "PARTITA IVA", "ISCRIZIONE", "SCADENZA ISCRIZIONE", "IN CORSO"],
)
_LISTED_JUDICIAL_ADMINISTRATION_EXPIRY = "In amministrazio ne giudiziaria e fermo restando fino al permanere della stessa"
_LISTED_NAME_VARIANT_NORMALISATIONS = {
    "02483290819": {
        "source_variants": [
            "STRADE E SERVIZI S.R.L. UNIPERSONALE",
            "STRADE E SERVIZI S.R.L.UNIPERSONALE",
        ],
        "canonical": "STRADE E SERVIZI S.R.L. UNIPERSONALE",
    },
    "02483280810": {
        "source_variants": [
            "GIKA S.R.L.",
            "GIKA S.r.l.",
        ],
        "canonical": "GIKA S.R.L.",
    },
}

_LISTED_OFFICE_VARIANT_NORMALISATIONS = {
    "GCCNDR95R07D423B": {
        "source_variants": ["SA LEMI", "SALEMI"],
        "canonical": "SALEMI",
    },
}

_APPLICANT_CONTINUATIONS = {
    (3, 1, 1): {
        "row": ["", "", "", "", "-Servizi funerari e cimiteriali", "", ""],
        "previous": {"page": 2, "name": "AMG TECH S.R.L.", "identifier": "02303880815"},
    },
    (5, 1, 1): {
        "row": ["", "", "", "", "attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 4, "name": "AUTOSPURGHI LICARI S.R.L.", "identifier": "02423440813"},
    },
    (6, 1, 1): {
        "row": ["", "", "", "", "attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 5, "name": "AUTOSPURGO PETROSINO DI BIONDO GIUSEPPE", "identifier": "BNDGPP84T14E974C"},
    },
    (7, 1, 1): {
        "row": ["", "", "", "", "-Fornitura di ferro lavorato", "", ""],
        "previous": {"page": 6, "name": "BENENATI BERNARDO", "identifier": "BNNBNR63R14A176Z"},
    },
    (11, 1, 1): {
        "row": ["", "", "", "", "catering", "", ""],
        "previous": {"page": 10, "name": "CIPPONERI LUIGI", "identifier": "CPPLGU81T03G208K"},
    },
    (12, 1, 1): {
        "row": ["", "", "", "", "attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 11, "name": "DA.SCA. S.N.C. DI SCARAMUZZO O. & C. (in Amministrazione Giudiziaria)", "identifier": "01398850816"},
    },
    (15, 1, 1): {
        "row": ["", "", "", "", "-Servizi ambientali, comprese le attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 14, "name": "EUROAMBIENTE S.R.L.", "identifier": "06547530821"},
    },
    (16, 1, 1): {
        "row": ["", "", "", "", "bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 15, "name": "EVOLA VITO", "identifier": "VLEVTI60M11F061P"},
    },
    (17, 1, 1): {
        "row": ["", "GOLFO", "", "", "-Nolo a freddo di macchinari -Autotrasporti per conto terzi -Servizi ambientali, comprese le attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 16, "name": "FIAM S.R.L.", "identifier": "02312540814"},
    },
    (18, 1, 1): {
        "row": ["", "", "", "", "bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 17, "name": "FILIPPO IMPASTATO & FIGLIO S.N.C.", "identifier": "01578680819"},
    },
    (23, 1, 1): {
        "row": ["", "", "", "", "smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 22, "name": "LA MARMORA GIUSEPPE", "identifier": "LMRGPP74T06C286Y"},
    },
    (26, 1, 1): {
        "row": ["", "", "", "", "terra e materiali inerti", "", ""],
        "previous": {"page": 25, "name": "MICRON DI PIAZZA DOMENICO", "identifier": "PZZDNC81T24L331M"},
    },
    (30, 1, 1): {
        "row": ["", "", "", "", "attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 29, "name": "PANTEL SERVICE S.R.L.", "identifier": "02753100813"},
    },
    (31, 1, 1): {
        "row": ["FILINGERI DI VITO CARLO FILINGERI & C. S.A.S.", "", "", "", "catering", "", ""],
        "previous": {"page": 30, "name": "PASTICCERIA CIOCCOLATTANDO VITO", "identifier": "02883270817"},
    },
    (33, 1, 1): {
        "row": ["", "", "", "", "terra e materiali inerti -Noli a freddo di macchinari", "", ""],
        "previous": {"page": 32, "name": "R.L.G. MONTAGGI S.R.L.", "identifier": "02840470815"},
    },
    (34, 1, 1): {
        "row": ["", "", "", "", "conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 33, "name": "REAM S.R.L.", "identifier": "02854920812"},
    },
    (35, 1, 1): {
        "row": ["", "", "", "", "attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 34, "name": "RENDA S.R.L.", "identifier": "02520400819"},
    },
    (37, 1, 1): {
        "row": ["", "", "", "", "-Autotrasporti per conto di terzi -Servizi ambientali, comprese le attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 36, "name": "SCAME S.R.L.", "identifier": "02281660817"},
    },
    (39, 1, 1): {
        "row": ["", "", "", "", "-Fornitura ferro lavorato -Noli a caldo -Autotrasporto per conto terzi -Servizi ambientali, comprese le attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 38, "name": "SELEMA S.R.L.", "identifier": "02582990814"},
    },
    (40, 1, 1): {
        "row": ["", "", "", "", "attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 39, "name": "SICILSPURGO S.N.C. DI MILAZZO VITO E C.", "identifier": "01615680814"},
    },
    (41, 1, 1): {
        "row": ["", "", "", "", "-Noli a caldo", "", ""],
        "previous": {"page": 40, "name": "SIRTEC S.R.L.", "identifier": "02060960818"},
    },
    (42, 1, 1): {
        "row": ["", "", "", "", "-Autotrasporti conto di terzi", "", ""],
        "previous": {"page": 41, "name": "TRAPANI SCAVI S.R.L.", "identifier": "02696620810"},
    },
    (44, 1, 1): {
        "row": ["SOCIETA' A RESPONSABILITA'LIMITATA", "", "", "", "- Noli a freddo di macchinari - Noli a caldo", "", ""],
        "previous": {"page": 43, "name": "VINCENZO EVOLA CANTIERI MAZARA", "identifier": "02810670816"},
    },
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def _ordered_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _strict_date(value: str) -> str:
    """Parse source dates without repairing digits or truncated years."""
    value = _clean(value)
    match = _DATE_RE.fullmatch(value)
    if match is None:
        return ""
    day, month, year = map(int, match.groups())
    try:
        parsed = datetime(year, month, day)
    except ValueError:
        return ""
    return parsed.strftime("%d/%m/%Y")


def _section_headings(page: Any) -> list[tuple[float, str]]:
    words = page.extract_words() or []
    headings: list[tuple[float, str]] = []
    for index, word in enumerate(words[:-1]):
        if _clean(word.get("text")).casefold() != "sezione":
            continue
        roman = re.sub(r"[^IVX]", "", _clean(words[index + 1].get("text")).upper())
        if roman in _ROMAN:
            headings.append((float(word.get("top", 0.0)), f"Sezione {roman}"))
    unique: list[tuple[float, str]] = []
    for top, section in sorted(headings):
        if not unique or section != unique[-1][1] or abs(top - unique[-1][0]) > 2:
            unique.append((top, section))
    return unique


def _section_for_table(current: str, headings: list[tuple[float, str]], table_top: float) -> str:
    section = current
    for top, candidate in headings:
        if top <= table_top + 1:
            section = candidate
        else:
            break
    return section


def _normalise_listed_row(raw: list[Any]) -> list[str]:
    row = [_clean(value) for value in raw]
    if len(row) == 6:
        row.append("")
    if len(row) != 7:
        raise RuntimeError(f"Trapani listed table-width drift: {len(row)} columns")
    return row


def _is_header(row: list[str]) -> bool:
    joined = " ".join(row).casefold()
    return "ragione sociale" in joined and "codice fiscale" in joined


def _group_status(markers: list[str]) -> str:
    marker_set = set(markers)
    unexpected = marker_set - _ALLOWED_UPDATE_MARKERS
    if unexpected:
        raise RuntimeError(f"Trapani unapproved update marker(s): {sorted(unexpected)!r}")
    nonblank = [value for value in markers if value]
    if nonblank and any(not value for value in markers):
        raise RuntimeError(f"Trapani repeated identifier mixes blank and non-blank update evidence: {markers!r}")
    return "renewal_update_in_progress" if nonblank else "listed"


def _activities(raw: str) -> list[str]:
    raw = _clean(raw)
    if not raw:
        return []
    values = [value.strip(" -") for value in re.split(r"\s+-\s*", raw) if value.strip(" -")]
    return values or [raw]


def parse_trapani_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    memberships: list[dict[str, Any]] = []
    current_section = ""
    seen_sections: list[str] = []
    seen_continuations: list[tuple[int, int, int]] = []
    header_fragments = 0

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGE_COUNT:
            raise RuntimeError(f"Trapani listed page-count drift: {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            geometry = (round(float(page.width), 2), round(float(page.height), 2))
            if geometry != _PAGE_GEOMETRY:
                raise RuntimeError(f"Trapani listed page-geometry drift on page {page_number}: {geometry}")
            tables = sorted(page.find_tables(), key=lambda table: float(table.bbox[1]))
            if len(tables) != _LISTED_TABLE_COUNTS[page_number - 1]:
                raise RuntimeError(
                    f"Trapani listed table-count drift on page {page_number}: {len(tables)}"
                )
            headings = _section_headings(page)
            page_memberships: list[dict[str, Any]] = []
            for table_number, table in enumerate(tables, 1):
                current_section = _section_for_table(current_section, headings, float(table.bbox[1]))
                if current_section and current_section not in seen_sections:
                    seen_sections.append(current_section)
                for row_number, raw in enumerate(table.extract() or [], 1):
                    row = _normalise_listed_row(raw)
                    if not any(row) or _is_header(row):
                        continue
                    key = (page_number, table_number, row_number)
                    if key == _LISTED_HEADER_FRAGMENT[0]:
                        if row != _LISTED_HEADER_FRAGMENT[1]:
                            raise RuntimeError(f"Trapani listed split-header fragment drift: {row!r}")
                        header_fragments += 1
                        continue
                    continuation = _LISTED_CONTINUATIONS.get(key)
                    if continuation is not None:
                        if row != continuation["row"]:
                            raise RuntimeError(f"Trapani continuation evidence drift at {key}: {row!r}")
                        if not memberships:
                            raise RuntimeError(f"Trapani continuation without previous membership at {key}")
                        previous = memberships[-1]
                        expected_previous = continuation["previous"]
                        observed_previous = {
                            "page": previous["page"],
                            "name": previous["name"],
                            "identifier": previous["identifier"],
                            "update_raw": previous["update_raw"],
                        }
                        if observed_previous != expected_previous:
                            raise RuntimeError(
                                f"Trapani continuation previous-row drift at {key}: {observed_previous!r}"
                            )
                        previous["name"] = continuation["name"]
                        previous["update_raw"] = continuation["update_raw"]
                        seen_continuations.append(key)
                        continue
                    if not row[0] or not row[1] or not _ID_RE.fullmatch(row[3]):
                        raise RuntimeError(f"Trapani listed row-shape drift on page {page_number}: {row!r}")
                    if row[6] not in _ALLOWED_UPDATE_MARKERS:
                        raise RuntimeError(f"Trapani listed update marker drift on page {page_number}: {row[6]!r}")
                    page_memberships.append(
                        {
                            "page": page_number,
                            "section": current_section,
                            "name": row[0],
                            "office": row[1],
                            "secondary": row[2],
                            "identifier": row[3].upper(),
                            "listing_raw": row[4],
                            "expiry_raw": row[5],
                            "update_raw": row[6],
                        }
                    )
                    memberships.append(page_memberships[-1])

    if seen_sections != list(_EXPECTED_SECTIONS):
        raise RuntimeError(f"Trapani listed section-boundary drift: {seen_sections!r}")
    if seen_continuations != list(_LISTED_CONTINUATIONS):
        raise RuntimeError(f"Trapani listed continuation-boundary drift: {seen_continuations!r}")
    if header_fragments != 1:
        raise RuntimeError(f"Trapani listed split-header fragment-count drift: {header_fragments}")
    if len(memberships) != 658:
        raise RuntimeError(f"Trapani listed sector-row cardinality drift: {len(memberships)}")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for membership in memberships:
        grouped.setdefault(membership["identifier"], []).append(membership)
    if len(grouped) != 333:
        raise RuntimeError(f"Trapani listed identifier cardinality drift: {len(grouped)}")

    records: list[dict[str, Any]] = []
    non_date_expiry_records = 0
    for identifier, rows in grouped.items():
        name_variants = _ordered_unique([row["name"] for row in rows])
        normalisation = _LISTED_NAME_VARIANT_NORMALISATIONS.get(identifier)
        if normalisation is None:
            if len(name_variants) != 1:
                raise RuntimeError(f"Trapani listed name drift within identifier {identifier}: {name_variants!r}")
            output_name = name_variants[0]
        else:
            if name_variants != normalisation["source_variants"]:
                raise RuntimeError(
                    f"Trapani approved name-variant evidence drift for {identifier}: {name_variants!r}"
                )
            output_name = normalisation["canonical"]
        office_variants = _ordered_unique([row["office"] for row in rows if row["office"]])
        office_normalisation = _LISTED_OFFICE_VARIANT_NORMALISATIONS.get(identifier)
        if office_normalisation is None:
            if len(office_variants) > 1:
                raise RuntimeError(
                    f"Trapani listed office drift within identifier {identifier}: {office_variants!r}"
                )
            output_office = office_variants[0] if office_variants else ""
        else:
            if office_variants != office_normalisation["source_variants"]:
                raise RuntimeError(
                    f"Trapani approved office-variant evidence drift for {identifier}: {office_variants!r}"
                )
            output_office = office_normalisation["canonical"]
        secondary_variants = _ordered_unique([row["secondary"] for row in rows if row["secondary"]])
        if len(secondary_variants) > 1:
            raise RuntimeError(
                f"Trapani listed secondary-office drift within identifier {identifier}: {secondary_variants!r}"
            )
        listing_raw_variants = _ordered_unique([row["listing_raw"] for row in rows])
        expiry_raw_variants = _ordered_unique([row["expiry_raw"] for row in rows])
        valid_listing_dates = _ordered_unique([_strict_date(value) for value in listing_raw_variants if _strict_date(value)])
        if len(valid_listing_dates) != 1:
            raise RuntimeError(
                f"Trapani listed listing-date evidence drift for {identifier}: {listing_raw_variants!r}"
            )
        valid_expiry_dates = _ordered_unique([_strict_date(value) for value in expiry_raw_variants if _strict_date(value)])
        expiry_date = ""
        if len(valid_expiry_dates) == 1 and len(expiry_raw_variants) == 1:
            expiry_date = valid_expiry_dates[0]
        elif identifier == "01712150819":
            expected = {
                "rows": 1,
                "pages": [34],
                "names": ["SICIL AMBIENTE DI SCATURRO AGOSTINO S.R.L."],
                "listing_raw": ["08/04/2026"],
                "updates": [""],
            }
            observed = {
                "rows": len(rows),
                "pages": _ordered_unique([str(row["page"]) for row in rows]),
                "names": name_variants,
                "listing_raw": listing_raw_variants,
                "updates": [row["update_raw"] for row in rows],
            }
            if observed != {**expected, "pages": [str(value) for value in expected["pages"]]}:
                raise RuntimeError(f"Trapani judicial-administration expiry evidence drift: {observed!r}")
            non_date_expiry_records += 1
        else:
            raise RuntimeError(
                f"Trapani listed expiry-date evidence drift for {identifier}: {expiry_raw_variants!r}"
            )
        markers = [row["update_raw"] for row in rows]
        status = _group_status(markers)
        marker_variants = _ordered_unique([marker for marker in markers if marker])
        sections = _ordered_unique([row["section"] for row in rows])
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=output_name,
                office=output_office,
                secondary=secondary_variants[0] if secondary_variants else "",
                identifier_raw=identifier,
                activities=sections,
                status=status,
                listing_date=valid_listing_dates[0],
                expiry_date=expiry_date,
                primary_date_label="Data iscrizione",
                source_fields={
                    "sections": sections,
                    "registered_office_variants": office_variants,
                    "secondary_office_variants": secondary_variants,
                    "listing_date_raw_variants": listing_raw_variants,
                    "expiry_date_raw_variants": expiry_raw_variants,
                    "in_aggiornamento": " · ".join(marker_variants),
                    "notes": ["* = ditta che ha già presentato istanza di permanenza"] if any("*" in marker for marker in marker_variants) else [],
                },
            )
        )

    if non_date_expiry_records != 1:
        raise RuntimeError(f"Trapani non-date expiry record-count drift: {non_date_expiry_records}")
    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != {"listed": 177, "renewal_update_in_progress": 156}:
        raise RuntimeError(f"Trapani listed status-boundary drift: {status_counts!r}")
    diagnostics = {
        "parser": "trapani_listed",
        "sector_rows": len(memberships),
        "public_records": len(records),
        "status_counts": status_counts,
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "source_sections": seen_sections,
        "continuation_rows": len(seen_continuations),
        "split_header_fragments": header_fragments,
        "non_date_expiry_records": non_date_expiry_records,
    }
    return ParsedBatch(records=records, diagnostics=diagnostics)


def parse_trapani_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows: list[list[str]] = []
    row_pages: list[int] = []
    seen_continuations: list[tuple[int, int, int]] = []
    per_page: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGE_COUNT:
            raise RuntimeError(f"Trapani applicant page-count drift: {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            geometry = (round(float(page.width), 2), round(float(page.height), 2))
            if geometry != _PAGE_GEOMETRY:
                raise RuntimeError(f"Trapani applicant page-geometry drift on page {page_number}: {geometry}")
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"Trapani applicant table-count drift on page {page_number}: {len(tables)}")
            page_rows: list[list[str]] = []
            for row_number, raw in enumerate(tables[0].extract() or [], 1):
                row = [_clean(value) for value in raw]
                if not any(row) or _is_header(row):
                    continue
                if len(row) == 7 and row[0] and _ID_RE.fullmatch(row[3]):
                    if row[6] not in _ALLOWED_APPLICANT_OUTCOMES:
                        raise RuntimeError(f"Trapani applicant outcome drift on page {page_number}: {row[6]!r}")
                    if not _strict_date(row[5]):
                        raise RuntimeError(f"Trapani applicant application-date drift on page {page_number}: {row[5]!r}")
                    page_rows.append(row)
                    rows.append(row)
                    row_pages.append(page_number)
                    continue

                key = (page_number, 1, row_number)
                continuation = _APPLICANT_CONTINUATIONS.get(key)
                if continuation is None:
                    raise RuntimeError(f"Trapani applicant row-shape drift on page {page_number}: {row!r}")
                if row != continuation["row"]:
                    raise RuntimeError(f"Trapani applicant continuation evidence drift at {key}: {row!r}")
                previous = continuation["previous"]
                if not rows or row_pages[-1] != previous["page"]:
                    raise RuntimeError(
                        f"Trapani applicant continuation previous-page drift at {key}: "
                        f"{row_pages[-1] if row_pages else None!r}"
                    )
                if rows[-1][0] != previous["name"] or rows[-1][3].upper() != previous["identifier"]:
                    raise RuntimeError(f"Trapani applicant continuation previous-record drift at {key}: {rows[-1]!r}")
                if any(row[index] for index in (2, 3, 5, 6)):
                    raise RuntimeError(f"Trapani applicant continuation unsupported-field drift at {key}: {row!r}")
                for index in (0, 1, 4):
                    if row[index]:
                        rows[-1][index] = _clean(f"{rows[-1][index]} {row[index]}")
                seen_continuations.append(key)
            per_page.append(len(page_rows))
    if per_page != _APPLICANT_ROW_COUNTS:
        raise RuntimeError(f"Trapani applicant per-page row drift: {per_page!r}")
    if seen_continuations != list(_APPLICANT_CONTINUATIONS):
        raise RuntimeError(f"Trapani applicant continuation-boundary drift: {seen_continuations!r}")
    if len(rows) != 222 or len({row[3].upper() for row in rows}) != 222:
        raise RuntimeError("Trapani applicant identifier/cardinality drift")

    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=row[0],
                office=row[1],
                secondary=row[2],
                identifier_raw=row[3].upper(),
                activities=_activities(row[4]),
                status="pending",
                outcome_raw=row[6],
                application_date=_strict_date(row[5]),
                primary_date_label="Data presentazione istanza",
                source_fields={
                    "requested_activities_source": row[4],
                    "application_date_raw_variants": [row[5]],
                },
            )
        )
    diagnostics = {
        "parser": "trapani_applicants",
        "sector_rows": len(rows),
        "public_records": len(records),
        "status_counts": {"pending": len(records)},
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "outcome_counts": dict(Counter(record["outcome_raw"] for record in records)),
        "continuation_rows": len(seen_continuations),
    }
    return ParsedBatch(records=records, diagnostics=diagnostics)


PARSERS = {
    "trapani_listed": parse_trapani_listed,
    "trapani_applicants": parse_trapani_applicants,
}

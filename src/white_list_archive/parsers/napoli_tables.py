from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "2"
_REFERENCE_DATE = "2026-09-13"
_LISTED_SHA256 = "93a8635c0bd9b00587f9cc60c52752061bd239a7c16cb34b64a11e495a0ab4be"
_APPLICANT_SHA256 = "053be2500b07a7da536c344aede12084dde9b7cf28b4717af99764cbd05e7e6b"
_LISTED_PAGES = 60
_APPLICANT_PAGES = 215
_EXPECTED_LISTED_RECORDS = 2259
_EXPECTED_APPLICANT_RECORDS = 2571

_EXPECTED_LISTED_STATUS_COUNTS = {
    "listed": 792,
    "renewal_update_in_progress": 1423,
    "rejected_or_denied": 12,
    "cancellation_related": 3,
    "other_or_unknown": 29,
}
_EXPECTED_APPLICANT_STATUS_COUNTS = {
    "pending": 2530,
    "rejected_or_denied": 40,
    "other_or_unknown": 1,
}
_EXPECTED_LISTED_IDENTIFIER_SHAPES = {"11_digit": 2068, "16_alnum": 167, "raw_only": 24}
_EXPECTED_APPLICANT_IDENTIFIER_SHAPES = {"11_digit": 2298, "16_alnum": 261, "raw_only": 12}

_ROMAN_SECTIONS = frozenset({"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"})
_SHORT_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{2})$")
_IDENTIFIER_11 = re.compile(r"^\d{11}$")
_IDENTIFIER_16 = re.compile(r"^[A-Za-z0-9]{16}$")

# The 48 source-positive nonstandard values in the listed outcome column are
# frozen by ordinal. Ordinary update rows are validated separately by their
# exact source prefix.
_LISTED_REVIEWED_UPDATE_SPECIAL = frozenset({671, 993, 1528, 1624})
_LISTED_REJECTED = frozenset({174, 197, 212, 440, 697, 1101, 1149, 1266, 1410, 1831, 1863, 2061})
_LISTED_CANCELLATION = frozenset({771, 830, 1524})
_LISTED_OTHER = frozenset(
    {
        32,
        61,
        77,
        83,
        155,
        371,
        372,
        402,
        488,
        529,
        592,
        731,
        869,
        871,
        950,
        964,
        968,
        1053,
        1240,
        1288,
        1326,
        1331,
        1407,
        1536,
        1661,
        1815,
        1912,
        2046,
        2244,
    }
)
_EXPECTED_LISTED_SPECIAL = (
    _LISTED_REVIEWED_UPDATE_SPECIAL | _LISTED_REJECTED | _LISTED_CANCELLATION | _LISTED_OTHER
)

# Physical table extraction places three glyph continuations immediately below
# the horizontal border. They are source-positive continuations of the preceding
# adverse outcome, not independent outcomes of the following company.
_APPLICANT_OUTCOME_CONTINUATIONS = {
    511: (
        "DINIEGO DI ISCRIZIONE Provv. 0135353 del 05/07/2017 confermato con",
        512,
        "provvedimento",
    ),
    879: (
        "DINIEGO DI ISCRIZIONE Provv. 0132224 del 30/06/2017 confermato da",
        880,
        "provv. 399217 del",
    ),
    1259: (
        "Provvedimento interdittivo prot.193574 dell'11/05/2026 sospeso con",
        1260,
        "ordinanza TAR",
    ),
}
_APPLICANT_RAW_NONBLANK = frozenset(
    {
        15,
        105,
        321,
        362,
        371,
        507,
        511,
        512,
        513,
        781,
        814,
        816,
        840,
        859,
        876,
        879,
        880,
        1025,
        1203,
        1259,
        1260,
        1306,
        1335,
        1484,
        1501,
        1572,
        1586,
        1642,
        1845,
        1874,
        2040,
        2045,
        2058,
        2147,
        2165,
        2195,
        2201,
        2246,
        2251,
        2280,
        2339,
        2361,
        2393,
        2394,
    }
)
_APPLICANT_CONTINUATION_ROWS = frozenset({512, 880, 1260})
_APPLICANT_INDEPENDENT_OUTCOME = _APPLICANT_RAW_NONBLANK - _APPLICANT_CONTINUATION_ROWS
_APPLICANT_OTHER = frozenset({1259})
_APPLICANT_REJECTED = _APPLICANT_INDEPENDENT_OUTCOME - _APPLICANT_OTHER

# Three legal-form fragments are printed across a horizontal row boundary.
# Bind only the exact reviewed raw pair; any source/text drift fails closed.
_APPLICANT_NAME_BOUNDARIES = {
    793: (
        "ECOLOGIA LA VESUVIANA",
        794,
        "S.R.L. ECOLOGIA SAN VINCENZO S.A.S. DI MIELE EMILIA",
        "ECOLOGIA LA VESUVIANA S.R.L.",
        "ECOLOGIA SAN VINCENZO S.A.S. DI MIELE EMILIA",
    ),
    1209: (
        "GENERAL COSTRUZIONI",
        1210,
        "S.R.L. GENERAL SERVICE S.R.L.",
        "GENERAL COSTRUZIONI S.R.L.",
        "GENERAL SERVICE S.R.L.",
    ),
    1226: (
        "GESTIONE APPALTI E",
        1227,
        "SERVIZI S.R.L.S. GESTIONE HOTEL S.R.L.",
        "GESTIONE APPALTI E SERVIZI S.R.L.S.",
        "GESTIONE HOTEL S.R.L.",
    ),
}
_PROTECTED_CLEAN_NAME_ROWS = {
    402: "CEM.AR. 86 - SOCIETA' COOPERATIVA DI PRODUZIONE E LAVORO A RESPON SABILITA' LIMITATA",
    403: "CEMENTI MOCCIA SPA",
}

# One malformed listed registration date is source-positive but not a valid
# DD/MM/YY value. Preserve the raw typography and do not infer the omitted
# separator or a normalised date.
_LISTED_MALFORMED_LISTING_DATE = {
    556: ("DE LISIO COSTRUZIONI SRL", "04518100633", "14/0319"),
}

# Seven listed records carry a source-positive non-calendar validity term.
# Bind ordinal + company + exact cleaned source typography; do not interpret
# the term as a calendar date or as a blank expiry.
_LISTED_NONCALENDAR_EXPIRY = {
    83: ("AMBIENTE CAMPANIA S.R.L.", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    155: ("AURORA S.R.L.", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    371: ("CIEFFE COSTRUZIONI SRL UNIPERSONALE", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    372: ("CIEFFE LAVORI S.R.L.", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    488: ("COSTRUZIONI GENERALI SUD S.R.L.", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    968: ("FONTANA DI FONTANA FRANCESCO S.R.L.", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    2244: ("XECO SRL", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
}

# Exact source-bound section anomalies. Invalid source typography is never
# silently repaired into a different legal section: only positively valid
# tokens are retained, duplicate valid tokens are de-duplicated, and the
# original source text remains in source_fields.
_SECTION_EXCEPTIONS = {
    "listed": {
        454: ("CONGLOMERATI S.r.l.", "05027321214", "II-IIII", ("II",)),
        820: ("ELETTROIMPIANTI DI RAIMO VITALIANO", "RMAVLN69P15I391U", "RMAVLN69P15I391U", ()),
        915: ("F.LLI MARTINO SNC DI MARTINO PASQUALE & C.", "04986160630", "I-VI-VI-X", ("I", "VI", "X")),
        1782: ("R.T. ELECTRONIC SYSTEM S.R.L.", "09469461215", "I-II-II-IV-V-VI-X", ("I", "II", "IV", "V", "VI", "X")),
    },
    "applicants": {
        398: ("CECA SRL", "05091870633", "I-III-V-V-X", ("I", "III", "V", "X")),
        1099: ("FG SERVICE S.R.L.", "09706611218", "IIII", ()),
        1170: ("G.P. PITTURAZIONI DI PIACENTE GAETANO", "PCNGTN94M27C129P", "I-II-III-V-VX", ("I", "II", "III", "V")),
        1520: ("L.C.S. ENGINEERING S.R.L.", "07466761215", "IIII", ()),
        2404: ("TECNOMEDICAL S.R.L.", "03110040635", "IIII", ()),
    },
}

# On 17 page-bottom rows the PDF table geometry omits the company cell from
# pdfplumber's table grid (and on the last five rows also further cells), even
# though the words are visibly present within the same physical row. A separate
# byte-pinned audit recovered the words using stable page-column bounds. Bind
# both the exact truncated table extraction and the exact recovered row so that
# any source or extraction-library drift fails closed rather than being filled
# heuristically at runtime.
_LISTED_PAGE_BOTTOM_RECOVERY = {
    1620: (("1620", "", "Napoli", "", "MRDLCU71A22F839W", "III-V", "19/10/16", "23/05/23", "iscrizione in aggiornamento"), ("1620", "NEW HOUSE COSTRUZIONI DI MURDACA LUCA I.I.", "Napoli", "", "MRDLCU71A22F839W", "III-V", "19/10/16", "23/05/23", "iscrizione in aggiornamento")),
    1659: (("1659", "", "Qualiano", "", "07427261214", "I-III", "15/07/25", "14/07/26", ""), ("1659", "OPERA IMPIANTI E COSTRUZIONI S.R.L.", "Qualiano", "", "07427261214", "I-III", "15/07/25", "14/07/26", "")),
    1698: (("1698", "", "Casalnuovo di Napoli", "", "04707610657", "III-V", "25/11/25", "24/11/26", ""), ("1698", "PERDONO DEVELOPMENT S.R.L.", "Casalnuovo di Napoli", "", "04707610657", "III-V", "25/11/25", "24/11/26", "")),
    1735: (("1735", "", "Pomigliano D'Arco", "", "RRCGST64P20G812T", "I-III-IV-V-VI-X", "22/10/19", "10/09/25", "iscrizione in aggiornamento"), ("1735", "POMILIA COSTRUZIONI DI ERRICHIELLO AUGUSTO IMPRESA INDIVIDUALE", "Pomigliano D'Arco", "", "RRCGST64P20G812T", "I-III-IV-V-VI-X", "22/10/19", "10/09/25", "iscrizione in aggiornamento")),
    1775: (("1775", "", "Napoli", "", "06651731215", "I", "05/12/16", "14/05/26", "iscrizione in aggiornamento"), ("1775", "R.C.S. SRL", "Napoli", "", "06651731215", "I", "05/12/16", "14/05/26", "iscrizione in aggiornamento")),
    1816: (("1816", "", "Napoli", "", "00282670637", "VI", "20/12/19", "13/02/23", "iscrizione in aggiornamento"), ("1816", "RICOLFI & C. S.P.A. - CASA DI SPEDIZIONI", "Napoli", "", "00282670637", "VI", "20/12/19", "13/02/23", "iscrizione in aggiornamento")),
    1854: (("1854", "", "Brusciano", "", "09415551218", "I-II-III-V-VI-X", "24/02/22", "18/03/27", ""), ("1854", "RUSSO GROUP SAS DI RUSSO FERDINANDO E C.", "Brusciano", "", "09415551218", "I-II-III-V-VI-X", "24/02/22", "18/03/27", "")),
    1890: (("1890", "", "Volla", "", "02768721215", "VI", "15/12/20", "12/09/25", "iscrizione in aggiornamento"), ("1890", "S.I.TRA.S. S.R.L. SOCIETA' ITALIANA TRASPORTI SPECIALI", "Volla", "", "02768721215", "VI", "15/12/20", "12/09/25", "iscrizione in aggiornamento")),
    1923: (("1923", "", "Somma Vesuviana", "", "04031220652", "III-V", "07/12/16", "22/10/26", ""), ("1923", "SANTACROCE SRL", "Somma Vesuviana", "", "04031220652", "III-V", "07/12/16", "22/10/26", "")),
    1965: (("1965", "", "Napoli", "", "09452181218", "X", "08/04/22", "07/04/23", "iscrizione in aggiornamento"), ("1965", "SERVIZI TECNICI E AMBIENTALI SRL", "Napoli", "", "09452181218", "X", "08/04/22", "07/04/23", "iscrizione in aggiornamento")),
    2004: (("2004", "", "Napoli", "", "07758000637", "I-III-V", "05/12/25", "04/12/26", "iscrizione in aggiornamento per modfica assetto societario"), ("2004", "SMARIG S.R.L", "Napoli", "", "07758000637", "I-III-V", "05/12/25", "04/12/26", "iscrizione in aggiornamento per modfica assetto societario")),
    2036: (("2036", "", "Casoria", "", "10041191213", "III", "18/11/25", "17/11/26", ""), ("2036", "SS COSTRUZIONI S.R.L.", "Casoria", "", "10041191213", "III", "18/11/25", "17/11/26", "")),
    2074: (("2074", "", "", "", "07789361214", "X", "", "09/09/25", "iscrizione in aggiornamento"), ("2074", "T-CYCLE INDUSTRIES S.R.L.", "Napoli", "", "07789361214", "X", "12/06/23", "09/09/25", "iscrizione in aggiornamento")),
    2117: (("2117", "", "", "", "PLTGNN95L47E396X", "IX", "", "08/12/26", ""), ("2117", "TERRA MIA DI PILATO GIOVANNA", "Barano d'Ischia", "", "PLTGNN95L47E396X", "IX", "09/12/25", "08/12/26", "")),
    2157: (("2157", "", "", "", "08282961211", "VI", "", "", "iscrizione in aggiornamento"), ("2157", "TRASPORTI F.C. S.R.L.S.", "Casoria", "", "08282961211", "VI", "08/03/22", "13/11/25", "iscrizione in aggiornamento")),
    2200: (("2200", "", "", "", "VLLGNN80T20F839S", "VI", "", "", ""), ("2200", "VELTRANS DI VELLUSO GIOVANNI", "Giugliano in Campania", "", "VLLGNN80T20F839S", "VI", "27/10/17", "09/12/26", "")),
    2239: (("2239", "", "", "", "08491491216", "IV", "", "", "iscrizione in aggiornamento"), ("2239", "WORK IN PROGRESS SRL", "Melito di Napoli", "", "08491491216", "IV", "22/10/19", "16/09/22", "iscrizione in aggiornamento")),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_cfg(cfg: dict[str, Any], *, source_key: str, population_scope: str, sha256: str) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Napoli source-key drift: {cfg.get('source_key')!r} != {source_key!r}")
    if cfg.get("authority_key") != "napoli":
        raise RuntimeError("Napoli parser bound to a non-Napoli authority")
    if cfg.get("population_scope") != population_scope:
        raise RuntimeError(
            f"Napoli population-scope drift for {source_key}: {cfg.get('population_scope')!r} != {population_scope!r}"
        )
    if cfg.get("sha256") != sha256:
        raise RuntimeError(f"Napoli configured SHA-256 drift for {source_key}: {cfg.get('sha256')!r} != {sha256!r}")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(
            f"Napoli reference-date drift for {source_key}: {cfg.get('reference_date')!r} != {_REFERENCE_DATE!r}"
        )


def _physical_rows(path: Path, *, pages: int, terminal: int, width: int, population: str) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != pages:
            raise RuntimeError(f"Napoli {population} page-count drift: {len(pdf.pages)} != {pages}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"Napoli {population} table-count drift on page {page_number}: {len(tables)} != 1")
            table = tables[0]
            extracted = table.extract() or []
            if len(extracted) != len(table.rows):
                raise RuntimeError(f"Napoli {population} physical/extracted row drift on page {page_number}")
            for row_number, raw in enumerate(extracted, start=1):
                cells = [_clean(value) for value in (raw or [])]
                if len(cells) != width:
                    raise RuntimeError(
                        f"Napoli {population} table-width drift p{page_number} r{row_number}: {len(cells)} != {width}"
                    )
                if not cells[0].isdigit():
                    continue
                ordinal = int(cells[0])
                if not (1 <= ordinal <= terminal):
                    raise RuntimeError(f"Napoli {population} unexpected ordinal on page {page_number}: {ordinal}")
                if ordinal in rows:
                    raise RuntimeError(f"Napoli {population} duplicate source ordinal: {ordinal}")
                rows[ordinal] = {"page": page_number, "row": row_number, "cells": cells}
    expected = list(range(1, terminal + 1))
    if sorted(rows) != expected:
        missing = sorted(set(expected) - set(rows))
        unexpected = sorted(set(rows) - set(expected))
        raise RuntimeError(
            f"Napoli {population} source-ordinal drift: missing={missing[:20]!r}; unexpected={unexpected[:20]!r}"
        )
    return rows


def _prepare_listed_rows(rows: dict[int, dict[str, Any]]) -> None:
    observed = {ordinal for ordinal, row in rows.items() if not row["cells"][1]}
    expected = set(_LISTED_PAGE_BOTTOM_RECOVERY)
    if observed != expected:
        raise RuntimeError(
            f"Napoli listed page-bottom recovery population drift: observed={sorted(observed)!r}; "
            f"expected={sorted(expected)!r}"
        )
    for ordinal, (truncated, recovered) in _LISTED_PAGE_BOTTOM_RECOVERY.items():
        current = tuple(rows[ordinal]["cells"])
        if current != truncated:
            raise RuntimeError(
                f"Napoli listed reviewed page-bottom row drift at ordinal {ordinal}: {current!r} != {truncated!r}"
            )
        rows[ordinal]["cells"] = list(recovered)


def _identifier(raw: str) -> tuple[list[str], str]:
    value = _clean(raw).upper()
    if _IDENTIFIER_11.fullmatch(value):
        return [value], "11_digit"
    if _IDENTIFIER_16.fullmatch(value):
        return [value], "16_alnum"
    if not value:
        return [], "blank"
    return [], "raw_only"


def _sections(
    raw: str,
    *,
    ordinal: int,
    population: str,
    company: str,
    identifier_raw: str,
) -> list[str]:
    value = _clean(raw)
    reviewed = _SECTION_EXCEPTIONS.get(population, {}).get(ordinal)
    if reviewed is not None:
        expected_company, expected_identifier, expected_raw, retained_tokens = reviewed
        if (
            _clean(company) != expected_company
            or _clean(identifier_raw).upper() != expected_identifier
            or value != expected_raw
        ):
            raise RuntimeError(
                f"Napoli {population} reviewed section exception drift at ordinal {ordinal}: "
                f"company={_clean(company)!r}; identifier={_clean(identifier_raw)!r}; section={value!r}"
            )
        return [f"Sezione {token}" for token in retained_tokens]
    if not value:
        return []
    tokens = [token for token in re.split(r"[-,;/\s]+", value.upper()) if token]
    if not tokens or any(token not in _ROMAN_SECTIONS for token in tokens):
        raise RuntimeError(f"Napoli {population} unreviewed section value at ordinal {ordinal}: {value!r}")
    if len(tokens) != len(set(tokens)):
        raise RuntimeError(f"Napoli {population} duplicate section token at ordinal {ordinal}: {value!r}")
    return [f"Sezione {token}" for token in tokens]


def _short_date(raw: str, *, ordinal: int, population: str, field: str) -> str:
    value = _clean(raw)
    if not value:
        return ""
    match = _SHORT_DATE.fullmatch(value)
    if not match:
        raise RuntimeError(
            f"Napoli {population} unreviewed {field} typography at ordinal {ordinal}: {value!r}"
        )
    day, month, short_year = (int(part) for part in match.groups())
    try:
        return date(2000 + short_year, month, day).isoformat()
    except ValueError as exc:
        raise RuntimeError(
            f"Napoli {population} invalid {field} calendar date at ordinal {ordinal}: {value!r}"
        ) from exc


def _listed_listing_date(raw: str, *, ordinal: int, company: str, identifier_raw: str) -> str:
    value = _clean(raw)
    reviewed = _LISTED_MALFORMED_LISTING_DATE.get(ordinal)
    if reviewed is not None:
        expected_company, expected_identifier, expected_raw = reviewed
        if (
            _clean(company) != expected_company
            or _clean(identifier_raw).upper() != expected_identifier
            or value != expected_raw
        ):
            raise RuntimeError(
                f"Napoli listed reviewed malformed listing-date drift at ordinal {ordinal}: "
                f"company={_clean(company)!r}; identifier={_clean(identifier_raw)!r}; date={value!r}"
            )
        return ""
    return _short_date(raw, ordinal=ordinal, population="listed", field="listing date")


def _listed_expiry(raw: str, *, ordinal: int, company: str) -> str:
    value = _clean(raw)
    reviewed = _LISTED_NONCALENDAR_EXPIRY.get(ordinal)
    if reviewed is not None:
        expected_company, expected_raw = reviewed
        if _clean(company) != expected_company or value != expected_raw:
            raise RuntimeError(
                f"Napoli listed reviewed non-calendar expiry drift at ordinal {ordinal}: "
                f"company={_clean(company)!r}; expiry={value!r}"
            )
        return ""
    return _short_date(raw, ordinal=ordinal, population="listed", field="expiry date")


def _listed_status(ordinal: int, raw: str) -> str:
    value = _clean(raw)
    folded = value.casefold()
    if not value:
        return "listed"
    if folded.startswith("iscrizione in aggiornamento"):
        return "renewal_update_in_progress"
    if ordinal in _LISTED_REVIEWED_UPDATE_SPECIAL:
        return "renewal_update_in_progress"
    if ordinal in _LISTED_REJECTED:
        return "rejected_or_denied"
    if ordinal in _LISTED_CANCELLATION:
        return "cancellation_related"
    if ordinal in _LISTED_OTHER:
        return "other_or_unknown"
    raise RuntimeError(f"Napoli listed unreviewed outcome at ordinal {ordinal}: {value!r}")


def _prepare_applicant_rows(rows: dict[int, dict[str, Any]]) -> None:
    raw_nonblank = {ordinal for ordinal, row in rows.items() if row["cells"][7]}
    if raw_nonblank != _APPLICANT_RAW_NONBLANK:
        raise RuntimeError(
            f"Napoli applicant raw outcome population drift: observed={sorted(raw_nonblank)!r}"
        )

    for parent, (parent_raw, child, fragment_raw) in _APPLICANT_OUTCOME_CONTINUATIONS.items():
        if rows[parent]["cells"][7] != parent_raw or rows[child]["cells"][7] != fragment_raw:
            raise RuntimeError(
                f"Napoli applicant reviewed outcome continuation drift at {parent}/{child}: "
                f"{rows[parent]['cells'][7]!r} / {rows[child]['cells'][7]!r}"
            )
        rows[parent]["cells"][7] = f"{parent_raw} {fragment_raw}"
        rows[child]["cells"][7] = ""

    for parent, (parent_raw, child, child_raw, parent_name, child_name) in _APPLICANT_NAME_BOUNDARIES.items():
        if rows[parent]["cells"][1] != parent_raw or rows[child]["cells"][1] != child_raw:
            raise RuntimeError(
                f"Napoli applicant reviewed company-border drift at {parent}/{child}: "
                f"{rows[parent]['cells'][1]!r} / {rows[child]['cells'][1]!r}"
            )
        rows[parent]["cells"][1] = parent_name
        rows[child]["cells"][1] = child_name

    for ordinal, expected in _PROTECTED_CLEAN_NAME_ROWS.items():
        if rows[ordinal]["cells"][1] != expected:
            raise RuntimeError(
                f"Napoli applicant protected clean-name drift at ordinal {ordinal}: "
                f"{rows[ordinal]['cells'][1]!r} != {expected!r}"
            )

    independent = {ordinal for ordinal, row in rows.items() if row["cells"][7]}
    if independent != _APPLICANT_INDEPENDENT_OUTCOME:
        raise RuntimeError(
            f"Napoli applicant independent outcome population drift: observed={sorted(independent)!r}"
        )


def _applicant_status(ordinal: int, raw: str) -> str:
    value = _clean(raw)
    if not value:
        return "pending"
    if ordinal in _APPLICANT_OTHER:
        return "other_or_unknown"
    if ordinal in _APPLICANT_REJECTED:
        return "rejected_or_denied"
    raise RuntimeError(f"Napoli applicant unreviewed independent outcome at ordinal {ordinal}: {value!r}")


def parse_napoli_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key="napoli-listed", population_scope="listed", sha256=_LISTED_SHA256)
    if _sha256(path) != _LISTED_SHA256:
        raise RuntimeError("Napoli listed source bytes drift from approved SHA-256")

    rows = _physical_rows(
        path,
        pages=_LISTED_PAGES,
        terminal=_EXPECTED_LISTED_RECORDS,
        width=9,
        population="listed",
    )
    _prepare_listed_rows(rows)
    observed_special = {
        ordinal
        for ordinal, row in rows.items()
        if row["cells"][8] and not row["cells"][8].casefold().startswith("iscrizione in aggiornamento")
    }
    if observed_special != _EXPECTED_LISTED_SPECIAL:
        raise RuntimeError(
            f"Napoli listed reviewed special-outcome population drift: observed={sorted(observed_special)!r}"
        )

    identifier_shapes: Counter[str] = Counter()
    blank_listing_dates = 0
    blank_expiry_dates = 0
    records: list[dict[str, Any]] = []
    for ordinal in range(1, _EXPECTED_LISTED_RECORDS + 1):
        page = rows[ordinal]["page"]
        _, name, office, secondary, identifier_raw, sections_raw, listing_raw, expiry_raw, outcome_raw = rows[ordinal]["cells"]
        if not name:
            raise RuntimeError(f"Napoli listed blank company name at ordinal {ordinal}")
        identifiers, identifier_shape = _identifier(identifier_raw)
        identifier_shapes[identifier_shape] += 1
        sections = _sections(
            sections_raw,
            ordinal=ordinal,
            population="listed",
            company=name,
            identifier_raw=identifier_raw,
        )
        listing_date = _listed_listing_date(
            listing_raw,
            ordinal=ordinal,
            company=name,
            identifier_raw=identifier_raw,
        )
        expiry_date = _listed_expiry(expiry_raw, ordinal=ordinal, company=name)
        blank_listing_dates += int(not listing_raw)
        blank_expiry_dates += int(not expiry_raw)
        status = _listed_status(ordinal, outcome_raw)

        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=sections,
            status=status,
            outcome_raw=outcome_raw,
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": sections,
                "sections_source_raw": sections_raw,
                "listing_date_raw_variants": [listing_raw] if listing_raw else [],
                "expiry_date_raw_variants": [expiry_raw] if expiry_raw else [],
                "in_aggiornamento": _clean(outcome_raw) if status == "renewal_update_in_progress" else "",
                "source_page": page,
            },
        )
        record["identifiers"] = identifiers
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Napoli listed status drift: {status_counts!r}")
    if dict(identifier_shapes) != _EXPECTED_LISTED_IDENTIFIER_SHAPES:
        raise RuntimeError(f"Napoli listed identifier-shape drift: {dict(identifier_shapes)!r}")

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "napoli_listed",
            "parser_version": PARSER_VERSION,
            "source_pages": _LISTED_PAGES,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_shapes": dict(identifier_shapes),
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "blank_listing_dates": blank_listing_dates,
            "blank_expiry_dates": blank_expiry_dates,
            "reviewed_special_outcomes": len(_EXPECTED_LISTED_SPECIAL),
            "reviewed_malformed_listing_dates": len(_LISTED_MALFORMED_LISTING_DATE),
            "reviewed_noncalendar_expiries": len(_LISTED_NONCALENDAR_EXPIRY),
            "reviewed_section_exceptions": len(_SECTION_EXCEPTIONS["listed"]),
            "reviewed_page_bottom_rows": len(_LISTED_PAGE_BOTTOM_RECOVERY),
        },
    )


def parse_napoli_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key="napoli-applicants", population_scope="applicants", sha256=_APPLICANT_SHA256)
    if _sha256(path) != _APPLICANT_SHA256:
        raise RuntimeError("Napoli applicant source bytes drift from approved SHA-256")

    rows = _physical_rows(
        path,
        pages=_APPLICANT_PAGES,
        terminal=_EXPECTED_APPLICANT_RECORDS,
        width=8,
        population="applicants",
    )
    _prepare_applicant_rows(rows)

    identifier_shapes: Counter[str] = Counter()
    blank_application_dates = 0
    records: list[dict[str, Any]] = []
    for ordinal in range(1, _EXPECTED_APPLICANT_RECORDS + 1):
        page = rows[ordinal]["page"]
        _, name, office, secondary, identifier_raw, sections_raw, application_raw, outcome_raw = rows[ordinal]["cells"]
        if not name:
            raise RuntimeError(f"Napoli applicant blank company name at ordinal {ordinal}")
        identifiers, identifier_shape = _identifier(identifier_raw)
        identifier_shapes[identifier_shape] += 1
        sections = _sections(
            sections_raw,
            ordinal=ordinal,
            population="applicants",
            company=name,
            identifier_raw=identifier_raw,
        )
        application_date = _short_date(
            application_raw,
            ordinal=ordinal,
            population="applicants",
            field="application date",
        )
        blank_application_dates += int(not application_raw)
        status = _applicant_status(ordinal, outcome_raw)

        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=sections,
            status=status,
            outcome_raw=outcome_raw,
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "requested_activities_source": sections_raw,
                "application_date_raw_variants": [application_raw] if application_raw else [],
                "source_page": page,
            },
        )
        record["identifiers"] = identifiers
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Napoli applicant status drift: {status_counts!r}")
    if dict(identifier_shapes) != _EXPECTED_APPLICANT_IDENTIFIER_SHAPES:
        raise RuntimeError(f"Napoli applicant identifier-shape drift: {dict(identifier_shapes)!r}")

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "napoli_applicants",
            "parser_version": PARSER_VERSION,
            "source_pages": _APPLICANT_PAGES,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_shapes": dict(identifier_shapes),
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "blank_application_dates": blank_application_dates,
            "reviewed_outcome_continuations": len(_APPLICANT_OUTCOME_CONTINUATIONS),
            "reviewed_name_boundaries": len(_APPLICANT_NAME_BOUNDARIES),
            "reviewed_section_exceptions": len(_SECTION_EXCEPTIONS["applicants"]),
        },
    )


PARSERS = {
    "napoli_listed": parse_napoli_listed,
    "napoli_applicants": parse_napoli_applicants,
}

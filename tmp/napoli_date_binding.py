from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import sys

import pdfplumber

SHORT = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2})$")
EXPECTED_LISTING = [(556, "DE LISIO COSTRUZIONI SRL", "04518100633", "14/0319")]
EXPECTED_EXPIRY = [
    (83, "AMBIENTE CAMPANIA S.R.L.", "09382941210", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    (155, "AURORA S.R.L.", "05472591212", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    (371, "CIEFFE COSTRUZIONI SRL UNIPERSONALE", "06292251219", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    (372, "CIEFFE LAVORI S.R.L.", "05720260651", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    (488, "COSTRUZIONI GENERALI SUD S.R.L.", "06555141214", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    (968, "FONTANA DI FONTANA FRANCESCO S.R.L.", "08331081219", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
    (2244, "XECO SRL", "03440840613", "Iscrizione valida per la durata dell'amministrazi one giudiziaria"),
]


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def load_rows(path: Path, *, pages: int, terminal: int, width: int) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != pages:
            raise RuntimeError(f"page drift: {len(pdf.pages)} != {pages}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"table-count drift p{page_number}: {len(tables)}")
            table = tables[0]
            extracted = table.extract() or []
            if len(extracted) != len(table.rows):
                raise RuntimeError(f"physical/extracted row drift p{page_number}")
            for row_number, raw in enumerate(extracted, start=1):
                if len(raw or []) != width:
                    raise RuntimeError(f"width drift p{page_number} r{row_number}: {len(raw or [])}")
                cells = [clean(value) for value in raw]
                if not cells[0].isdigit():
                    continue
                ordinal = int(cells[0])
                if ordinal in result:
                    raise RuntimeError(f"duplicate ordinal: {ordinal}")
                result[ordinal] = cells
    if sorted(result) != list(range(1, terminal + 1)):
        raise RuntimeError("ordinal coverage drift")
    return result


def malformed(value: str) -> bool:
    if not value:
        return False
    match = SHORT.fullmatch(value)
    if not match:
        return True
    day, month, year = map(int, match.groups())
    try:
        date(2000 + year, month, day)
    except ValueError:
        return True
    return False


def audit(listed_path: Path, applicant_path: Path) -> None:
    listed = load_rows(listed_path, pages=60, terminal=2259, width=9)
    applicants = load_rows(applicant_path, pages=215, terminal=2571, width=8)
    listing = [(o, row[1], row[4], row[6]) for o, row in listed.items() if malformed(row[6])]
    expiry = [(o, row[1], row[4], row[7]) for o, row in listed.items() if malformed(row[7])]
    application = [(o, row[1], row[4], row[6]) for o, row in applicants.items() if malformed(row[6])]
    if listing != EXPECTED_LISTING:
        raise RuntimeError(f"listed listing-date anomaly drift: {listing!r}")
    if expiry != EXPECTED_EXPIRY:
        raise RuntimeError(f"listed expiry anomaly drift: {expiry!r}")
    if application:
        raise RuntimeError(f"applicant application-date anomaly drift: {application!r}")


def patch_parser(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "_LISTED_MALFORMED_LISTING_DATE" in text:
        raise RuntimeError("Napoli malformed listing-date binding already present")

    anchor = "_LISTED_NONCALENDAR_EXPIRY = {\n"
    insert = '''# One malformed listed registration date is source-positive but not a valid
# DD/MM/YY value. Preserve the raw typography and do not infer the omitted
# separator or a normalised date.
_LISTED_MALFORMED_LISTING_DATE = {
    556: ("DE LISIO COSTRUZIONI SRL", "04518100633", "14/0319"),
}

_LISTED_NONCALENDAR_EXPIRY = {
'''
    if text.count(anchor) != 1:
        raise RuntimeError("listing-date constant anchor drift")
    text = text.replace(anchor, insert, 1)

    anchor = "def _listed_expiry(raw: str, *, ordinal: int, company: str) -> str:\n"
    insert = '''def _listed_listing_date(raw: str, *, ordinal: int, company: str, identifier_raw: str) -> str:
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
'''
    if text.count(anchor) != 1:
        raise RuntimeError("listed-expiry function anchor drift")
    text = text.replace(anchor, insert, 1)

    old = 'listing_date = _short_date(listing_raw, ordinal=ordinal, population="listed", field="listing date")'
    new = '''listing_date = _listed_listing_date(
            listing_raw,
            ordinal=ordinal,
            company=name,
            identifier_raw=identifier_raw,
        )'''
    if text.count(old) != 1:
        raise RuntimeError("listed listing-date call anchor drift")
    text = text.replace(old, new, 1)

    diag = '            "reviewed_noncalendar_expiries": len(_LISTED_NONCALENDAR_EXPIRY),\n'
    diag_new = '            "reviewed_malformed_listing_dates": len(_LISTED_MALFORMED_LISTING_DATE),\n' + diag
    if text.count(diag) != 1:
        raise RuntimeError("listed diagnostics anchor drift")
    text = text.replace(diag, diag_new, 1)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: napoli_date_binding.py LISTED_PDF APPLICANT_PDF PARSER")
    listed, applicant, parser = map(Path, sys.argv[1:])
    audit(listed, applicant)
    patch_parser(parser)


if __name__ == "__main__":
    main()

"""Read-only structural census of the archived Reggio Calabria November originals."""
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
import re
from datetime import datetime

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import _record
from white_list_archive.publishing.public_contract import public_record
from white_list_archive.publishing.publication_handoff import records_digest

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for

PINS = (
    ("listed", "d185e63dcd0a603aec194ddc32593960cb72f183fdba120abd0d2dc6f9666b13", 281479),
    ("applicant", "fa15cb7cbd4c17d94a05c374c2e69b073648122197aef866b7ed6ea95a969764", 392393),
)


def content_profile(cells, population, counters):
    """Summarise the source fields without emitting any row values."""
    fields = (
        ("name", "office", "secondary_office", "identifier", "listing_date",
         "expiry_date", "activities", "outcome")
        if population == "listed"
        else ("name", "office", "secondary_office", "identifier", "activities",
              "application_date", "outcome")
    )
    if len(cells) != len(fields) + 1:
        raise ValueError("Unexpected data row width")
    for field, value in zip(fields, cells[1:], strict=True):
        if not value:
            counters[f"{field}_blank"] += 1
        elif field.endswith("_date"):
            counters[f"{field}_{date_shape(value)}"] += 1
        elif field == "identifier":
            shape = "standard_shape" if re.fullmatch(r"(?:[0-9]{11}|[A-Za-z0-9]{16})", value) else "other_shape"
            counters[f"identifier_{shape}"] += 1
        elif field == "outcome":
            outcome = " ".join(value.casefold().split())
            if population == "applicant":
                label = "instruction" if outcome in {"istruttoria", "istrutoria", "istruttorria"} else "other"
            else:
                label = "renewal_or_update" if (
                    "aggiornamento in corso" in outcome or
                    ("istruttoria" in outcome and any(x in outcome for x in ("rinnovo", "aggiornamento", "permanenza")))
                ) else "other"
            counters[f"outcome_{label}"] += 1


def date_shape(value):
    return "calendar_value" if source_date(value) else "needs_review"


def source_date(value):
    value = re.sub(r"\s*-\s*", "-", value.casefold())
    for italian, english in (("gen", "jan"), ("mag", "may"), ("giu", "jun"),
                             ("lug", "jul"), ("ago", "aug"), ("set", "sep"),
                             ("ott", "oct"), ("dic", "dec")):
        value = value.replace(f"-{italian}-", f"-{english}-")
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return parsed.date().isoformat()
    return ""


REVIEWED_STRUCTURE = json.loads('''{
    "listed": {
        "numbered_rows_per_page": [
            3,
            10,
            8,
            10,
            9,
            8,
            6,
            6,
            7,
            9,
            8,
            5,
            5,
            9,
            8,
            10,
            7,
            6,
            5,
            10,
            6,
            6,
            6,
            7,
            8,
            6,
            10,
            6,
            8,
            6,
            8,
            10,
            8,
            7,
            8,
            7,
            6,
            10,
            9,
            8,
            9,
            7,
            5,
            11,
            8,
            7,
            12,
            7,
            7,
            8,
            12,
            8,
            7,
            7,
            9,
            9,
            5,
            8,
            8,
            9,
            8,
            5,
            5,
            8,
            9,
            10,
            7,
            7,
            8,
            9,
            6,
            2
        ],
        "number_only_ordinals": [
            544,
            546
        ],
        "header_like_rows": 1,
        "content_profile": {
            "activities_blank": 3,
            "expiry_date_blank": 13,
            "expiry_date_calendar_value": 529,
            "expiry_date_needs_review": 2,
            "identifier_other_shape": 14,
            "identifier_standard_shape": 530,
            "listing_date_calendar_value": 544,
            "office_blank": 1,
            "outcome_blank": 252,
            "outcome_other": 30,
            "outcome_renewal_or_update": 262,
            "secondary_office_blank": 539
        }
    },
    "applicant": {
        "numbered_rows_per_page": [
            3,
            9,
            12,
            9,
            10,
            8,
            10,
            9,
            12,
            8,
            7,
            10,
            12,
            10,
            11,
            12,
            6,
            10,
            10,
            5,
            6,
            8,
            6,
            9,
            4,
            5,
            8,
            13,
            10,
            8,
            8,
            14,
            12,
            8,
            7,
            10,
            7,
            10,
            6,
            10,
            8,
            10,
            9,
            8,
            8,
            13,
            7,
            9,
            13,
            11,
            5,
            8,
            9,
            14,
            10,
            10,
            6,
            12,
            9,
            12,
            7,
            12,
            10,
            9,
            11,
            6,
            7,
            13,
            10,
            9,
            8,
            9,
            11,
            9,
            8,
            11,
            5,
            5
        ],
        "number_only_ordinals": [],
        "header_like_rows": 78,
        "content_profile": {
            "activities_blank": 1,
            "application_date_calendar_value": 701,
            "application_date_needs_review": 2,
            "identifier_other_shape": 32,
            "identifier_standard_shape": 671,
            "office_blank": 2,
            "outcome_instruction": 701,
            "outcome_other": 2,
            "secondary_office_blank": 703
        }
    }
}''')


def candidate_record(cells, population, digest, page, row):
    ordinal, name, office, secondary, identifier, *values = cells
    listed = population == "listed"
    base = "https://prefettura.interno.gov.it"
    filename = ("white-list-foglio-unico-nuove-attivita-16-nov-2026.pdf" if listed
                else "elenco-richieste-iscrizioni-white-list-foglio-del-16-nov-2026.pdf")
    config = {
        "source_key": "reggio-calabria-listed" if listed else "reggio-calabria-applicants",
        "authority_key": "reggio-calabria",
        "authority_name": "Prefettura di Reggio Calabria",
        "register_key": "reggio-calabria-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": population,
        "reference_date": "2026-11-16",
        "sha256": digest,
        "source_page_url": base + "/it/prefetture/reggio-calabria/evidenza/white-list",
        "resource_url": base + "/sites/default/files/0/2026-11/" + filename,
    }
    fields = {"physical_locator": f"page {page} row {row}"}
    cues = Counter()
    content_profile(cells, population, cues)
    if listed:
        listing, expiry, activities, outcome = values
        status = ("listed" if not outcome else "renewal_update_in_progress"
                  if cues["outcome_renewal_or_update"] else "other_or_unknown")
        dates = {"listing_date": source_date(listing), "expiry_date": source_date(expiry),
                 "primary_date_label": "Data iscrizione"}
        fields.update(listing_date_raw_variants=[listing], expiry_date_raw_variants=[expiry] if expiry else [])
    else:
        activities, application, outcome = values
        status = "pending" if cues["outcome_instruction"] else "other_or_unknown"
        dates = {"application_date": source_date(application), "primary_date_label": "Data presentazione istanza"}
        fields["application_date_raw"] = application
    record = _record(config, int(ordinal), name=name, office=office, secondary=secondary,
                     identifier_raw=identifier, activities=[activities] if activities else [],
                     status=status, outcome_raw=outcome, source_fields=fields, **dates)
    record["identifiers"] = [identifier.upper()] if cues["identifier_standard_shape"] else []
    record["parser_name"] = "reggio_calabria_november_candidate"
    record["parser_version"] = "1"
    return public_record(record)


def census(raw, population, digest):
    tables_per_page = []
    numbered_rows_per_page = []
    widths = Counter()
    numbers = Counter()
    number_only = 0
    profile = Counter()
    records = []
    number_only_ordinals = []
    header_like_rows = 0
    other_nonblank_rows = 0
    with pdfplumber.open(BytesIO(raw)) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            tables = page.find_tables()
            tables_per_page.append(len(tables))
            start = numbers.total()
            for table in tables:
                for row_number, row in enumerate(table.extract(), 1):
                    cells = [str(cell or "").strip() for cell in row]
                    if not any(cells):
                        continue
                    if cells[0].isascii() and cells[0].isdecimal():
                        numbers[int(cells[0])] += 1
                        widths[len(cells)] += 1
                        if any(cells[1:]):
                            content_profile(cells, population, profile)
                            records.append(candidate_record(cells, population, digest, page_number, row_number))
                        else:
                            number_only += 1
                            number_only_ordinals.append(int(cells[0]))
                    else:
                        other_nonblank_rows += 1
                        label = ' '.join(cells).casefold()
                        header_like_rows += 'ragione sociale' in label and ('codice fiscale' in label or 'partita iva' in label)
            numbered_rows_per_page.append(numbers.total() - start)
            page.close()
    summary = {
        "pages": len(tables_per_page),
        "tables_per_page": tables_per_page,
        "numbered_rows_per_page": numbered_rows_per_page,
        "numbered_rows": numbers.total(),
        "duplicate_numbers": numbers.total() - len(numbers),
        "min_number": min(numbers, default=None),
        "max_number": max(numbers, default=None),
        "number_only_rows": number_only,
        "number_only_ordinals": number_only_ordinals,
        "header_like_rows": header_like_rows,
        "content_profile": profile,
        "numbered_row_widths": widths,
        "other_nonblank_table_rows": other_nonblank_rows,
    }
    expected = REVIEWED_STRUCTURE[population]
    if ({key: summary[key] for key in expected} != expected
            or set(numbers) != set(range(1, sum(expected["numbered_rows_per_page"]) + 1))
            or numbers.total() != len(numbers)
            or tables_per_page != [1] * len(expected["numbered_rows_per_page"])
            or other_nonblank_rows != expected["header_like_rows"]):
        raise ValueError("November source does not match independently verified census")
    summary["candidate_observations"] = len(records)
    summary["candidate_status_counts"] = Counter(record["source_status"] for record in records)
    summary["candidate_records_sha256"] = records_digest(records)
    return summary


def main():
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    results = []
    for population, digest, size in PINS:
        result = {"population": population, "sha256": digest, "bytes": size}
        try:
            raw = store.read_digest_verified(digest)
            if len(raw) != size or sha256(raw).hexdigest() != digest:
                raise ValueError("Archived original differs from pin")
            result["verified_bytes"] = True
            result["structure"] = census(raw, population, digest)
        except Exception as exc:
            result["error_type"] = type(exc).__name__
        results.append(result)
    print(json.dumps({"source_reference": "2026-11-16", "review_only": True, "results": results},
                     sort_keys=True))
    return int(any("structure" not in result for result in results))


if __name__ == "__main__":
    raise SystemExit(main())

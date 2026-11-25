"""Read-only review of two archived Cagliari pairs; no edition or privacy approval."""
from collections import Counter
from datetime import date
from hashlib import sha256
from io import BytesIO
import json
import re

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import _clean
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for

PINS = (
    ("2026-11-08", "listed", "c2dd36617483db942460fa3227773bd3c84fb59eeab8a2ffc8d6ab97f3a32650", 784589),
    ("2026-11-08", "applicant", "0942b2905289fefcc04158e089e622982dedbb8c0adfab5df8137d15c1426c9a", 95986),
    ("2026-11-15", "listed", "6fe9d00a1f5be8df941e8658d1b690f48627d3d44a8251e5088cb69e6ed2aed9", 1507208),
    ("2026-11-15", "applicant", "d08bf025064b6dd4d5cdb87ede9c015e2b62aa84ddf99b24d9ee12c19fa79783", 110636),
)
MAX_BYTES, MAX_PAGES, MAX_ROWS = 5_000_000, 150, 20_000
SECTION = re.compile(r"sez\.\s*0?(10|[1-9])", re.I)


def date_shape(value):
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
        return False
    d, m, y = map(int, value.split("/"))
    try:
        date(y, m, d)
    except ValueError:
        return False
    return True


def profile_pages(pages, filename_date):
    counts, widths, sectors = Counter(), Counter(), Counter()
    groups = set()
    group_sectors = set()
    group_notes = {}
    applicant_ordinals = Counter()
    applicant_shape_evidence = Counter()
    residual_shapes = Counter()
    listed_status_clues = Counter()
    day = date.fromisoformat(filename_date)
    marker = day.strftime("%d/%m/%Y")
    for page in pages:
        counts["pages"] += 1
        if counts["pages"] > MAX_PAGES:
            raise ValueError("Page limit exceeded")
        page_text = " ".join((page.extract_text() or "").casefold().split())
        counts["filename_date_marker_pages"] += marker in page_text
        # Heading clues are independent of the filename and row shape.
        counts["applicant_title_clue_pages"] += "imprese richiedenti" in page_text
        counts["listed_title_clue_pages"] += "imprese iscritte" in page_text
        counts["registration_expiry_label_pages"] += (
            "data iscrizione" in page_text and "data scadenza" in page_text)
        for table in page.extract_tables():
            for row in table or []:
                counts["physical_rows"] += 1
                if counts["physical_rows"] > MAX_ROWS:
                    raise ValueError("Row limit exceeded")
                cells = [_clean(v) for v in row]
                widths[str(len(cells))] += 1
                if not any(cells):
                    counts["blank_rows"] += 1
                    continue
                if len(cells) == 9 and cells[0].isdigit() and SECTION.fullmatch(cells[1]):
                    counts["listed_shaped_rows"] += 1
                    sectors[SECTION.fullmatch(cells[1]).group(1)] += 1
                    counts["listed_rows_invalid_date"] += not all(date_shape(v) for v in cells[6:8])
                    counts["listed_rows_with_identifier_syntax"] += bool(re.fullmatch(r"\d{11}|[A-Za-z0-9]{16}", cells[5]))
                    # Exclude ordinal and sector, retain every other cell for a
                    # conservative shape-group count, not distinct entities.
                    key = tuple(v.casefold() for v in cells[2:])
                    groups.add(key)
                    group_sector = (key, SECTION.fullmatch(cells[1]).group(1))
                    counts["repeated_same_section_rows"] += group_sector in group_sectors
                    group_sectors.add(group_sector)
                    note = " ".join(cells[-1].casefold().split())
                    note_class = ("blank_note" if not note else
                        "explicit_update_in_progress" if note == "aggiornamento in corso"
                        else "other_note_requires_review")
                    listed_status_clues[note_class] += 1
                    group_notes[key] = note_class
                elif len(cells) in (7, 8) and cells[0].isdigit():
                    counts["applicant_shaped_rows"] += 1
                    counts["applicant_rows_invalid_date"] += not date_shape(cells[-2])
                    counts["applicant_rows_istruttoria_clue"] += "istruttoria" in cells[-1].casefold()
                    counts["applicant_rows_with_identifier_syntax"] += bool(re.fullmatch(r"\d{11}|[A-Za-z0-9]{16}", cells[-4]))
                    applicant_ordinals[int(cells[0])] += 1
                    # Applicant-shaped rows can occur in the listed attachment.
                    # Distinguish the legacy parser's actual outcome predicate
                    # and date/request clues without promoting either population.
                    outcome = "istruttoria" in cells[-1].casefold()
                    valid_date = date_shape(cells[-2])
                    applicant_shape_evidence[
                        "legacy_outcome_and_calendar_date" if outcome and valid_date
                        else "legacy_outcome_invalid_date" if outcome
                        else "no_legacy_outcome_clue"] += 1
                    tokens = [t.strip().upper() for t in cells[-3].split(",") if t.strip()]
                    applicant_shape_evidence["request_tokens_blank" if not tokens else
                        "request_tokens_known_roman" if all(t in {
                            "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"
                        } for t in tokens) else "request_tokens_require_review"] += 1
                else:
                    counts["unclassified_rows"] += 1
                    # Finite aggregate evidence only; residuals remain unclassified.
                    tokens = {" ".join(v.casefold().split()) for v in cells if v}
                    labels = {"ragione sociale", "denominazione", "codice fiscale",
                              "partita iva", "sede legale", "data iscrizione",
                              "data scadenza iscrizione", "data istanza", "esito",
                              "sezione", "note"}
                    n = sum(bool(v) for v in cells)
                    role = ("multiple_known_header_labels" if len(tokens & labels) >= 2
                            else "single_nonblank_cell" if n == 1 else "other_multicell")
                    residual_shapes[role] += 1
    keys = ("blank_rows", "listed_shaped_rows", "applicant_shaped_rows", "unclassified_rows")
    if not counts["physical_rows"] or sum(counts[k] for k in keys) != counts["physical_rows"]:
        raise ValueError("Unreconciled physical census")
    if (sum(residual_shapes.values()) != counts["unclassified_rows"] or
            sum(listed_status_clues.values()) != counts["listed_shaped_rows"]):
        raise ValueError("Unreconciled aggregate clues")
    return {"counts": {k: counts[k] for k in (
        "pages", "filename_date_marker_pages", "applicant_title_clue_pages",
        "listed_title_clue_pages", "registration_expiry_label_pages", "physical_rows",
        *keys, "listed_rows_invalid_date", "listed_rows_with_identifier_syntax",
        "applicant_rows_invalid_date", "applicant_rows_istruttoria_clue",
        "applicant_rows_with_identifier_syntax", "repeated_same_section_rows")},
        "residual_shape_clues_not_classifications": dict(residual_shapes),
        "listed_note_clues_not_statuses": dict(listed_status_clues),
        "listed_group_note_clues_not_statuses": dict(Counter(group_notes.values())),
        "applicant_shape_evidence_not_classifications": dict(applicant_shape_evidence),
        "applicant_repeated_ordinal_rows": sum(n - 1 for n in applicant_ordinals.values()),
        "widths": dict(widths), "listed_sector_clues": dict(sectors),
        "listed_shape_groups_not_entities": len(groups),
        "logical_record_census_approved": False}


def profile_pdf(raw, filename_date):
    if not raw.startswith(b"%PDF-") or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid bounded PDF")
    with pdfplumber.open(BytesIO(raw)) as pdf:
        return profile_pages(pdf.pages, filename_date)


def audit(store, pins=PINS, scanner=profile_pdf):
    dates = {p[0] for p in pins}
    if len(pins) != 2 * len(dates) or not dates or any(
            {p[1] for p in pins if p[0] == d} != {"listed", "applicant"} for d in dates):
        raise ValueError("Complete pairs required")
    result = []
    for clue, population, digest, size in pins:
        item = {"filename_date_clue": clue, "population_clue": population,
                "original_sha256": digest, "expected_bytes": size, "source_bytes_verified": False}
        try:
            raw = store.read_digest_verified(digest)
            if len(raw) != size or sha256(raw).hexdigest() != digest:
                raise ValueError("Original identity mismatch")
            item["source_bytes_verified"] = True
            item["physical_profile"] = scanner(raw, clue)
        except Exception as exc:
            item["error_type"] = type(exc).__name__
            item["review_code"] = "source_review_incomplete"
        result.append(item)
    return {"scope": "cagliari_november_archived_pairs_source_only",
            "originals_expected": len(pins),
            "originals_sha_verified": sum(x["source_bytes_verified"] for x in result),
            "physical_profiles_completed": sum("physical_profile" in x for x in result),
            "official_edition_date_approved": False, "source_edition_approved": False,
            "privacy_approved": False, "public_release_eligible": False,
            "postgresql_writes": 0, "public_promotions": 0, "results": result}


def main():
    try:
        config = StoreConfig.from_env()
        report = audit(EvidenceStore(client_for(config), config))
    except Exception:
        report = {"review_code": "protected_source_read_unavailable",
                  "source_edition_approved": False, "privacy_approved": False,
                  "public_release_eligible": False, "originals_sha_verified": 0}
    print(json.dumps(report, sort_keys=True))
    return int(report.get("physical_profiles_completed", 0) != len(PINS))


if __name__ == "__main__":
    raise SystemExit(main())

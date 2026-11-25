"""Bounded source-only Chieti November DOC audit, no source edition approval."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import html
import json
import re
import subprocess
import xml.etree.ElementTree as ET

from white_list_archive.parsers.chieti_legacy_doc import (
    _EXPECTED_ACTIVITY_LABELS, _source_date, _source_identifiers,
)
from white_list_archive.parsers.multi_prefecture_tables import _clean
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for

PINS = (
    ("listed", "3d903b25d7e4dbf9bf718ff9701fb4bd1d082683f324e52779ac7eb09f321d69", 2586624),
    ("applicant", "057cbd46819c49711a6c76258a9d969132c6a7306dc8637ffbc2e7d71f340e71", 543232),
)
MAX_BYTES = 5_000_000
MAX_XML = 20_000_000
MAX_ROWS = 20_000
OLE = bytes.fromhex("d0cf11e0a1b11ae1")


def _note_clue(raw, population):
    """Fixed vocabulary only: no status or identity inference, no raw output."""
    value = _clean(raw).casefold()
    if not value:
        return "blank"
    flags = {
        "expiry_wording": "iscrizione scaduta" in value,
        "cancellation_wording": "cancellazione" in value,
        "adverse_wording": "respinta" in value or "interditt" in value,
        "archive_transfer_wording": "archiviat" in value or "trasferita per competenza" in value,
        "procedure_wording": "istrutt" in value or "istritt" in value or "rinnovo" in value,
    }
    matched = [key for key, present in flags.items() if present]
    if len(matched) > 1:
        return "overlapping_wording_requires_review"
    if not matched:
        return "unmapped_wording_requires_review"
    return matched[0]


def _date_clue(raw):
    if not _clean(raw):
        return "blank"
    return "parsed" if _source_date(raw) else "nonblank_unparsed"


def _table_sector_clues(root):
    """Map only direct chapter paragraph tables to exact reviewed headings."""
    known = {label: str(i + 1) for i, label in enumerate(_EXPECTED_ACTIVITY_LABELS)}
    result = {}
    for chapter in root.findall(".//chapter"):
        sector = None
        for para in chapter.findall("./para"):
            tables = para.findall(".//informaltable")
            if tables:
                for table in tables:
                    result[id(table)] = sector
                continue
            value = _clean("".join(para.itertext()))
            if not value:
                continue
            heading = re.sub(r"^ATTIVITA[’']:\s*", "", value, flags=re.I)
            # Reset on an unrecognised heading or intervening text: do not
            # inherit an earlier sector across ambiguous source content.
            sector = known.get(heading)
    return result


def profile_docbook(docbook, population):
    if len(docbook) > MAX_XML:
        raise ValueError("Output limit")
    counts, widths = Counter(), Counter()
    groups = set()
    group_sectors = {}
    sector_rows, notes, date_clues = Counter(), Counter(), Counter()
    repeated_same_sector_rows = 0
    if population == "listed":
        xml = re.sub(r'<!DOCTYPE book PUBLIC.*?docbookx\.dtd">\s*', "", docbook, flags=re.S)
        if re.search(r"<!DOCTYPE|<!ENTITY", xml, re.I):
            raise ValueError("Unexpected XML declaration")
        root = ET.fromstring(xml)
        tables = root.findall(".//informaltable")
        table_sectors = _table_sector_clues(root)
        counts["tables"] = len(tables)
        if not tables:
            return {"counts": dict(counts), "review_code": "unresolved_table_layout", "logical_census_approved": False}
        for table in tables:
            for row in table.findall(".//row"):
                cells = [_clean("".join(entry.itertext())) for entry in row.findall("./entry")]
                counts["physical_rows"] += 1
                if counts["physical_rows"] > MAX_ROWS:
                    raise ValueError("Row limit")
                widths[str(len(cells))] += 1
                if not any(cells):
                    counts["empty"] += 1
                elif len(cells) == 6 and cells[0].casefold().startswith("ragione sociale"):
                    counts["header_clue"] += 1
                elif len(cells) == 6:
                    counts["six_column_data_clue"] += 1
                    counts["blank_name"] += not cells[0]
                    counts["identifier_syntax"] += bool(_source_identifiers(cells[2]))
                    counts["listing_date_unparsed"] += not bool(_source_date(cells[3]))
                    counts["expiry_date_unparsed"] += not bool(_source_date(cells[4]))
                    counts["nonblank_note"] += bool(cells[5])
                    key = tuple(cells)
                    groups.add(key)
                    sector = table_sectors.get(id(table))
                    sector_rows[sector or "unresolved_heading"] += 1
                    observed = group_sectors.setdefault(key, set())
                    if sector is not None:
                        repeated_same_sector_rows += sector in observed
                        observed.add(sector)
                else:
                    counts["unclassified"] += 1
        counts["exact_cell_groups_not_entities"] = len(groups)
        for key in groups:
            notes[_note_clue(key[5], population)] += 1
            date_clues["listing:" + _date_clue(key[3])] += 1
            date_clues["expiry:" + _date_clue(key[4])] += 1
        if sum(sector_rows.values()) != counts["six_column_data_clue"]:
            raise ValueError("Unreconciled sector clues")
        if sum(notes.values()) != len(groups) or sum(date_clues.values()) != 2 * len(groups):
            raise ValueError("Unreconciled grouped diagnostics")
        if counts["physical_rows"] != sum(counts[k] for k in ("empty", "header_clue", "six_column_data_clue", "unclassified")):
            raise ValueError("Unreconciled physical rows")
    elif population == "applicant":
        paragraphs = re.findall(r"<para>(.*?)</para>", docbook, flags=re.S)
        candidates = [p for p in paragraphs if "\x07" in p]
        counts["bel_paragraphs"] = len(candidates)
        if len(candidates) != 1:
            return {"counts": dict(counts), "review_code": "unresolved_bel_layout", "logical_census_approved": False}
        raw = html.unescape(re.sub(r"<[^>]+>", "", candidates[0]))
        tokens = [_clean(x) for x in raw.split("\x07")]
        if tokens and tokens[-1] == "" and (len(tokens) - 1) % 8 == 0:
            tokens.pop()
        counts["tokens"] = len(tokens)
        counts["residual_tokens"] = len(tokens) % 8
        counts["eight_token_blocks"] = len(tokens) // 8
        if counts["eight_token_blocks"] > MAX_ROWS:
            raise ValueError("Block limit")
        header = ["Ragione Sociale", "Sede legale", "Sede secondaria con rappresentanza stabile in Italia",
                  "Codice fiscale Partita IVA", "Attività per cui è richiesta l’iscrizione",
                  "Data di presentazione dell’istanza", "Esito", ""]
        counts["exact_legacy_header"] = int(tokens[:8] == header)
        if not counts["exact_legacy_header"]:
            return {"counts": dict(counts), "review_code": "unresolved_bel_header", "logical_census_approved": False}
        for i in range(8, len(tokens) - len(tokens) % 8, 8):
            block = tokens[i:i+8]
            if block[-1] or not block[0]:
                counts["unclassified_blocks"] += 1
                continue
            counts["seven_column_data_clue"] += 1
            counts["identifier_syntax"] += bool(_source_identifiers(block[3]))
            counts["application_date_unparsed"] += not bool(_source_date(block[5]))
            counts["nonblank_outcome"] += bool(block[6])
            notes[_note_clue(block[6], population)] += 1
            date_clues["application:" + _date_clue(block[5])] += 1
        if counts["eight_token_blocks"] != 1 + counts["seven_column_data_clue"] + counts["unclassified_blocks"]:
            raise ValueError("Unreconciled blocks")
        if sum(notes.values()) != counts["seven_column_data_clue"] or sum(date_clues.values()) != counts["seven_column_data_clue"]:
            raise ValueError("Unreconciled applicant diagnostics")
    else:
        raise ValueError("Unexpected population")
    profile = {"counts": dict(counts), "widths": dict(widths), "logical_census_approved": False,
               "note_clues_not_statuses": dict(notes), "date_clues_not_edition_dates": dict(date_clues)}
    if population == "listed":
        profile["sector_row_clues_not_approved"] = dict(sector_rows)
        profile["same_known_sector_repeated_rows"] = repeated_same_sector_rows
        profile["groups_without_known_sector"] = sum(not value for value in group_sectors.values())
        profile["group_identifier_syntax_count"] = sum(bool(_source_identifiers(key[2])) for key in groups)
        profile["sector_group_count"] = sum(len(value) for value in group_sectors.values())
    if population == "listed" and (not counts["six_column_data_clue"] or counts["unclassified"]):
        profile["review_code"] = "unresolved_listed_rows"
    if population == "applicant" and (not counts["seven_column_data_clue"] or counts["residual_tokens"] or counts["unclassified_blocks"]):
        profile["review_code"] = "unresolved_applicant_blocks"
    return profile


def profile_doc(raw, population):
    if not raw.startswith(OLE) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid bounded OLE")
    with TemporaryDirectory() as directory:
        path = Path(directory) / "original.doc"
        path.write_bytes(raw)
        process = subprocess.run(["antiword", "-x", "db", str(path)], capture_output=True, timeout=60, check=False)
        if process.returncode or len(process.stdout) > MAX_XML:
            raise ValueError("Conversion failed or exceeded limit")
        return profile_docbook(process.stdout.decode("utf-8", "replace"), population)


def audit(store, pins=PINS, scanner=profile_doc):
    if len(pins) != 2 or {p for p, _, _ in pins} != {"listed", "applicant"}:
        raise ValueError("Complete pair required")
    result = []
    for pop, digest, size in pins:
        item = {"population_clue": pop, "original_sha256": digest, "expected_bytes": size,
                "filename_date_clue": "2026-11-20", "source_bytes_verified": False}
        try:
            raw = store.read_digest_verified(digest)
            if len(raw) != size or sha256(raw).hexdigest() != digest:
                raise ValueError("Original identity mismatch")
            item["source_bytes_verified"] = True
            item["physical_profile"] = scanner(raw, pop)
        except Exception as exc:
            item["error_type"] = type(exc).__name__
            item["review_code"] = "source_review_incomplete"
        result.append(item)
    return {"scope": "chieti_november20_archived_pair_source_only", "results": result,
            "originals_sha_verified": sum(x["source_bytes_verified"] for x in result),
            "physical_profiles_returned": sum("physical_profile" in x for x in result),
            "structural_profiles_without_residual_flags": sum(
                "physical_profile" in x and "review_code" not in x["physical_profile"] for x in result),
            "official_edition_date_approved": False, "privacy_approved": False,
            "source_edition_approved": False, "public_release_eligible": False,
            "postgresql_writes": 0, "public_promotions": 0}


def main():
    try:
        config = StoreConfig.from_env()
        result = audit(EvidenceStore(client_for(config), config))
    except Exception:
        result = {"review_code": "protected_source_read_unavailable", "source_edition_approved": False,
                  "privacy_approved": False, "public_release_eligible": False}
    print(json.dumps(result, sort_keys=True))
    return int(result.get("structural_profiles_without_residual_flags", 0) != 2)


if __name__ == "__main__":
    raise SystemExit(main())

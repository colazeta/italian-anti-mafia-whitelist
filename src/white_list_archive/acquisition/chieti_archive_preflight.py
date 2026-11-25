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

from white_list_archive.parsers.chieti_legacy_doc import _source_date, _source_identifiers
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


def profile_docbook(docbook, population):
    if len(docbook) > MAX_XML:
        raise ValueError("Output limit")
    counts, widths = Counter(), Counter()
    groups = set()
    if population == "listed":
        xml = re.sub(r'<!DOCTYPE book PUBLIC.*?docbookx\.dtd">\s*', "", docbook, flags=re.S)
        if re.search(r"<!DOCTYPE|<!ENTITY", xml, re.I):
            raise ValueError("Unexpected XML declaration")
        root = ET.fromstring(xml)
        tables = root.findall(".//informaltable")
        counts["tables"] = len(tables)
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
                    groups.add(tuple(cells))
                else:
                    counts["unclassified"] += 1
        counts["exact_cell_groups_not_entities"] = len(groups)
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
        if counts["eight_token_blocks"] != 1 + counts["seven_column_data_clue"] + counts["unclassified_blocks"]:
            raise ValueError("Unreconciled blocks")
    else:
        raise ValueError("Unexpected population")
    return {"counts": dict(counts), "widths": dict(widths), "logical_census_approved": False}


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
    return int(result.get("physical_profiles_returned", 0) != 2)


if __name__ == "__main__":
    raise SystemExit(main())

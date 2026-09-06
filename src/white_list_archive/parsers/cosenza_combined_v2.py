from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

WS_RE = re.compile(r"\s+")
DATE_RE = re.compile(r"(?P<left>\()?\b(?P<date>\d{2}/\d{2}/\d{4})\b(?P<right>\))?")
NUMERIC_11_RE = re.compile(r"\b\d{11}\b")
PLAIN_DATE_RE = re.compile(r"(?<!\()\b\d{2}/\d{2}/\d{4}\b(?!\))")

PARSER_NAME = "white_list_archive.parsers.cosenza_combined_v2"
PARSER_VERSION = "2"
SCHEMA_FINGERPRINT = "fbb124c5a43d26bef93316844b3021096060f7ed9d2cc0f8f6081f6df935dc97"

COLUMN_RANGES = {
    "operator_name": (0.0, 175.0),
    "registered_office": (175.0, 265.0),
    "secondary_office": (265.0, 297.0),
    "identifier": (297.0, 348.0),
    "requested_activities": (348.0, 468.0),
    "application_date": (468.0, 516.0),
    "outcome": (516.0, 999.0),
}

PARSER_CONFIGURATION = json.dumps(
    {
        "schema_fingerprint": SCHEMA_FINGERPRINT,
        "line_y_tolerance": 4.0,
        "column_ranges": COLUMN_RANGES,
        "row_start_rule": (
            "name + legal-office + (plain application date OR 11-digit numeric identifier "
            "with application/outcome context); identifier validity is not required"
        ),
        "principle": "lossless-first source-column parsing; no canonical entity/legal-effect assertions",
    },
    sort_keys=True,
    ensure_ascii=False,
)
PARSER_CONFIGURATION_HASH = hashlib.sha256(PARSER_CONFIGURATION.encode("utf-8")).hexdigest()

OUTPUT_COLUMNS = [
    "row_ordinal",
    "operator_name_raw",
    "operator_name_normalised",
    "registered_office_raw",
    "secondary_office_raw",
    "identifier_field_raw",
    "identifiers_json",
    "requested_activities_raw",
    "requested_activities_json",
    "application_date_field_raw",
    "application_dates_json",
    "outcome_raw",
    "outcome_json",
    "source_status",
    "observed_listing_date",
    "observed_expiry_date",
    "record_hash",
    "mention_key",
    "raw_block",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalise_ws(value: str) -> str:
    return WS_RE.sub(" ", value).strip()


def normalise_name(value: str) -> str:
    value = value.upper().replace("’", "'").replace("‘", "'")
    return _normalise_ws(value).strip(" .")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _column_for(x_center: float) -> str | None:
    for column, (lower, upper) in COLUMN_RANGES.items():
        if lower <= x_center < upper:
            return column
    return None


def _bbox_words(pdf: Path) -> list[dict[str, object]]:
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as handle:
        output = Path(handle.name)
    try:
        subprocess.run(
            ["pdftotext", "-bbox-layout", str(pdf), str(output)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        root = ET.parse(output).getroot()
    finally:
        output.unlink(missing_ok=True)

    ns = {"x": "http://www.w3.org/1999/xhtml"}
    words: list[dict[str, object]] = []
    for page_number, page in enumerate(root.findall(".//x:page", ns), start=1):
        for word in page.findall(".//x:word", ns):
            x0 = float(word.attrib["xMin"])
            x1 = float(word.attrib["xMax"])
            y0 = float(word.attrib["yMin"])
            y1 = float(word.attrib["yMax"])
            words.append(
                {
                    "page": page_number,
                    "x0": x0,
                    "x1": x1,
                    "xc": (x0 + x1) / 2,
                    "y0": y0,
                    "y1": y1,
                    "yc": (y0 + y1) / 2,
                    "text": "".join(word.itertext()),
                }
            )
    return words


def _lines(words: list[dict[str, object]], tolerance: float = 4.0) -> list[dict[str, object]]:
    by_page: dict[int, list[dict[str, object]]] = {}
    for word in words:
        by_page.setdefault(int(word["page"]), []).append(word)

    output: list[dict[str, object]] = []
    for page_number in sorted(by_page):
        page_words = sorted(
            by_page[page_number], key=lambda word: (float(word["yc"]), float(word["x0"]))
        )
        groups: list[dict[str, object]] = []
        for word in page_words:
            if not groups or abs(float(groups[-1]["yc"]) - float(word["yc"])) > tolerance:
                groups.append({"page": page_number, "yc": float(word["yc"]), "words": [word]})
            else:
                group_words = groups[-1]["words"]
                assert isinstance(group_words, list)
                group_words.append(word)
                groups[-1]["yc"] = sum(float(item["yc"]) for item in group_words) / len(group_words)
        for group in groups:
            group_words = group["words"]
            assert isinstance(group_words, list)
            group_words.sort(key=lambda word: float(word["x0"]))
        output.extend(groups)
    return output


def _line_column_text(line: dict[str, object], column: str) -> str:
    words = line["words"]
    assert isinstance(words, list)
    return " ".join(
        str(word["text"])
        for word in words
        if _column_for(float(word["xc"])) == column
    ).strip()


def _is_row_start(line: dict[str, object]) -> bool:
    name = _line_column_text(line, "operator_name")
    legal_office = _line_column_text(line, "registered_office")
    identifier = _line_column_text(line, "identifier")
    application = _line_column_text(line, "application_date")
    outcome = _line_column_text(line, "outcome")
    if not name or not legal_office:
        return False
    plain_application_date = bool(PLAIN_DATE_RE.search(application))
    numeric_11_with_row_context = bool(
        NUMERIC_11_RE.search(identifier) and (application or outcome)
    )
    return plain_application_date or numeric_11_with_row_context


def _field_lines(segment: list[dict[str, object]], column: str) -> list[str]:
    values = []
    for line in segment:
        text = _line_column_text(line, column)
        if text:
            values.append(text)
    return values


def _parse_identifiers(lines: list[str]) -> tuple[str, list[dict[str, object]]]:
    raw = "\n".join(lines).strip()
    parsed: list[dict[str, object]] = []
    pending: list[str] = []
    source_hint: str | None = None

    def flush_pending() -> None:
        nonlocal pending
        if not pending:
            return
        compact = "".join(pending).upper()
        if (
            len(compact) == 16
            and re.fullmatch(r"[A-Z0-9]{16}", compact)
            and re.search(r"[A-Z]", compact)
        ):
            parsed.append(
                {
                    "raw_value": compact,
                    "shape": "16_char_alphanumeric",
                    "candidate_schemes": ["IT_CF"],
                    "scheme_assertion": "IT_CF_CANDIDATE",
                    "source_hint": source_hint,
                }
            )
        else:
            parsed.append(
                {
                    "raw_value": compact,
                    "shape": "unparsed_alphanumeric",
                    "candidate_schemes": [],
                    "scheme_assertion": "UNKNOWN",
                    "source_hint": source_hint,
                }
            )
        pending = []

    for line in lines:
        token = "".join(line.split()).upper()
        if not token:
            continue
        if token in {"C.F.", "C.F", "CF"}:
            flush_pending()
            source_hint = "CF"
            continue
        if re.fullmatch(r"\d+", token):
            flush_pending()
            if len(token) == 11:
                if source_hint == "CF":
                    candidates = ["IT_CF"]
                    assertion = "IT_CF_CANDIDATE"
                else:
                    candidates = ["IT_VAT", "IT_CF"]
                    assertion = "UNRESOLVED_CF_OR_VAT"
                shape = "11_digit_numeric"
            else:
                candidates = []
                assertion = "UNKNOWN"
                shape = f"numeric_{len(token)}_digits"
            parsed.append(
                {
                    "raw_value": token,
                    "shape": shape,
                    "candidate_schemes": candidates,
                    "scheme_assertion": assertion,
                    "source_hint": source_hint,
                }
            )
            source_hint = None
            continue
        if re.fullmatch(r"[A-Z0-9]+", token) and re.search(r"[A-Z]", token):
            pending.append(token)
            if len("".join(pending)) >= 16:
                flush_pending()
                source_hint = None
            continue
        flush_pending()
        parsed.append(
            {
                "raw_value": token,
                "shape": "unparsed",
                "candidate_schemes": [],
                "scheme_assertion": "UNKNOWN",
                "source_hint": source_hint,
            }
        )
        source_hint = None
    flush_pending()
    return raw, parsed


def _parse_dates(raw: str) -> list[dict[str, object]]:
    return [
        {
            "raw_value": match.group(0),
            "date": match.group("date"),
            "parenthesized": bool(match.group("left") and match.group("right")),
        }
        for match in DATE_RE.finditer(raw)
    ]


def _parse_outcome(raw: str) -> dict[str, object]:
    normalised = _normalise_ws(raw)
    upper = normalised.upper()
    if "INSERITO NELLE LISTE IN DATA" in upper:
        status = "listed"
    elif "RICHIESTA DI RINNOVO" in upper:
        status = (
            "renewal_update_in_progress"
            if "AGGIORNAMENTO IN CORSO" in upper
            else "renewal_requested"
        )
    elif "IN ISTRUTTORIA" in upper:
        status = "pending"
    elif "DINIEG" in upper or "RIGETT" in upper:
        status = "rejected_or_denied"
    elif "CANCELLA" in upper:
        status = "cancellation_related"
    else:
        status = "other_or_unknown"

    listing_match = re.search(
        r"INSERITO\s+NELLE\s+LISTE\s+IN\s+DATA\s+(\d{2}/\d{2}/\d{4})",
        upper,
    )
    expiry_match = re.search(r"SCADENZA\s+(\d{2}/\d{2}/\d{4})", upper)
    return {
        "status": status,
        "observed_listing_date": listing_match.group(1) if listing_match else None,
        "observed_expiry_date": expiry_match.group(1) if expiry_match else None,
        "renewal_requested": "RICHIESTA DI RINNOVO" in upper,
        "update_in_progress": "AGGIORNAMENTO IN CORSO" in upper,
        "dates": _parse_dates(normalised),
    }


def parse_pdf(pdf: Path) -> list[dict[str, object]]:
    lines = _lines(_bbox_words(pdf))
    starts = [index for index, line in enumerate(lines) if _is_row_start(line)]
    records: list[dict[str, object]] = []

    for ordinal, start in enumerate(starts, start=1):
        end = starts[ordinal] if ordinal < len(starts) else len(lines)
        segment = lines[start:end]
        source_columns = {
            column: _field_lines(segment, column) for column in COLUMN_RANGES
        }

        name = _normalise_ws(" ".join(source_columns["operator_name"]))
        registered_office = _normalise_ws(" ".join(source_columns["registered_office"]))
        secondary_office = _normalise_ws(" ".join(source_columns["secondary_office"]))
        identifier_raw, identifiers = _parse_identifiers(source_columns["identifier"])
        activities_raw = _normalise_ws(" ".join(source_columns["requested_activities"]))
        activities = [
            part.strip() for part in re.split(r";\s*", activities_raw) if part.strip()
        ]
        application_raw = _normalise_ws(" ".join(source_columns["application_date"]))
        application_dates = _parse_dates(application_raw)
        outcome_raw = _normalise_ws(" ".join(source_columns["outcome"]))
        outcome = _parse_outcome(outcome_raw)

        raw_lines = []
        for line in segment:
            words = line["words"]
            assert isinstance(words, list)
            tokens = [
                str(word["text"])
                for word in words
                if _column_for(float(word["xc"])) is not None
            ]
            if tokens:
                raw_lines.append(" ".join(tokens))
        raw_block = "\n".join(raw_lines).strip()
        record_hash = hashlib.sha256(
            _normalise_ws(raw_block).encode("utf-8")
        ).hexdigest()
        mention_material = "\x1f".join(
            [identifier_raw.replace("\n", ""), normalise_name(name)]
        )
        mention_key = hashlib.sha256(mention_material.encode("utf-8")).hexdigest()

        records.append(
            {
                "row_ordinal": ordinal,
                "operator_name_raw": name,
                "operator_name_normalised": normalise_name(name),
                "registered_office_raw": registered_office,
                "secondary_office_raw": secondary_office,
                "identifier_field_raw": identifier_raw,
                "identifiers_json": json.dumps(identifiers, ensure_ascii=False),
                "requested_activities_raw": activities_raw,
                "requested_activities_json": json.dumps(activities, ensure_ascii=False),
                "application_date_field_raw": application_raw,
                "application_dates_json": json.dumps(
                    application_dates, ensure_ascii=False
                ),
                "outcome_raw": outcome_raw,
                "outcome_json": json.dumps(outcome, ensure_ascii=False),
                "source_status": outcome["status"],
                "observed_listing_date": outcome["observed_listing_date"] or "",
                "observed_expiry_date": outcome["observed_expiry_date"] or "",
                "record_hash": record_hash,
                "mention_key": mention_key,
                "raw_block": raw_block,
            }
        )
    return records


def _record_key(record: dict[str, object]) -> tuple[str, str]:
    return (
        str(record["identifier_field_raw"]).replace("\n", ""),
        str(record["operator_name_normalised"]),
    )


def _coverage(records: list[dict[str, object]]) -> dict[str, int]:
    return {
        "registered_office": sum(bool(record["registered_office_raw"]) for record in records),
        "secondary_office": sum(bool(record["secondary_office_raw"]) for record in records),
        "identifier_field": sum(bool(record["identifier_field_raw"]) for record in records),
        "requested_activities": sum(bool(record["requested_activities_raw"]) for record in records),
        "application_date_field": sum(bool(record["application_date_field_raw"]) for record in records),
        "outcome": sum(bool(record["outcome_raw"]) for record in records),
        "observed_listing_date": sum(bool(record["observed_listing_date"]) for record in records),
        "observed_expiry_date": sum(bool(record["observed_expiry_date"]) for record in records),
    }


def diff_records(
    before: list[dict[str, object]], after: list[dict[str, object]]
) -> dict[str, object]:
    before_by_key = {_record_key(record): record for record in before}
    after_by_key = {_record_key(record): record for record in after}
    common = set(before_by_key) & set(after_by_key)
    added = set(after_by_key) - set(before_by_key)
    disappeared = set(before_by_key) - set(after_by_key)

    transitions = Counter()
    content_changed = 0
    for key in common:
        old = before_by_key[key]
        new = after_by_key[key]
        if old["source_status"] != new["source_status"]:
            transitions[f"{old['source_status']}->{new['source_status']}"] += 1
        if old["record_hash"] != new["record_hash"]:
            content_changed += 1

    return {
        "records": {
            "before": len(before),
            "after": len(after),
            "net": len(after) - len(before),
        },
        "mention_observations": {
            "added": len(added),
            "disappeared": len(disappeared),
            "common": len(common),
            "record_content_changed": content_changed,
        },
        "source_status": {
            "before_counts": dict(
                Counter(str(record["source_status"]) for record in before)
            ),
            "after_counts": dict(
                Counter(str(record["source_status"]) for record in after)
            ),
            "changed_common_mentions": sum(transitions.values()),
            "transition_counts": dict(sorted(transitions.items())),
        },
        "structured_field_coverage": {
            "before": _coverage(before),
            "after": _coverage(after),
        },
        "interpretation_guardrails": [
            "row detection does not require a formally valid tax/VAT identifier",
            "all source columns remain source observations, not canonical administrative facts",
            "observed_listing_date and observed_expiry_date are parsed from source Esito wording",
            "appearance/disappearance is observational and is not an administrative registration/removal event",
        ],
    }


def _write_records(records: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("before_pdf", type=Path)
    parser.add_argument("after_pdf", type=Path)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/cosenza-v2")
    )
    args = parser.parse_args()

    started_at = _utc_now()
    before = parse_pdf(args.before_pdf)
    after = parse_pdf(args.after_pdf)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    before_path = args.output_dir / "before_records_v2.csv"
    after_path = args.output_dir / "after_records_v2.csv"
    _write_records(before, before_path)
    _write_records(after, after_path)

    diff = diff_records(before, after)
    (args.output_dir / "diff_summary_v2.json").write_text(
        json.dumps(diff, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    manifest = {
        "parser_name": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "processing_revision": os.environ.get("GITHUB_SHA", "local-unversioned"),
        "configuration_hash": PARSER_CONFIGURATION_HASH,
        "schema_fingerprint": SCHEMA_FINGERPRINT,
        "started_at": started_at,
        "completed_at": _utc_now(),
        "inputs": [
            {
                "label": "before",
                "pdf_sha256": _sha256_file(args.before_pdf),
                "record_count": len(before),
            },
            {
                "label": "after",
                "pdf_sha256": _sha256_file(args.after_pdf),
                "record_count": len(after),
            },
        ],
        "source_fields": [
            "Ragione sociale",
            "Sede legale",
            "Sede secondaria",
            "Codice fiscale/Partita IVA",
            "Attività per cui è richiesta l’iscrizione",
            "Data di presentazione dell’istanza",
            "Esito",
        ],
        "interpretation_guardrails": diff["interpretation_guardrails"],
    }
    (args.output_dir / "parse_manifest_v2.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(diff, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

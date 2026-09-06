from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

ID_RE = re.compile(r"(?<!\d)(\d{11})(?!\d)")
FIELD_SPLIT_RE = re.compile(r"\s{3,}")
WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class MentionRecord:
    row_ordinal: int
    identifier_raw: str
    operator_name_raw: str
    operator_name_normalised: str
    source_status: str
    record_hash: str
    mention_key: str
    raw_block: str


def normalise_name(value: str) -> str:
    value = value.upper().replace("’", "'").replace("‘", "'")
    return WS_RE.sub(" ", value).strip(" .")


def classify_source_status(block: str) -> str:
    """Classify only the source's Esito wording; this is not a legal-effect status."""
    upper = block.upper()
    if "INSERITO NELLE" in upper and "LISTE IN DATA" in upper:
        return "listed"
    if "RICHIESTA DI" in upper and "RINNOVO" in upper:
        if "AGGIORNAMENTO" in upper and "IN CORSO" in upper:
            return "renewal_update_in_progress"
        return "renewal_requested"
    if "IN ISTRUTTORIA" in upper:
        return "pending"
    if "DINIEG" in upper or "RIGETT" in upper:
        return "rejected_or_denied"
    if "CANCELLA" in upper:
        return "cancellation_related"
    return "other_or_unknown"


def parse_mentions(text: str) -> list[MentionRecord]:
    """Parse source mentions from pdftotext -layout output.

    The Cosenza combined list has one recurring row start containing an 11-digit
    source identifier. We intentionally parse mentions, not canonical entities:
    the source may reuse or publish ambiguous identifier values.
    """
    lines = text.splitlines()
    starts: list[tuple[int, str, str]] = []
    for line_number, line in enumerate(lines):
        match = ID_RE.search(line)
        if not match:
            continue
        left = line[: match.start()].strip()
        fields = FIELD_SPLIT_RE.split(left)
        if len(fields) < 2 or not fields[0].strip():
            # A continuation line can contain another numeric identifier. It is
            # not a new source row unless both name and legal-office columns exist.
            continue
        starts.append((line_number, match.group(1), fields[0].strip()))

    records: list[MentionRecord] = []
    for ordinal, (start, identifier, raw_name) in enumerate(starts, start=1):
        end = starts[ordinal][0] if ordinal < len(starts) else len(lines)
        raw_block = "\n".join(lines[start:end]).strip()
        normalised_block = WS_RE.sub(" ", raw_block).strip()
        name_normalised = normalise_name(raw_name)
        record_hash = hashlib.sha256(normalised_block.encode("utf-8")).hexdigest()
        mention_key = hashlib.sha256(
            f"{identifier}\x1f{name_normalised}".encode("utf-8")
        ).hexdigest()
        records.append(
            MentionRecord(
                row_ordinal=ordinal,
                identifier_raw=identifier,
                operator_name_raw=raw_name,
                operator_name_normalised=name_normalised,
                source_status=classify_source_status(raw_block),
                record_hash=record_hash,
                mention_key=mention_key,
                raw_block=raw_block,
            )
        )
    return records


def diff_mentions(before: list[MentionRecord], after: list[MentionRecord]) -> dict[str, object]:
    before_mentions = {(r.identifier_raw, r.operator_name_normalised): r for r in before}
    after_mentions = {(r.identifier_raw, r.operator_name_normalised): r for r in after}
    common = set(before_mentions) & set(after_mentions)
    added = set(after_mentions) - set(before_mentions)
    disappeared = set(before_mentions) - set(after_mentions)

    before_by_id: dict[str, list[MentionRecord]] = defaultdict(list)
    after_by_id: dict[str, list[MentionRecord]] = defaultdict(list)
    for record in before:
        before_by_id[record.identifier_raw].append(record)
    for record in after:
        after_by_id[record.identifier_raw].append(record)

    shared_ids = set(before_by_id) & set(after_by_id)
    stable_identifier_name_changes = [
        identifier
        for identifier in shared_ids
        if len(before_by_id[identifier]) == len(after_by_id[identifier]) == 1
        and before_by_id[identifier][0].operator_name_normalised
        != after_by_id[identifier][0].operator_name_normalised
    ]
    ambiguous_identifiers = [
        identifier
        for identifier in set(before_by_id) | set(after_by_id)
        if len(before_by_id.get(identifier, [])) > 1 or len(after_by_id.get(identifier, [])) > 1
    ]

    status_changes = [
        key
        for key in common
        if before_mentions[key].source_status != after_mentions[key].source_status
    ]
    transition_counts = Counter(
        f"{before_mentions[key].source_status}->{after_mentions[key].source_status}"
        for key in status_changes
    )

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
            "record_content_changed": sum(
                before_mentions[key].record_hash != after_mentions[key].record_hash
                for key in common
            ),
        },
        "identifier_observations": {
            "new_identifiers": len(set(after_by_id) - set(before_by_id)),
            "disappeared_identifiers": len(set(before_by_id) - set(after_by_id)),
            "stable_identifier_name_changes": len(stable_identifier_name_changes),
            "ambiguous_identifiers": len(ambiguous_identifiers),
        },
        "source_status": {
            "before_counts": dict(Counter(r.source_status for r in before)),
            "after_counts": dict(Counter(r.source_status for r in after)),
            "changed_common_mentions": len(status_changes),
            "transition_counts": dict(sorted(transition_counts.items())),
        },
        "interpretation_guardrails": [
            "added/disappeared are source-observation events, not administrative registration/removal events",
            "source_status is parsed from published Esito wording and is not a legal-effect determination",
            "identifier values are source fields and are not assumed to uniquely identify canonical LegalEntity rows",
        ],
    }


def write_records(records: list[MentionRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row_ordinal",
                "identifier_raw",
                "operator_name_raw",
                "operator_name_normalised",
                "source_status",
                "record_hash",
                "mention_key",
                "raw_block",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("before_text", type=Path)
    parser.add_argument("after_text", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/cosenza-mentions"))
    args = parser.parse_args()

    before = parse_mentions(args.before_text.read_text(encoding="utf-8", errors="replace"))
    after = parse_mentions(args.after_text.read_text(encoding="utf-8", errors="replace"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_records(before, args.output_dir / "before_records.csv")
    write_records(after, args.output_dir / "after_records.csv")
    summary = diff_mentions(before, after)
    summary_path = args.output_dir / "diff_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(summary_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()

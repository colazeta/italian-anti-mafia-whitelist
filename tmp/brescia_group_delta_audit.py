from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from white_list_archive.parsers import brescia_openxml as bs

LISTED = Path("/tmp/brescia-listed.xlsx")
SHIFT_SUMMARY = Path("tmp/brescia_layout_audit_summary.json")
OUT = Path("tmp/brescia_group_delta_audit_output.json")


def sha256_json(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def key_for(row):
    return (
        row["name"],
        row["identifier_raw"],
        row["listing_date"] or row["listing_raw"],
        row["expiry_date"] or row["expiry_raw"],
    )


def main() -> None:
    summary = json.loads(SHIFT_SUMMARY.read_text(encoding="utf-8"))
    shift_rows = set(summary["expected_name_blank_company_like_rows"])
    rows, section_counts, _, structural_shift_rows = bs._listed_rows(LISTED)
    peer_resolved = bs._resolve_peer_dates(rows)

    groups = {}
    for row in rows:
        key = key_for(row)
        group = groups.setdefault(key, [])
        if any(peer["section"] == row["section"] for peer in group):
            raise RuntimeError(f"same-section semantic duplicate: {key!r}")
        group.append(row)

    new_groups = []
    mixed_groups = []
    shift_group_statuses = Counter()
    total_statuses = Counter()
    shift_rows_seen = set()

    for key, members in groups.items():
        member_shift_rows = sorted(row["source_row"] for row in members if row["source_row"] in shift_rows)
        has_shift = bool(member_shift_rows)
        has_original_named = any(row["source_row"] not in shift_rows for row in members)
        status = (
            "renewal_update_in_progress"
            if any(row["update_raw"].casefold() == bs._STANDARD_UPDATE.casefold() for row in members)
            else "listed"
        )
        total_statuses[status] += 1
        if not has_shift:
            continue
        shift_rows_seen.update(member_shift_rows)
        item = {
            "key": list(key),
            "status": status,
            "source_rows": sorted(row["source_row"] for row in members),
            "shift_source_rows": member_shift_rows,
            "sections": [row["section"] for row in members],
            "offices": [row["office"] for row in members],
            "updates": [row["update_raw"] for row in members],
            "has_preexisting_named_row": has_original_named,
        }
        shift_group_statuses[status] += 1
        if has_original_named:
            mixed_groups.append(item)
        else:
            new_groups.append(item)

    if shift_rows_seen != shift_rows:
        raise RuntimeError(
            f"shift row coverage drift: missing={sorted(shift_rows-shift_rows_seen)} extra={sorted(shift_rows_seen-shift_rows)}"
        )

    output = {
        "source_rows": len(rows),
        "section_counts": dict(section_counts),
        "structural_shift_rows": structural_shift_rows,
        "peer_resolved_date_rows": peer_resolved,
        "semantic_groups": len(groups),
        "total_status_counts": dict(total_statuses),
        "audited_shift_source_rows": len(shift_rows),
        "groups_touched_by_shift_rows": len(new_groups) + len(mixed_groups),
        "new_groups_from_shift_rows": len(new_groups),
        "mixed_groups_with_preexisting_named_rows": len(mixed_groups),
        "shift_group_status_counts": dict(shift_group_statuses),
        "new_group_status_counts": dict(Counter(item["status"] for item in new_groups)),
        "mixed_group_status_counts": dict(Counter(item["status"] for item in mixed_groups)),
        "new_groups_sha256": sha256_json(new_groups),
        "mixed_groups_sha256": sha256_json(mixed_groups),
        "new_groups": new_groups,
        "mixed_groups": mixed_groups,
    }
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in output.items() if k not in {"new_groups", "mixed_groups"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

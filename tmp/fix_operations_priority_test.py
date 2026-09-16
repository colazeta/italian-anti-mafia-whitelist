from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tests/test_operations.py"

OLD = '''    for row in ledger["prefectures"]:\n        if row["public_export_enabled"]:\n            row["coverage_status"] = "BLOCKED"\n    assert priority_queue(ledger)[0]["actionable_issue"]\n'''

NEW = '''    for row in ledger["prefectures"]:\n        if row["public_export_enabled"]:\n            row["coverage_status"] = "BLOCKED"\n\n    # The actionable-issue ordering invariant must not depend on the live ledger\n    # permanently containing an actionable territorial issue. Milano was the last\n    # such source-population issue; once it is resolved, that historical fixture\n    # disappears. Build a controlled tie instead and verify that actionability is\n    # still the deciding key before region/recency/authority ordering.\n    candidates = [row for row in ledger["prefectures"] if row["coverage_status"] != "BLOCKED"]\n    assert len(candidates) >= 2\n    for row in candidates:\n        row.update(\n            source_verified=False,\n            coverage_status="NOT_STARTED",\n            canonical_integration_validated=False,\n            actionable_issue=False,\n        )\n    target = candidates[-1]\n    target["actionable_issue"] = True\n    assert priority_queue(ledger)[0]["authority_key"] == target["authority_key"]\n'''


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    count = text.count(OLD)
    if count != 1:
        raise RuntimeError(f"Expected one operations-priority fixture block, found {count}")
    PATH.write_text(text.replace(OLD, NEW), encoding="utf-8")
    print("Updated actionable-priority regression to use a controlled fixture")


if __name__ == "__main__":
    main()

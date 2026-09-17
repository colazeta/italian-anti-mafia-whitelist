from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_AT = "2026-09-17T00:03:58Z"
OLD_SHA = "b360e209f3997894a3e7408e5be7f07d77cddca0c3490581ff3410218a02d9a8"
NEW_SHA = "37fd59b67b153dd642298c7143de4aa1bc57bb1cced0a9310bc9539a79078215"
OLD_REGISTERED_SHA = "4509948e4baf91ed5c92bd5940a2fca1cd5f9a6fd21f553c4864e68735e36608"
NEW_REGISTERED_SHA = "7f5c7dcc3288387d15125aee1f8aee4e271e5743ecc3a6e9da229873cc1f4848"
EVIDENCE = "docs/sources/milano-source-transition-2026-09-17.md"

REMOVED = [
    ("04793740962", "RIZZI TOBIA DI RIZZI PIETRO SRL", ["Sezione 4"]),
    ("06960770961", "V.M.V. Costruzioni Generali Srl", ["Sezione 3", "Sezione 10"]),
    ("07693660156", "AIR ENTERPRISE SRL", ["Sezione 6"]),
    ("09835880155", "SAVING SHIPPING & FORWARDING SRL", ["Sezione 6"]),
    ("10674330963", "KRUGER A/S", ["Sezione 3"]),
    ("11016700152", "SPREAFICO TRASPORTI SRL", ["Sezione 6"]),
]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one occurrence in {path}: {old!r}; got {text.count(old)}")
    path.write_text(text.replace(old, new), encoding="utf-8")


parser = ROOT / "src/white_list_archive/parsers/milano_webapp.py"
replace_once(parser, 'PARSER_VERSION = "1"', 'PARSER_VERSION = "2"')
replace_once(parser, '_REFERENCE_DATE = "2026-09-16"', '_REFERENCE_DATE = "2026-09-17"')
replace_once(parser, "_EXPECTED_SECTOR_ROWS = 4220", "_EXPECTED_SECTOR_ROWS = 4213")
replace_once(parser, "_EXPECTED_RECORDS = 2618", "_EXPECTED_RECORDS = 2612")
replace_once(parser, '    "listed": 939,', '    "listed": 933,')
replace_once(parser, "_EXPECTED_IDENTIFIER_COVERAGE = 2618", "_EXPECTED_IDENTIFIER_COVERAGE = 2612")

semantic_test = ROOT / "tests/test_milano_parser_semantics.py"
replace_once(semantic_test, '"reference_date": "2026-09-16"', '"reference_date": "2026-09-17"')

publication_path = ROOT / "data/publication/multi_prefecture_pilot.json"
publication = json.loads(publication_path.read_text(encoding="utf-8"))
entries = [x for x in publication["sources"] if x.get("source_key") == "milano-combined"]
if len(entries) != 1:
    raise SystemExit(f"expected one milano-combined publication entry, got {len(entries)}")
entry = entries[0]
expected_old = {
    "reference_date": "2026-09-16",
    "sha256": OLD_SHA,
    "expected_sector_rows": 4220,
    "expected_source_rows": 2618,
    "last_source_update": "2026-09-16",
}
for key, value in expected_old.items():
    if entry.get(key) != value:
        raise SystemExit(f"publication precondition failed for {key}: {entry.get(key)!r} != {value!r}")
entry.update(
    reference_date="2026-09-17",
    sha256=NEW_SHA,
    expected_sector_rows=4213,
    expected_source_rows=2612,
    last_source_update="2026-09-17",
    last_source_update_basis=(
        "current mutable official web application captured and independently revalidated on 17 September 2026; "
        "the date is a capture/reference boundary only and is not an inferred company event or legal-effect date"
    ),
    notes=(
        "The mutable combined operational table was independently captured twice on 17 September 2026 at "
        "970,799 bytes with SHA-256 37fd59b67b153dd642298c7143de4aa1bc57bb1cced0a9310bc9539a79078215. "
        "The reviewed boundary contains 4,213 sector rows and 2,612 logical observations: 933 listed, 517 "
        "renewal/update in progress and 1,162 pending; all 2,612 identifiers are strict. Compared with the "
        "approved 16 September boundary, there are no additions and no status changes among retained identities; "
        "six previously listed identities are absent from both current official views. All six had source-explicit "
        "expiry date 17 September 2026 in the approved edition. V.M.V. Costruzioni Generali Srl previously occurred "
        "in two statutory sections, explaining the seven-row physical decrease. The registered-only sibling was "
        "also independently stable at 557,481 bytes, SHA-256 7f5c7dcc3288387d15125aee1f8aee4e271e5743ecc3a6e9da229873cc1f4848, "
        "and its 1,450 identities exactly match the combined non-pending set; it remains corroborative and is not co-ingested."
    ),
)
publication_path.write_text(json.dumps(publication, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

inventory_path = ROOT / "data/source_registry/source_series_inventory.csv"
lines = inventory_path.read_text(encoding="utf-8").splitlines(keepends=True)
header = next(csv.reader([lines[0].rstrip("\r\n")]))
matched = 0
for idx, line in enumerate(lines[1:], 1):
    row = next(csv.reader([line.rstrip("\r\n")]))
    if row[0] != "milano-combined":
        continue
    matched += 1
    data = dict(zip(header, row, strict=True))
    if data["verified_date"] != "2026-09-16":
        raise SystemExit(f"inventory date precondition failed: {data['verified_date']!r}")
    data["verified_date"] = "2026-09-17"
    data["notes"] = (
        "Current mutable combined listed/applicant table independently reverified 17 September 2026. "
        "Two byte-identical no-cache captures yield 4,213 sector rows and 2,612 logical observations "
        "(933 listed, 517 renewal/update, 1,162 pending), all with strict identifiers. Six listed identities from "
        "the approved 16 September edition are absent; all six had source-explicit expiry date 17 September 2026. "
        "The independently stable registered-only sibling contains 1,450 identities exactly equal to the combined "
        "non-pending set. Exact hashes, removed identities and conservative interpretation are documented in "
        + EVIDENCE + "."
    )
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerow([data[col] for col in header])
    lines[idx] = out.getvalue()
if matched != 1:
    raise SystemExit(f"expected one milano-combined inventory row, got {matched}")
inventory_path.write_text("".join(lines), encoding="utf-8")

monitor_path = ROOT / "data/monitoring/national_coverage.json"
monitor = json.loads(monitor_path.read_text(encoding="utf-8"))
prefectures = [x for x in monitor["prefectures"] if x.get("authority_key") == "milano"]
if len(prefectures) != 1:
    raise SystemExit(f"expected one Milano monitoring row, got {len(prefectures)}")
pref = prefectures[0]
if pref.get("latest_source_reference_date") != "2026-09-16":
    raise SystemExit(f"monitoring reference-date precondition failed: {pref.get('latest_source_reference_date')!r}")
pref["latest_source_reference_date"] = "2026-09-17"
pref["last_successful_source_check_at"] = CHECK_AT
pref["last_attempted_source_check_at"] = CHECK_AT
pref["last_content_change_at"] = CHECK_AT
pref["last_successful_investigation_on"] = "2026-09-17"
pref["monitoring_status"] = "CURRENT"
known = pref.setdefault("known_content_sha256", [])
for sha in (OLD_SHA, NEW_SHA, OLD_REGISTERED_SHA, NEW_REGISTERED_SHA):
    if sha not in known:
        known.append(sha)
for field in ("completion_evidence", "evidence"):
    values = pref.setdefault(field, [])
    if EVIDENCE not in values:
        values.append(EVIDENCE)
checks = monitor.setdefault("checks", [])
if not any(x.get("authority_key") == "milano" and x.get("at") == CHECK_AT for x in checks):
    checks.append({
        "authority_key": "milano",
        "at": CHECK_AT,
        "evidence": EVIDENCE,
        "error": None,
        "content_changed": True,
        "content_sha256": NEW_SHA,
    })
monitor_path.write_text(json.dumps(monitor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

evidence_path = ROOT / EVIDENCE
if evidence_path.exists():
    raise SystemExit(f"transition evidence already exists: {evidence_path}")
evidence_path.write_text(
    """# Milano source transition — 17 September 2026

## Scope

This note records a fail-closed transition of the current mutable Milano White List web application. It does not infer legal status, cancellation grounds or completeness from search failure. The official combined table remains the sole ingested source; the registered-only view is used only as independent corroboration.

## Official surfaces

- Prefettura landing page: https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list
- combined listed/applicant table: https://whitelist.prefmi.it/elenco/elenco.php
- registered-only sibling: https://whitelist.prefmi.it/elenco/elenco_iscritte.php

## Independent captures

Two independent no-cache captures on 17 September 2026 were byte-identical for each current official view.

| view | bytes | SHA-256 | logical identities | physical/sector rows |
| --- | ---: | --- | ---: | ---: |
| combined | 970,799 | `37fd59b67b153dd642298c7143de4aa1bc57bb1cced0a9310bc9539a79078215` | 2,612 | 4,213 |
| registered-only sibling | 557,481 | `7f5c7dcc3288387d15125aee1f8aee4e271e5743ecc3a6e9da229873cc1f4848` | 1,450 | 2,454 |

The combined table parses to exactly **933 listed + 517 renewal/update in progress + 1,162 pending = 2,612** observations, all with strict identifiers. The registered-only sibling parses to **977 listed + 473 renewal/update in progress = 1,450** observations. Its identity set is exactly equal to the combined table's non-pending identity set; no pending identity appears in the sibling.

## Exact transition from the approved 16 September boundary

The approved combined edition contained 2,618 logical observations and 4,220 sector rows at SHA-256 `b360e209f3997894a3e7408e5be7f07d77cddca0c3490581ff3410218a02d9a8`. The current edition adds no identity and changes no status among the 2,612 retained identities. Six previously listed identities are absent from both current official views:

| identifier | name in approved edition | previous sections |
| --- | --- | --- |
| 04793740962 | RIZZI TOBIA DI RIZZI PIETRO SRL | Sezione 4 |
| 06960770961 | V.M.V. Costruzioni Generali Srl | Sezioni 3, 10 |
| 07693660156 | AIR ENTERPRISE SRL | Sezione 6 |
| 09835880155 | SAVING SHIPPING & FORWARDING SRL | Sezione 6 |
| 10674330963 | KRUGER A/S | Sezione 3 |
| 11016700152 | SPREAFICO TRASPORTI SRL | Sezione 6 |

All six records carried a source-explicit expiry date of **17 September 2026** in the approved edition. This is recorded as source evidence only: absence from the current views is not interpreted as a cancellation, adverse decision or any other legal conclusion. V.M.V. Costruzioni Generali Srl appeared in two sections, so six logical removals correspond to seven fewer sector rows.

The registered-only sibling also changed byte identity from the previously corroborated SHA-256 `4509948e4baf91ed5c92bd5940a2fca1cd5f9a6fd21f553c4864e68735e36608` to the current hash above while preserving exact cross-view identity consistency.

## Provenance and retention

The parser remains fail-closed on source structure, denominators, statuses and configured content identity. `durable_evidence_verified` remains false: the current official web application is mutable and this transition does not claim independent immutable archival custody. The 17 September date is a capture/reference boundary, not an inferred company event or legal-effect date.
""",
    encoding="utf-8",
)

print("Milano transition prepared: 2,612 observations; 4,213 sector rows; 6 listed identities absent from current source")

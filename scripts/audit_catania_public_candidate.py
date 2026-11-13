"""Review-only exact Catania November publication delta (never prints company data)."""
from __future__ import annotations
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import tempfile

from white_list_archive.publishing.public_snapshot import restore

ROOT=Path("public-site/data")
SOURCE_KEYS={"catania-listed","catania-applicants"}
SOURCE_COUNTS={"catania-listed":1864,"catania-applicants":173}
SOURCE_STATUSES={
    "catania-listed":{"listed":1662,"renewal_update_in_progress":202},
    "catania-applicants":{"pending":173},
}
SOURCE_SHAS={
    "catania-listed":"ccd1a9abbf8144ae4edb43c7df07c1648c0273196a7aff278c03c62b39b733ff",
    "catania-applicants":"adb590642773f68047e207beeb6aace3555ece674b6b64872c1347c0c7d4ffbb",
}

def rows_by_source(records):
    by=defaultdict(list)
    for row in records:
        by[row["source_key"]].append(row)
    return by

def digest(rows):
    # Never transmit individual observations or hashes to the summary; these
    # internal digests are only used to detect unexpected changes.
    payload=json.dumps(sorted(rows,key=lambda r:r["record_locator"]),
                       ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(payload).hexdigest()

def main():
    proposal=json.loads((ROOT/"registry.json").read_text(encoding="utf-8"))
    manifest=json.loads(Path("data/publication/public_snapshot.json").read_text())
    with tempfile.TemporaryDirectory(prefix="approved-september-public-") as td:
        restore(manifest,Path(td))
        approved=json.loads((Path(td)/"registry.json").read_text(encoding="utf-8"))
    before=rows_by_source(approved["records"])
    after=rows_by_source(proposal["records"])
    if set(before)!=set(after):
        raise RuntimeError("Catania candidate changed source-series coverage")
    changed_non_catania=[key for key in before if key not in SOURCE_KEYS and digest(before[key])!=digest(after[key])]
    if changed_non_catania:
        raise RuntimeError(f"Non-Catania source observations changed unexpectedly: {len(changed_non_catania)} sources")
    if proposal["meta"]["authority_count"]!=74 or proposal["meta"]["register_count"]!=77:
        raise RuntimeError("Catania release lost approved authority/register coverage")
    expected_total=len(approved["records"])+sum(SOURCE_COUNTS[k]-len(before[k]) for k in SOURCE_KEYS)
    if len(proposal["records"])!=expected_total:
        raise RuntimeError("Catania candidate national denominator does not reconcile")
    summary={}
    for key in sorted(SOURCE_KEYS):
        rows=after[key]
        report=[s for s in proposal["meta"]["sources"] if s["source_key"]==key]
        if len(report)!=1 or report[0]["sha256"]!=SOURCE_SHAS[key] or report[0]["reference_date"]!="2026-11-06":
            raise RuntimeError(f"{key}: source report SHA/reference mismatch")
        if len(rows)!=SOURCE_COUNTS[key]:
            raise RuntimeError(f"{key}: new source record count mismatch")
        actual_status=dict(Counter(row["source_status"] for row in rows))
        if actual_status!=SOURCE_STATUSES[key]:
            raise RuntimeError(f"{key}: source status breakdown drift")
        blank=sum(not row.get("name") for row in rows)
        if blank != (1 if key=="catania-applicants" else 0):
            raise RuntimeError(f"{key}: blank source names drift")
        summary[key]={"previous_records":len(before[key]),"proposed_records":len(rows),
                      "date":"2026-11-06","statuses":actual_status,
                      "blank_source_names_preserved":blank}
    print(json.dumps({
        "review_only":True, "published":False, "national_approved_baseline":len(approved["records"]),
        "national_proposed":len(proposal["records"]),
        "old_authorities":approved["meta"]["authority_count"],
        "new_authorities":proposal["meta"]["authority_count"],
        "sources_updated":summary,
        "non_catania_source_records_changed":0,
    },sort_keys=True))

if __name__=="__main__":
    main()

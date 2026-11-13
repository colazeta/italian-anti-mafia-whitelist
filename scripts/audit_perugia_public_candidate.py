"""Review-only exact Perugia November publication delta (never prints company data)."""
from __future__ import annotations
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import tempfile

from white_list_archive.publishing.public_snapshot import restore

ROOT=Path("public-site/data")
SOURCE_KEYS={"perugia-listed","perugia-applicants"}
SOURCE_COUNTS={"perugia-listed":1020,"perugia-applicants":1243}
SOURCE_STATUSES={
    "perugia-listed":{"listed":642,"renewal_update_in_progress":378},
    "perugia-applicants":{"listed":1038,"pending":204,"other_or_unknown":1},
}
SOURCE_SHAS={
    "perugia-listed":"d8dd83ac23e8fd1fa3b3913423d0b08ff5b1bc12a964738d4ff1a8499fa274f8",
    "perugia-applicants":"c049e8ec3d94f3a87ec7e6749cdd5f88b769c318156d38a51bba07b777762e77",
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
    if manifest["release_tag"] != "public-data-43496640709-1":
        print(json.dumps({"exact_perugia_incremental_audit": "not_applicable_to_later_baseline",
                          "selected_baseline": manifest["release_tag"]}, sort_keys=True))
        return
    before=rows_by_source(approved["records"])
    after=rows_by_source(proposal["records"])
    if set(before)!=set(after):
        raise RuntimeError("Perugia candidate changed source-series coverage")
    changed_non_perugia=[key for key in before if key not in SOURCE_KEYS and digest(before[key])!=digest(after[key])]
    if changed_non_perugia:
        details=[]
        for key in sorted(changed_non_perugia):
            previous={r["record_locator"]:r for r in before[key]}
            proposed={r["record_locator"]:r for r in after[key]}
            field_counts=Counter()
            for loc in set(previous) & set(proposed):
                for field in set(previous[loc]) | set(proposed[loc]):
                    if previous[loc].get(field)!=proposed[loc].get(field):
                        field_counts[field]+=1
            details.append({"source_key":key,
                            "old_count":len(before[key]),"new_count":len(after[key]),
                            "changed_field_names_only":dict(field_counts),
                            "added_locators":len(set(proposed)-set(previous)),
                            "removed_locators":len(set(previous)-set(proposed))})
        raise RuntimeError(f"Unexpected non-Perugia changes (safe metadata only): {details}")
    if proposal["meta"]["authority_count"]!=74 or proposal["meta"]["register_count"]!=77:
        raise RuntimeError("Perugia release lost approved authority/register coverage")
    expected_total=len(approved["records"])+sum(SOURCE_COUNTS[k]-len(before[k]) for k in SOURCE_KEYS)
    if len(proposal["records"])!=expected_total:
        raise RuntimeError("Perugia candidate national denominator does not reconcile")
    summary={}
    for key in sorted(SOURCE_KEYS):
        rows=after[key]
        report=[s for s in proposal["meta"]["sources"] if s["source_key"]==key]
        if len(report)!=1 or report[0]["sha256"]!=SOURCE_SHAS[key] or report[0]["reference_date"]!="2026-11-05":
            raise RuntimeError(f"{key}: source report SHA/reference mismatch")
        if len(rows)!=SOURCE_COUNTS[key]:
            raise RuntimeError(f"{key}: new source record count mismatch")
        actual_status=dict(Counter(row["source_status"] for row in rows))
        if actual_status!=SOURCE_STATUSES[key]:
            raise RuntimeError(f"{key}: source status breakdown drift")
        blank=sum(not row.get("name") for row in rows)
        if blank != 0:
            raise RuntimeError(f"{key}: blank source names drift")
        summary[key]={"previous_records":len(before[key]),"proposed_records":len(rows),
                      "date":"2026-11-05","statuses":actual_status,
                      "blank_source_names_preserved":blank}
    print(json.dumps({
        "review_only":True, "published":False, "national_approved_baseline":len(approved["records"]),
        "national_proposed":len(proposal["records"]),
        "old_authorities":approved["meta"]["authority_count"],
        "new_authorities":proposal["meta"]["authority_count"],
        "sources_updated":summary,
        "non_perugia_source_records_changed":0,
    },sort_keys=True))

if __name__=="__main__":
    main()

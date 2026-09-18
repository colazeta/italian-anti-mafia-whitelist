from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

from white_list_archive.parsers import milano_webapp as m

COMBINED_URL = "https://whitelist.prefmi.it/elenco/elenco.php"
REGISTERED_URL = "https://whitelist.prefmi.it/elenco/elenco_iscritte.php"
LIVE_REGISTRY_URL = "https://colazeta.github.io/italian-anti-mafia-whitelist/data/registry.json"
EXPECTED_COMBINED_SHA = "b92945af542b89ca99122d60a6f2d1c4c22359bb2c1bbe7c40672c7738bbc58a"
OUT = Path("audit-output/milano-drift-review.json")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "italian-anti-mafia-whitelist-evidence-review/1.0",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        if response.status != 200:
            raise RuntimeError(f"{url}: HTTP {response.status}")
        return response.read()


def capture_pair(url: str) -> tuple[bytes, bytes, dict]:
    first = fetch(url)
    time.sleep(3)
    second = fetch(url)
    return first, second, {
        "url": url,
        "capture_1_bytes": len(first),
        "capture_2_bytes": len(second),
        "capture_1_sha256": hashlib.sha256(first).hexdigest(),
        "capture_2_sha256": hashlib.sha256(second).hexdigest(),
        "byte_identical": first == second,
    }


def source_cfg(url: str, sha: str) -> dict:
    doc = json.loads(Path("data/publication/multi_prefecture_pilot.json").read_text(encoding="utf-8"))
    cfg = next(x for x in doc["sources"] if x["source_key"] == "milano-combined").copy()
    cfg["resource_url"] = url
    cfg["sha256"] = sha
    return cfg


def parse_adaptive(raw: bytes, url: str) -> tuple[list[dict], dict]:
    path = Path("/tmp/milano-review-source.html")
    path.write_bytes(raw)
    cfg = source_cfg(url, hashlib.sha256(raw).hexdigest())

    names = (
        "_EXPECTED_SECTOR_ROWS",
        "_EXPECTED_RECORDS",
        "_EXPECTED_STATUS_COUNTS",
        "_EXPECTED_IDENTIFIER_COVERAGE",
        "_EXPECTED_NONBLANK_NOTES",
    )
    original = {name: getattr(m, name) for name in names}
    observed = {}
    try:
        for _ in range(8):
            try:
                batch = m.parse_milano_combined(path, cfg)
                observed.update(batch.diagnostics)
                return batch.records, observed
            except RuntimeError as exc:
                text = str(exc)
                match = re.search(r"Milano sector-row drift: (\d+) !=", text)
                if match:
                    value = int(match.group(1))
                    m._EXPECTED_SECTOR_ROWS = value
                    observed["sector_rows"] = value
                    continue
                match = re.search(r"Milano grouped-record drift: (\d+) !=", text)
                if match:
                    value = int(match.group(1))
                    m._EXPECTED_RECORDS = value
                    observed["public_records"] = value
                    continue
                match = re.search(r"Milano status-count drift: (\{.*\}) !=", text)
                if match:
                    value = ast.literal_eval(match.group(1))
                    m._EXPECTED_STATUS_COUNTS = value
                    observed["status_counts"] = value
                    continue
                match = re.search(r"Milano identifier-coverage drift: (\d+) !=", text)
                if match:
                    value = int(match.group(1))
                    m._EXPECTED_IDENTIFIER_COVERAGE = value
                    observed["identifier_coverage"] = value
                    continue
                match = re.search(r"Milano note-denominator drift: (\d+) !=", text)
                if match:
                    value = int(match.group(1))
                    m._EXPECTED_NONBLANK_NOTES = value
                    observed["nonblank_notes"] = value
                    continue
                raise
        raise RuntimeError("adaptive audit exceeded bounded denominator-reconciliation loop")
    finally:
        for name, value in original.items():
            setattr(m, name, value)


def by_identifier(records: list[dict]) -> dict[str, dict]:
    result = {}
    for row in records:
        identifier = str(row.get("identifier_field_raw") or "").upper()
        if not identifier:
            raise RuntimeError("Milano audited record has blank identifier")
        if identifier in result:
            raise RuntimeError(f"Milano audited identifier duplicated: {identifier}")
        result[identifier] = row
    return result


def summary(records: list[dict]) -> dict:
    return {
        "logical_records": len(records),
        "status_counts": dict(sorted(Counter(r["source_status"] for r in records).items())),
        "identifier_coverage": sum(bool(r.get("identifiers")) for r in records),
        "application_date_count": sum(bool(r.get("application_date")) for r in records),
        "listing_date_count": sum(bool(r.get("observed_listing_date")) for r in records),
        "expiry_date_count": sum(bool(r.get("observed_expiry_date")) for r in records),
        "nonblank_notes": sum(bool((r.get("source_fields") or {}).get("note")) for r in records),
        "max_application_date": max((r["application_date"] for r in records if r.get("application_date")), default=None),
        "max_listing_date": max((r["observed_listing_date"] for r in records if r.get("observed_listing_date")), default=None),
        "max_expiry_date": max((r["observed_expiry_date"] for r in records if r.get("observed_expiry_date")), default=None),
    }


def sections(row: dict) -> list[int]:
    values = []
    for label in (row.get("source_fields") or {}).get("sections") or []:
        try:
            values.append(int(str(label).split()[-1]))
        except Exception:
            pass
    return sorted(values)


def view(row: dict) -> dict:
    return {
        "status": row.get("source_status") or "",
        "application_date": row.get("application_date") or "",
        "listing_date": row.get("observed_listing_date") or "",
        "expiry_date": row.get("observed_expiry_date") or "",
        "sections": sections(row),
    }


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    report = {
        "candidate_combined_sha256": EXPECTED_COMBINED_SHA,
        "captures": {},
        "summaries": {},
        "corroboration": {},
        "live_registry_comparison": {},
        "errors": [],
    }

    try:
        c1, c2, cmeta = capture_pair(COMBINED_URL)
        r1, r2, rmeta = capture_pair(REGISTERED_URL)
        report["captures"] = {"combined": cmeta, "registered_only": rmeta}
        if c1 != c2:
            report["errors"].append("combined captures are not byte-identical")
        if cmeta["capture_1_sha256"] != EXPECTED_COMBINED_SHA:
            report["errors"].append(
                f"combined candidate changed again: {cmeta['capture_1_sha256']} != {EXPECTED_COMBINED_SHA}"
            )
        if r1 != r2:
            report["errors"].append("registered-only captures are not byte-identical")

        combined_records, combined_diag = parse_adaptive(c1, COMBINED_URL)
        registered_records, registered_diag = parse_adaptive(r1, REGISTERED_URL)
        report["summaries"] = {
            "combined": {**summary(combined_records), "diagnostics": combined_diag},
            "registered_only": {**summary(registered_records), "diagnostics": registered_diag},
        }

        combined = by_identifier(combined_records)
        registered = by_identifier(registered_records)
        combined_nonpending = {k for k, v in combined.items() if v["source_status"] != "pending"}
        registered_ids = set(registered)
        report["corroboration"] = {
            "combined_nonpending_identifiers": len(combined_nonpending),
            "registered_identifiers": len(registered_ids),
            "sets_equal": combined_nonpending == registered_ids,
            "missing_from_registered": sorted(combined_nonpending - registered_ids),
            "extra_in_registered": sorted(registered_ids - combined_nonpending),
        }
        if combined_nonpending != registered_ids:
            report["errors"].append("registered-only identity set differs from combined non-pending identity set")

        try:
            live_doc = json.loads(fetch(LIVE_REGISTRY_URL).decode("utf-8"))
            live_records = [r for r in live_doc.get("records", []) if r.get("authority_key") == "milano"]
            live = by_identifier(live_records)
            added = sorted(set(combined) - set(live))
            removed = sorted(set(live) - set(combined))
            changed = []
            for identifier in sorted(set(combined) & set(live)):
                old, new = view(live[identifier]), view(combined[identifier])
                if old != new:
                    changed.append({
                        "identifier": identifier,
                        "name": combined[identifier].get("name"),
                        "old": old,
                        "new": new,
                    })
            report["live_registry_comparison"] = {
                "live_url": LIVE_REGISTRY_URL,
                "live_total_records": len(live_doc.get("records", [])),
                "live_milano_records": len(live),
                "current_milano_records": len(combined),
                "added_count": len(added),
                "removed_count": len(removed),
                "changed_count": len(changed),
                "added": [
                    {"identifier": i, "name": combined[i].get("name"), **view(combined[i])}
                    for i in added
                ],
                "removed": [
                    {"identifier": i, "name": live[i].get("name"), **view(live[i])}
                    for i in removed
                ],
                "changed": changed,
            }
        except Exception as exc:
            report["live_registry_comparison"] = {"error": repr(exc)}

    except Exception as exc:
        report["errors"].append(repr(exc))

    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

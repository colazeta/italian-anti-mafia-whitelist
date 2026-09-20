from __future__ import annotations

import json
from pathlib import Path

RAW_SHA = "aeac0b690c28fa84d317d52d79382b4b9e51de9a4c7cbfef2a841bd9a7aa1d6a"
SEMANTIC_SHA = "5f8d3c7deada39f95b1da000c727b9c1f5e42bf7fe3deff06cb0ff825b1bf389"
REFERENCE_DATE = "2026-09-20"
CHECK_AT = "2026-09-20T00:05:33Z"
SOURCE_ID_REMOVED = "237"


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count == 0 and new in text:
        return text
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one old boundary, found {count}")
    return text.replace(old, new, 1)


# 1. Publication approval: approve only the independently reverified current
# source boundary. The observation date is not a source-edition or legal-effect
# date. Parser code and status semantics remain unchanged.
config_path = Path("data/publication/multi_prefecture_pilot.json")
config = json.loads(config_path.read_text(encoding="utf-8"))
matches = [x for x in config["sources"] if x.get("source_key") == "potenza-combined"]
if len(matches) != 1:
    raise RuntimeError(f"expected one potenza-combined config, got {len(matches)}")
potenza = matches[0]
allowed_old_or_new = {
    "reference_date": {"2026-09-17", REFERENCE_DATE},
    "sha256": {"cb3a1816dbe54bb0a1260a63e326385bcc435e52d8928a775f7c5bc259655d30", RAW_SHA},
    "expected_source_rows": {1035, 1034},
    "semantic_sha256": {"8b3a129f54dfb889740a6f16fddcd53294fc4269a7e311353e72dc9c7b81dd2e", SEMANTIC_SHA},
}
for key, allowed in allowed_old_or_new.items():
    if potenza.get(key) not in allowed:
        raise RuntimeError(f"unexpected Potenza {key}: {potenza.get(key)!r}")
potenza.update(
    {
        "reference_date": REFERENCE_DATE,
        "sha256": RAW_SHA,
        "expected_source_rows": 1034,
        "semantic_sha256": SEMANTIC_SHA,
        "last_source_update": REFERENCE_DATE,
        "last_source_update_basis": (
            "current mutable official web-application capture directly reverified on 20 September 2026; "
            "the date is an observation/reference boundary only and is not an inferred source-edition, "
            "company-decision or legal-effect date"
        ),
        "notes": (
            "Official Ministry landing links the UTG Potenza public White List web application. Two independent "
            "complete no-cache captures on 20 September 2026 were byte-identical and yielded 1,034 observations: "
            "215 listed, 376 pending and 443 renewal/update in progress. Relative to the approved 17 September "
            "boundary, source id 237 (PATANELLA ANTONIO & C. S.N.C.) is absent from the current endpoint; no new "
            "source ids and no status changes among the 1,034 surviving ids were observed. Absence from the mutable "
            "current endpoint is recorded only as source drift and is not interpreted as revocation, cancellation, "
            "denial, withdrawal or any other legal effect. Publication remains fail-closed on the independently "
            "approved full parsed source-semantic digest; raw capture SHA-256 remains observation provenance."
        ),
    }
)
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# 2. Source-series inventory: advance only the Potenza combined observation.
series_path = Path("data/source_registry/source_series_inventory.csv")
series = series_path.read_text(encoding="utf-8")n = None
lines = series.splitlines()
indexes = [i for i, line in enumerate(lines) if line.startswith("potenza-combined,potenza,")]
if len(indexes) != 1:
    raise RuntimeError(f"expected one potenza-combined inventory row, got {len(indexes)}")
i = indexes[0]
old_row = lines[i]
prefix = (
    "potenza-combined,potenza,WL-REGIME-L190-2012,listed_and_applicant,all,custom_web_application,"
    "https://www.utgpotenza.it/_whitelist.php,linked_application_resolved,2026-09-20,"
)
notes = (
    "Current official UTG Potenza web application revalidated 20 September 2026 by two independent complete "
    f"byte-identical captures at raw SHA-256 {RAW_SHA}; the strict production parser yields 1,034 observations "
    "(215 listed, 376 pending, 443 renewal/update in progress) with semantic approval "
    f"{SEMANTIC_SHA}. Against the approved 17 September boundary, source id 237 is the sole missing id, with no "
    "new ids and no status changes among surviving ids. The source disappearance is not interpreted as revocation, "
    "cancellation, denial, withdrawal or other legal effect."
)
import csv, io
buf = io.StringIO()
writer = csv.writer(buf, lineterminator="")
writer.writerow([
    "potenza-combined", "potenza", "WL-REGIME-L190-2012", "listed_and_applicant", "all",
    "custom_web_application", "https://www.utgpotenza.it/_whitelist.php", "linked_application_resolved",
    "2026-09-20", notes,
])
new_row = buf.getvalue()
if old_row != new_row:
    lines[i] = new_row
series_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# 3. Monitoring ledger: append one exact successful current-source observation
# and advance only Potenza monitoring fields. Do not promote durable evidence.
coverage_path = Path("data/monitoring/national_coverage.json")
coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
checks = coverage.get("checks")
if not isinstance(checks, list):
    raise RuntimeError("monitoring checks missing")
if not any(c.get("authority_key") == "potenza" and c.get("content_sha256") == RAW_SHA for c in checks):
    checks.append(
        {
            "authority_key": "potenza",
            "at": CHECK_AT,
            "evidence": "docs/sources/potenza-operational-check-2026-09-15.md",
            "error": None,
            "content_changed": True,
            "content_sha256": RAW_SHA,
        }
    )
prefs = [x for x in coverage.get("prefectures", []) if x.get("authority_key") == "potenza"]
if len(prefs) != 1:
    raise RuntimeError(f"expected one Potenza monitoring entry, got {len(prefs)}")
p = prefs[0]
if p.get("durable_evidence_verified") is not False:
    raise RuntimeError("Potenza durable-evidence flag unexpectedly changed")
p.update(
    {
        "latest_source_reference_date": REFERENCE_DATE,
        "last_successful_source_check_at": CHECK_AT,
        "last_attempted_source_check_at": CHECK_AT,
        "last_content_change_at": CHECK_AT,
        "last_successful_investigation_on": REFERENCE_DATE,
        "monitoring_status": "CURRENT",
    }
)
known = p.setdefault("known_content_sha256", [])
if RAW_SHA not in known:
    known.append(RAW_SHA)
coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# 4. Evidence note. Keep historical boundaries; append the new current-source
# observation and explain the sole delta without assigning a legal meaning.
note_path = Path("docs/sources/potenza-operational-check-2026-09-15.md")
note = note_path.read_text(encoding="utf-8")
marker = "## Current-source revalidation — 20 September 2026"
if marker not in note:
    note += f"""

{marker}

The mutable official UTG Potenza endpoint was revalidated again after it caused the Palermo national candidate to fail closed on a source-row mismatch. Two independent complete no-cache captures were byte-identical: **438,054 bytes**, raw SHA-256 `{RAW_SHA}`, `Result=OK`, `TotalRecordCount=1034`, and **1,034 distinct numeric source ids**.

The unchanged strict production parser yields **1,034 source-backed observations**: **215 listed**, **376 pending**, and **443 renewal/update in progress**. Structured identifiers are present on **1,033/1,034** observations; application dates on **1,034/1,034**; listing dates on **658**; expiry dates on **658**. The production parsed semantic SHA-256 is `{SEMANTIC_SHA}`.

A direct id-level comparison against the currently approved/public 1,035-row Potenza projection isolates the change exactly: source id **237**, `PATANELLA ANTONIO & C. S.N.C.` (`01749860712`), previously observed as `listed` with application date `2019-07-04`, listing date `2019-09-19`, and expiry date `2026-09-19`, is absent from the current endpoint. There are **no new source ids** and **no source-status changes among the 1,034 surviving ids**. The disappearance is therefore recorded strictly as a change in the current mutable source population. It is **not** interpreted as revocation, cancellation, denial, withdrawal, expiry, or any other legal effect without positive official evidence of that effect.

The approved current observation boundary is therefore 1,034 rows at reference date 20 September 2026. Publication remains fail-closed on the full parsed semantic digest above; the raw digest is provenance for this capture rather than a claim that the mutable endpoint is immutable.
"""
    note_path.write_text(note, encoding="utf-8")


# 5. Browser acceptance boundary. These are exact mechanical consequences of
# the sole absent listed row: -1 total/listed/id/application/listing/expiry.
browser_path = Path("tests/public_portal_browser.cjs")
browser = browser_path.read_text(encoding="utf-8")
repls = [
    ("assert.equal(stats.total,67180);", "assert.equal(stats.total,67179);", "browser national total"),
    ("assert.equal(potenza.length,1035);", "assert.equal(potenza.length,1034);", "browser Potenza total"),
    ("assert.equal(potenza.filter(r=>r.source_key==='potenza-combined').length,1035);", "assert.equal(potenza.filter(r=>r.source_key==='potenza-combined').length,1034);", "browser Potenza source total"),
    ("assert.deepEqual(statusCounts(potenza),{listed:216,pending:376,renewal_update_in_progress:443});", "assert.deepEqual(statusCounts(potenza),{listed:215,pending:376,renewal_update_in_progress:443});", "browser Potenza statuses"),
    ("assert.equal(new Set(potenza.map(r=>r.record_locator)).size,1035);", "assert.equal(new Set(potenza.map(r=>r.record_locator)).size,1034);", "browser Potenza locators"),
    ("assert.equal(potenza.filter(r=>r.identifiers.length>0).length,1034);", "assert.equal(potenza.filter(r=>r.identifiers.length>0).length,1033);", "browser Potenza ids"),
    ("assert.equal(potenza.filter(r=>r.application_date!=='').length,1035);", "assert.equal(potenza.filter(r=>r.application_date!=='').length,1034);", "browser Potenza application dates"),
    ("assert.equal(potenza.filter(r=>r.observed_listing_date!=='').length,659);", "assert.equal(potenza.filter(r=>r.observed_listing_date!=='').length,658);", "browser Potenza listing dates"),
    ("assert.equal(potenza.filter(r=>r.observed_expiry_date!=='').length,659);", "assert.equal(potenza.filter(r=>r.observed_expiry_date!=='').length,658);", "browser Potenza expiry dates"),
]
for old, new, label in repls:
    browser = replace_once(browser, old, new, label=label)
# Positive assertion: disappearance is a source-population fact, not a status.
anchor = "      const scavone=potenza.filter(r=>r.source_fields.physical_locator==='source-id:656');\n"
absence_assert = "      assert.equal(potenza.filter(r=>r.source_fields.physical_locator==='source-id:237').length,0);\n"
if absence_assert not in browser:
    if browser.count(anchor) != 1:
        raise RuntimeError("browser Potenza absence anchor missing")
    browser = browser.replace(anchor, absence_assert + anchor, 1)
browser_path.write_text(browser, encoding="utf-8")


# 6. Prepare, but do not directly commit, the permanent Pages workflow candidate.
# Actions tokens are not used to rewrite workflow files; this candidate is
# validated in the finalizer and promoted separately only after all gates pass.
workflow_path = Path(".github/workflows/public-pages.yml")
workflow = workflow_path.read_text(encoding="utf-8")
wf_repls = [
    ("assert reg['meta']['record_count'] == 67180", "assert reg['meta']['record_count'] == 67179", "workflow national total"),
    ("assert len(potenza_records) == 1035", "assert len(potenza_records) == 1034", "workflow Potenza total"),
    ("assert sum(r['source_status'] == 'listed' for r in potenza_records) == 216", "assert sum(r['source_status'] == 'listed' for r in potenza_records) == 215", "workflow Potenza listed"),
    ("assert len({r['record_locator'] for r in potenza_records}) == 1035", "assert len({r['record_locator'] for r in potenza_records}) == 1034", "workflow Potenza locators"),
    ("assert sum(bool(r['identifiers']) for r in potenza_records) == 1034", "assert sum(bool(r['identifiers']) for r in potenza_records) == 1033", "workflow Potenza ids"),
    ("assert sum(bool(r['application_date']) for r in potenza_records) == 1035", "assert sum(bool(r['application_date']) for r in potenza_records) == 1034", "workflow Potenza application dates"),
    ("assert sum(bool(r['observed_listing_date']) for r in potenza_records) == 659", "assert sum(bool(r['observed_listing_date']) for r in potenza_records) == 658", "workflow Potenza listing dates"),
    ("assert sum(bool(r['observed_expiry_date']) for r in potenza_records) == 659", "assert sum(bool(r['observed_expiry_date']) for r in potenza_records) == 658", "workflow Potenza expiry dates"),
]
for old, new, label in wf_repls:
    workflow = replace_once(workflow, old, new, label=label)
wf_anchor = "          scavone = [r for r in potenza_records if r['source_fields']['physical_locator'] == 'source-id:656']\n"
wf_absence = "          assert not [r for r in potenza_records if r['source_fields']['physical_locator'] == 'source-id:237']\n"
if wf_absence not in workflow:
    if workflow.count(wf_anchor) != 1:
        raise RuntimeError("workflow Potenza absence anchor missing")
    workflow = workflow.replace(wf_anchor, wf_absence + wf_anchor, 1)
Path("tmp/potenza-public-pages.yml").write_text(workflow, encoding="utf-8")

print(json.dumps({
    "potenza_rows": 1034,
    "status_counts": {"listed": 215, "pending": 376, "renewal_update_in_progress": 443},
    "raw_sha256": RAW_SHA,
    "semantic_sha256": SEMANTIC_SHA,
    "sole_missing_source_id": SOURCE_ID_REMOVED,
    "candidate_national_records": 67179,
}, sort_keys=True))

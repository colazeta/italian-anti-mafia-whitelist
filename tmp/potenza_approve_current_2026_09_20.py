from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

from white_list_archive.parsers.potenza_webapp import parse_potenza_combined
from white_list_archive.publishing.public_national_registry import _semantic_digest

RAW = "aeac0b690c28fa84d317d52d79382b4b9e51de9a4c7cbfef2a841bd9a7aa1d6a"
SEM = "40d3eba14b33d376ea307c1a7f120ac46161787e21a604f33e9430a59d4512fe"
OLD_RAW = "cb3a1816dbe54bb0a1260a63e326385bcc435e52d8928a775f7c5bc259655d30"
OLD_SEM = "8b3a129f54dfb889740a6f16fddcd53294fc4269a7e311353e72dc9c7b81dd2e"
CHECKED_AT = "2026-09-19T23:38:55Z"
REF_DATE = "2026-09-20"
BASE_URL = (
    "https://www.utgpotenza.it/data/vis_imprese.php?action=list&jtStartIndex=0&"
    "jtPageSize=2000&jtSorting=ragione_sociale%20ASC&cerca_ragione_sociale=&"
    "cerca_sede_legale=&cerca_stato_richiesta=0&cerca_sezione=0"
)
LIVE_REGISTRY = "https://colazeta.github.io/italian-anti-mafia-whitelist/data/registry.json"


def fetch(url: str, nonce: str | None = None) -> bytes:
    if nonce:
        url = f"{url}&_cb={nonce}"
    headers = {
        "User-Agent": "italian-anti-mafia-whitelist/1.0 (+https://github.com/colazeta/italian-anti-mafia-whitelist)",
        "Cache-Control": "no-cache, no-store",
        "Pragma": "no-cache",
    }
    if nonce:
        headers["X-White-List-Revalidation-Nonce"] = nonce
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


cfg_path = Path("data/publication/multi_prefecture_pilot.json")
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
pot = next(x for x in cfg["sources"] if x["source_key"] == "potenza-combined")
expected_prior = {
    "reference_date": "2026-09-17",
    "sha256": OLD_RAW,
    "expected_source_rows": 1035,
    "semantic_sha256": OLD_SEM,
}
for key, value in expected_prior.items():
    if pot.get(key) != value:
        raise SystemExit(f"unexpected prior Potenza config {key}: {pot.get(key)!r}")

captures: list[bytes] = []
batches = []
for index in (1, 2):
    raw = fetch(BASE_URL, f"approval-v2-{index}-20260920")
    if hashlib.sha256(raw).hexdigest() != RAW or len(raw) != 438054:
        raise SystemExit("current Potenza raw boundary changed during approval")
    payload = json.loads(raw)
    if payload.get("Result") != "OK" or int(payload.get("TotalRecordCount", -1)) != 1034 or len(payload.get("Records", [])) != 1034:
        raise SystemExit("current Potenza source count/result changed during approval")
    path = Path(f"/tmp/potenza-approval-{index}.json")
    path.write_bytes(raw)
    batch = parse_potenza_combined(path, pot)
    if _semantic_digest(batch.records) != SEM:
        raise SystemExit("current Potenza semantic boundary changed during approval")
    if batch.diagnostics.get("status_counts") != {"listed": 215, "pending": 376, "renewal_update_in_progress": 443}:
        raise SystemExit("current Potenza status distribution changed during approval")
    expected_diag = {
        "identifier_coverage": 1033,
        "application_date_coverage": 1034,
        "listing_date_coverage": 658,
        "expiry_date_coverage": 658,
        "distinct_source_ids": 1034,
    }
    for key, value in expected_diag.items():
        if batch.diagnostics.get(key) != value:
            raise SystemExit(f"current Potenza diagnostic {key} changed: {batch.diagnostics.get(key)!r}")
    captures.append(raw)
    batches.append(batch)
if captures[0] != captures[1]:
    raise SystemExit("independent Potenza captures are not byte-identical")

live = json.loads(fetch(LIVE_REGISTRY).decode("utf-8"))
live_potenza = [r for r in live["records"] if r.get("authority_key") == "potenza"]
if live["meta"]["record_count"] != 67180 or len(live_potenza) != 1035:
    raise SystemExit("live canonical boundary changed before Potenza approval")
pattern = re.compile(r":id-(\d+)$")
live_by_id = {}
for record in live_potenza:
    match = pattern.search(str(record.get("record_locator", "")))
    if not match:
        raise SystemExit("unexpected canonical Potenza locator")
    live_by_id[match.group(1)] = record
current_by_id = {str(r["source_fields"]["source_id"]): r for r in batches[0].records}
current_ids, live_ids = set(current_by_id), set(live_by_id)
if current_ids - live_ids or live_ids - current_ids != {"237"}:
    raise SystemExit(f"unexpected Potenza id delta added={sorted(current_ids-live_ids)} removed={sorted(live_ids-current_ids)}")
for source_id in current_ids:
    if current_by_id[source_id]["source_status"] != live_by_id[source_id]["source_status"]:
        raise SystemExit(f"unexpected surviving status change for source id {source_id}")
removed = live_by_id["237"]
for key, value in {
    "name": "PATANELLA ANTONIO & C. S.N.C.",
    "identifier_field_raw": "01749860712",
    "source_status": "listed",
    "application_date": "2019-07-04",
    "observed_listing_date": "2019-09-19",
    "observed_expiry_date": "2026-09-19",
}.items():
    if removed.get(key) != value:
        raise SystemExit(f"unexpected canonical source-id 237 {key}: {removed.get(key)!r}")

pot["reference_date"] = REF_DATE
pot["sha256"] = RAW
pot["expected_source_rows"] = 1034
pot["semantic_sha256"] = SEM
pot["last_source_update"] = REF_DATE
pot["last_source_update_basis"] = (
    "current mutable official web-application capture directly reverified on 20 September 2026; "
    "the date is an observation/reference boundary only and is not an inferred source-edition, "
    "company-decision or legal-effect date"
)
pot["notes"] = (
    "Official Ministry landing links the UTG Potenza public White List web application. Two independent "
    "complete current endpoint captures on 20 September 2026 were byte-identical at raw SHA-256 " + RAW +
    " and yielded 1,034 observations: 215 listed, 376 pending and 443 renewal/update in progress. Direct "
    "comparison with the live approved 17 September boundary established exactly one source-id removal: "
    "source id 237, PATANELLA ANTONIO & C. S.N.C. (01749860712), previously listed with observed expiry "
    "19 September 2026, is absent from the current endpoint; no source ids were added and no surviving "
    "source status changed. The temporal concurrence with the previously observed expiry is recorded but "
    "no causal, revocation, cancellation, denial, removal or other legal effect is inferred. Publication "
    "remains fail-closed on the independently approved full parsed source-semantic digest " + SEM +
    "; raw capture SHA-256 remains observation provenance."
)
cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

cov_path = Path("data/monitoring/national_coverage.json")
cov = json.loads(cov_path.read_text(encoding="utf-8"))
pcov = next(x for x in cov["prefectures"] if x["authority_key"] == "potenza")
pcov["latest_source_reference_date"] = REF_DATE
pcov["last_successful_source_check_at"] = CHECKED_AT
pcov["last_attempted_source_check_at"] = CHECKED_AT
pcov["last_content_change_at"] = CHECKED_AT
pcov["last_successful_investigation_on"] = REF_DATE
pcov["monitoring_status"] = "CURRENT"
if RAW not in pcov["known_content_sha256"]:
    pcov["known_content_sha256"].append(RAW)
if not any(x.get("authority_key") == "potenza" and x.get("content_sha256") == RAW for x in cov["checks"]):
    cov["checks"].append({
        "authority_key": "potenza",
        "at": CHECKED_AT,
        "evidence": "docs/sources/potenza-operational-check-2026-09-15.md",
        "error": None,
        "content_changed": True,
        "content_sha256": RAW,
    })
cov_path.write_text(json.dumps(cov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

inv_path = Path("data/source_registry/source_series_inventory.csv")
with inv_path.open(encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)
row = next(x for x in rows if x["source_series_key"] == "potenza-combined")
row["verified_date"] = REF_DATE
row["notes"] = (
    "Current official UTG Potenza web application directly revalidated 20 September 2026. Two independent "
    "complete cache-bypassed captures were byte-identical at raw SHA-256 " + RAW + " and the strict parser "
    "yields 1,034 observations: 215 listed, 376 pending and 443 renewal/update in progress. Against the live "
    "approved 17 September boundary, source id 237 (PATANELLA ANTONIO & C. S.N.C., 01749860712) is the sole "
    "removed source id; it had observed expiry 19 September 2026. No source ids were added and no surviving "
    "status changed. Production semantic approval is " + SEM + ". The temporal concurrence with the prior "
    "expiry is not treated as proof of causal or legal effect."
)
with inv_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

doc_path = Path("docs/sources/potenza-operational-check-2026-09-15.md")
doc = doc_path.read_text(encoding="utf-8")
marker = "## Current-source transition — 20 September 2026"
if marker in doc:
    raise SystemExit("20 September Potenza transition already documented unexpectedly")
doc += f"""

{marker}

At **2026-09-19T23:38:55Z** (20 September Europe/Rome), the official UTG Potenza endpoint was captured twice independently with cache-bypass controls. The complete responses were byte-identical at **438,054 bytes**, raw SHA-256 **`{RAW}`**, `Result=OK`, `TotalRecordCount=1034`, with 1,034 distinct source ids. The strict production parser returned **215 listed**, **376 pending**, and **443 renewal/update in progress**; **1,033** validated identifiers plus one conservatively retained raw-only identifier; **1,034** application dates; **658** listing dates; **658** expiry dates; and no per-company activity inference. The full parsed source-semantic SHA-256 is **`{SEM}`**.

A direct source-id/status comparison against the then-live approved **17 September 2026** Potenza projection (1,035 observations) found **no new source ids and no status changes among the 1,034 surviving ids**. The sole delta is disappearance of source id **237**, **PATANELLA ANTONIO & C. S.N.C.**, identifier **`01749860712`**, previously `listed`, application date `2019-07-04`, observed listing date `2019-09-19`, observed expiry date **`2026-09-19`**. The fact that disappearance was observed immediately after the previously published expiry date is retained as provenance only: the repository does **not** infer expiry as the cause, nor any revocation, cancellation, denial, adverse measure, legal effect or historical deletion. The prior approved edition remains part of the historical record.
"""
doc_path.write_text(doc, encoding="utf-8")

source = Path(".github/workflows/public-pages.yml").read_text(encoding="utf-8")
replacements = {
    "assert reg['meta']['record_count'] == 67180": "assert reg['meta']['record_count'] == 67179",
    "assert len(potenza_records) == 1035": "assert len(potenza_records) == 1034",
    "assert sum(r['source_status'] == 'listed' for r in potenza_records) == 216": "assert sum(r['source_status'] == 'listed' for r in potenza_records) == 215",
    "assert len({r['record_locator'] for r in potenza_records}) == 1035": "assert len({r['record_locator'] for r in potenza_records}) == 1034",
    "assert sum(bool(r['identifiers']) for r in potenza_records) == 1034": "assert sum(bool(r['identifiers']) for r in potenza_records) == 1033",
    "assert sum(bool(r['application_date']) for r in potenza_records) == 1035": "assert sum(bool(r['application_date']) for r in potenza_records) == 1034",
    "assert sum(bool(r['observed_listing_date']) for r in potenza_records) == 659": "assert sum(bool(r['observed_listing_date']) for r in potenza_records) == 658",
    "assert sum(bool(r['observed_expiry_date']) for r in potenza_records) == 659": "assert sum(bool(r['observed_expiry_date']) for r in potenza_records) == 658",
}
for old, new in replacements.items():
    if source.count(old) != 1:
        raise SystemExit(f"expected exactly one public-pages anchor {old!r}; got {source.count(old)}")
    source = source.replace(old, new)
anchor = "          scavone = [r for r in potenza_records if r['source_fields']['physical_locator'] == 'source-id:656']"
if source.count(anchor) != 1:
    raise SystemExit("unexpected Potenza public-pages anchor")
source = source.replace(
    anchor,
    "          assert not [r for r in potenza_records if r['source_fields']['physical_locator'] == 'source-id:237']\n" + anchor,
)
Path("tmp/potenza-public-pages.yml").write_text(source, encoding="utf-8")
print("prepared_potenza_approval", RAW, SEM, Counter(r["source_status"] for r in batches[0].records), "removed_source_id=237")

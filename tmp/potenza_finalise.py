from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import urllib.request
from pathlib import Path

from white_list_archive.parsers.potenza_webapp import parse_potenza_combined
from white_list_archive.publishing.public_national_registry import _semantic_digest

SOURCE_URL = "https://www.utgpotenza.it/data/vis_imprese.php?action=list&jtStartIndex=0&jtPageSize=2000&jtSorting=ragione_sociale%20ASC&cerca_ragione_sociale=&cerca_sede_legale=&cerca_stato_richiesta=0&cerca_sezione=0"
RAW_SHA = "24fbb61f7ae028a0a2fee8d7d4c89d42ceefdf18fc6d69298a1df0549b78c820"
SEM_SHA = "96b5227dd78fc83b78a2fd1516e8a5cfae6d482be97351f1e8c71c641e7e6316"
CHECK_AT = "2026-09-17T13:11:20Z"
HEADERS = {"User-Agent": "italian-anti-mafia-whitelist/1.0 (+https://github.com/colazeta/italian-anti-mafia-whitelist)"}


def get_source() -> bytes:
    req = urllib.request.Request(SOURCE_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as response:
        if response.status != 200:
            raise SystemExit(f"Potenza GET returned HTTP {response.status}")
        return response.read()


def dump_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one old fragment, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    # Reverify the reviewed source boundary twice immediately before mutation.
    one = get_source()
    time.sleep(2)
    two = get_source()
    if one != two:
        raise SystemExit("independent current Potenza captures differ")
    if hashlib.sha256(one).hexdigest() != RAW_SHA:
        raise SystemExit("Potenza source changed after approved drift audit")
    payload = json.loads(one)
    assert payload.get("Result") == "OK"
    assert int(payload.get("TotalRecordCount")) == 1035
    assert len(payload.get("Records", [])) == 1035
    assert len({str(r["id"]).strip() for r in payload["Records"]}) == 1035
    capture = Path("/tmp/potenza-current.json")
    capture.write_bytes(one)

    cfg_path = Path("data/publication/multi_prefecture_pilot.json")
    cfg_all = json.loads(cfg_path.read_text(encoding="utf-8"))
    pot = next(x for x in cfg_all["sources"] if x["source_key"] == "potenza-combined")
    assert pot["reference_date"] == "2026-09-15"
    assert pot["expected_source_rows"] == 1034
    assert pot["semantic_sha256"] == "c033d7b1f2d758f42e9b0a97d70e8f7f2278cb08608db86c2e7b600e1857cb34"
    assert pot["approval_mode"] == "semantic_sha256"
    pot["reference_date"] = "2026-09-17"
    pot["sha256"] = RAW_SHA
    pot["expected_source_rows"] = 1035
    pot["semantic_sha256"] = SEM_SHA
    pot["last_source_update"] = "2026-09-17"
    pot["last_source_update_basis"] = (
        "current mutable official web-application capture directly reverified on 17 September 2026; "
        "the date is an observation/reference boundary only and is not an inferred source-edition, "
        "company-decision or legal-effect date"
    )
    pot["notes"] = (
        "Official Ministry landing links the UTG Potenza public White List web application. Two independent "
        "complete current endpoint captures on 17 September 2026 were byte-identical and yielded 1,035 "
        "observations: 216 listed, 376 pending and 443 renewal/update in progress. Against the approved "
        "15 September boundary, source id 656 was added with explicit pending evidence and source id 359 "
        "changed from listed to renewal/update in progress through agg_incorso=1; no source ids were removed. "
        "Publication remains fail-closed on the independently approved full parsed source-semantic digest; "
        "raw capture SHA-256 remains observation provenance and no legal effect is inferred from the transition."
    )
    dump_json(cfg_path, cfg_all)

    cov_path = Path("data/monitoring/national_coverage.json")
    cov = json.loads(cov_path.read_text(encoding="utf-8"))
    pcov = next(x for x in cov["prefectures"] if x["authority_key"] == "potenza")
    assert pcov["latest_source_reference_date"] == "2026-09-15"
    assert "483f71b0481573651dc62e382e3e3e7a45cfd84509ec79f51a07194dbb3af0a6" in pcov["known_content_sha256"]
    pcov["latest_source_reference_date"] = "2026-09-17"
    pcov["last_successful_source_check_at"] = CHECK_AT
    pcov["last_attempted_source_check_at"] = CHECK_AT
    pcov["last_content_change_at"] = CHECK_AT
    pcov["last_successful_investigation_on"] = "2026-09-17"
    pcov["monitoring_status"] = "CURRENT"
    if RAW_SHA not in pcov["known_content_sha256"]:
        pcov["known_content_sha256"].append(RAW_SHA)
    if not any(c.get("authority_key") == "potenza" and c.get("content_sha256") == RAW_SHA for c in cov["checks"]):
        cov["checks"].append(
            {
                "authority_key": "potenza",
                "at": CHECK_AT,
                "evidence": "docs/sources/potenza-operational-check-2026-09-15.md",
                "error": None,
                "content_changed": True,
                "content_sha256": RAW_SHA,
            }
        )
    dump_json(cov_path, cov)

    inv_path = Path("data/source_registry/source_series_inventory.csv")
    inv = inv_path.read_text(encoding="utf-8")
    matches = re.findall(r"^potenza-combined,.*$", inv, flags=re.MULTILINE)
    if len(matches) != 1:
        raise SystemExit(f"expected one Potenza inventory row, found {len(matches)}")
    row = [
        "potenza-combined",
        "potenza",
        "WL-REGIME-L190-2012",
        "listed_and_applicant",
        "all",
        "custom_web_application",
        "https://www.utgpotenza.it/_whitelist.php",
        "linked_application_resolved",
        "2026-09-17",
        (
            "Current linked UTG Potenza web application revalidated 17 September 2026 by two byte-identical "
            f"independent complete endpoint GETs at SHA-256 {RAW_SHA}. The current response exposes 1,035 "
            "observations: 216 listed, 376 pending and 443 renewal/update in progress. Compared with the approved "
            "15 September boundary, source id 656 is newly present with explicit pending evidence and source id 359 "
            "explicitly moved from listed to renewal/update in progress through agg_incorso=1; no source ids were "
            f"removed. Production approval is pinned to semantic SHA-256 {SEM_SHA}; no legal effect is inferred."
        ),
    ]
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="").writerow(row)
    inv_path.write_text(inv.replace(matches[0], buf.getvalue(), 1), encoding="utf-8")

    doc_path = Path("docs/sources/potenza-operational-check-2026-09-15.md")
    doc = doc_path.read_text(encoding="utf-8")
    marker = "## Current-boundary revalidation — 17 September 2026"
    if marker in doc:
        raise SystemExit("17 September Potenza evidence section already exists unexpectedly")
    appendix = f"""

{marker}

A fresh current-boundary check was performed against the same official UTG Potenza data endpoint already established through the Ministry White List chain. Two independent complete GETs were byte-identical: **438,471 bytes**, SHA-256 **`{RAW_SHA}`**, `Result=OK`, `TotalRecordCount=1035`, and 1,035 distinct numeric source ids. The parser contract and source schema are unchanged. With the 17 September observation/reference boundary, the approved production semantic SHA-256 is **`{SEM_SHA}`**.

The current parsed population is **1,035 observations**: **216 listed**, **376 pending**, and **443 renewal/update in progress**. Identifier coverage is **1,034/1,035**, with the same single raw-only malformed identifier already preserved conservatively; all 1,035 observations expose an application date, while listing and expiry dates remain present for 659 observations. Requested activities remain empty because the combined endpoint still does not expose positive per-company statutory-section evidence.

The change against the approved 15 September public boundary is narrow and source-identifiable. **No source ids were removed.** Source id **656**, `SCAVONE & C. S.R.L.` (`01652690767`), is newly present with `stato_richiesta=1`, `agg_incorso=0`, and application date **2026-09-16**; it is therefore recorded as `pending`. Existing source id **359**, `MALASPINA S.R.L.`, now exposes `stato_richiesta=2`, `agg_incorso=1`, retaining its explicit listing and expiry dates; the parser therefore records the already-supported source state `renewal_update_in_progress` instead of `listed`. This records only the current public-source observation. It does **not** infer revocation, cancellation, denial, removal, or any other legal effect.
"""
    doc_path.write_text(doc.rstrip() + appendix + "\n", encoding="utf-8")

    wf_path = Path(".github/workflows/public-pages.yml")
    wf = wf_path.read_text(encoding="utf-8")
    wf = replace_once(wf, "assert reg['meta']['record_count'] == 57969", "assert reg['meta']['record_count'] == 57970", "national public count")
    for old, new in {
        "assert len(potenza_records) == 1034": "assert len(potenza_records) == 1035",
        "assert sum(r['source_status'] == 'listed' for r in potenza_records) == 217": "assert sum(r['source_status'] == 'listed' for r in potenza_records) == 216",
        "assert sum(r['source_status'] == 'pending' for r in potenza_records) == 375": "assert sum(r['source_status'] == 'pending' for r in potenza_records) == 376",
        "assert sum(r['source_status'] == 'renewal_update_in_progress' for r in potenza_records) == 442": "assert sum(r['source_status'] == 'renewal_update_in_progress' for r in potenza_records) == 443",
        "assert len({r['record_locator'] for r in potenza_records}) == 1034": "assert len({r['record_locator'] for r in potenza_records}) == 1035",
        "assert sum(bool(r['identifiers']) for r in potenza_records) == 1033": "assert sum(bool(r['identifiers']) for r in potenza_records) == 1034",
        "assert sum(bool(r['application_date']) for r in potenza_records) == 1034": "assert sum(bool(r['application_date']) for r in potenza_records) == 1035",
    }.items():
        wf = replace_once(wf, old, new, old)
    anchor = "          assert gap[0]['source_fields']['in_aggiornamento'] == '1'\n"
    extra = anchor + """          scavone = [r for r in potenza_records if r['source_fields']['physical_locator'] == 'source-id:656']
          assert len(scavone) == 1
          assert scavone[0]['name'] == 'SCAVONE & C. S.R.L.'
          assert scavone[0]['identifier_field_raw'] == '01652690767'
          assert scavone[0]['source_status'] == 'pending'
          assert scavone[0]['application_date'] == '2026-09-16'
          malaspina = [r for r in potenza_records if r['source_fields']['physical_locator'] == 'source-id:359']
          assert len(malaspina) == 1
          assert malaspina[0]['name'] == 'MALASPINA S.R.L.'
          assert malaspina[0]['source_status'] == 'renewal_update_in_progress'
          assert malaspina[0]['observed_listing_date'] == '2018-10-18'
          assert malaspina[0]['observed_expiry_date'] == '2026-10-18'
          assert malaspina[0]['source_fields']['in_aggiornamento'] == '1'
"""
    wf_path.write_text(replace_once(wf, anchor, extra, "Potenza reviewed-delta assertions"), encoding="utf-8")

    browser_path = Path("tests/public_portal_browser.cjs")
    browser = browser_path.read_text(encoding="utf-8")
    browser = replace_once(browser, "assert.equal(stats.total,57969);", "assert.equal(stats.total,57970);", "browser national total")
    for old, new in {
        "assert.equal(potenza.length,1034);": "assert.equal(potenza.length,1035);",
        "assert.equal(potenza.filter(r=>r.source_key==='potenza-combined').length,1034);": "assert.equal(potenza.filter(r=>r.source_key==='potenza-combined').length,1035);",
        "assert.deepEqual(statusCounts(potenza),{listed:217,pending:375,renewal_update_in_progress:442});": "assert.deepEqual(statusCounts(potenza),{listed:216,pending:376,renewal_update_in_progress:443});",
        "assert.equal(new Set(potenza.map(r=>r.record_locator)).size,1034);": "assert.equal(new Set(potenza.map(r=>r.record_locator)).size,1035);",
        "assert.equal(potenza.filter(r=>r.identifiers.length>0).length,1033);": "assert.equal(potenza.filter(r=>r.identifiers.length>0).length,1034);",
        "assert.equal(potenza.filter(r=>r.application_date!=='').length,1034);": "assert.equal(potenza.filter(r=>r.application_date!=='').length,1035);",
    }.items():
        browser = replace_once(browser, old, new, old)
    banchor = "      assert.equal(gap[0].source_fields.in_aggiornamento,'1');\n"
    bextra = banchor + """      const scavone=potenza.filter(r=>r.source_fields.physical_locator==='source-id:656');
      assert.equal(scavone.length,1);
      assert.equal(scavone[0].name,'SCAVONE & C. S.R.L.');
      assert.equal(scavone[0].identifier_field_raw,'01652690767');
      assert.equal(scavone[0].source_status,'pending');
      assert.equal(scavone[0].application_date,'2026-09-16');
      const malaspina=potenza.filter(r=>r.source_fields.physical_locator==='source-id:359');
      assert.equal(malaspina.length,1);
      assert.equal(malaspina[0].name,'MALASPINA S.R.L.');
      assert.equal(malaspina[0].source_status,'renewal_update_in_progress');
      assert.equal(malaspina[0].observed_listing_date,'2018-10-18');
      assert.equal(malaspina[0].observed_expiry_date,'2026-10-18');
      assert.equal(malaspina[0].source_fields.in_aggiornamento,'1');
"""
    browser_path.write_text(replace_once(browser, banchor, bextra, "browser Potenza reviewed-delta assertions"), encoding="utf-8")

    # Direct validation of the captured current bytes under the new approved config.
    cfg_all = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg = next(x for x in cfg_all["sources"] if x["source_key"] == "potenza-combined")
    batch = parse_potenza_combined(capture, cfg)
    assert cfg["reference_date"] == "2026-09-17"
    assert cfg["expected_source_rows"] == 1035
    assert _semantic_digest(batch.records) == SEM_SHA
    assert batch.diagnostics["status_counts"] == {"listed": 216, "pending": 376, "renewal_update_in_progress": 443}
    assert batch.diagnostics["identifier_coverage"] == 1034
    assert batch.diagnostics["application_date_coverage"] == 1035
    assert batch.diagnostics["listing_date_coverage"] == 659
    assert batch.diagnostics["expiry_date_coverage"] == 659
    by_id = {r["source_fields"]["source_id"]: r for r in batch.records}
    assert by_id["656"]["source_status"] == "pending"
    assert by_id["656"]["application_date"] == "2026-09-16"
    assert by_id["359"]["source_status"] == "renewal_update_in_progress"
    print("Potenza reviewed current boundary validated")


if __name__ == "__main__":
    main()

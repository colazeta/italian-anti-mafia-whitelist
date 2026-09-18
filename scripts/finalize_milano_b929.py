from __future__ import annotations

import csv
import io
import json
from pathlib import Path

COMBINED_SHA = "b92945af542b89ca99122d60a6f2d1c4c22359bb2c1bbe7c40672c7738bbc58a"
REGISTERED_SHA = "20714806f285559da9bbfb51203e7329e990112224643bcb6a0bed7a473ef8e2"
VERIFIED_AT = "2026-09-18T17:35:50Z"
EVIDENCE_DOC = "docs/sources/milano-source-transition-2026-09-18-b929.md"
TRANSITION_IDS = (
    "00772460150",
    "03998810612",
    "06363290963",
    "06895800966",
    "07299620158",
    "07883430964",
    "10899610967",
    "11328240152",
    "11350850969",
    "13102060152",
)


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def update_parser() -> None:
    path = "src/white_list_archive/parsers/milano_webapp.py"
    replace_once(path, 'PARSER_VERSION = "4"', 'PARSER_VERSION = "5"')
    replace_once(
        path,
        '    "listed": 938,\n    "renewal_update_in_progress": 516,\n    "pending": 1157,',
        '    "listed": 948,\n    "renewal_update_in_progress": 516,\n    "pending": 1147,',
    )


def update_publication() -> None:
    p = Path("data/publication/multi_prefecture_pilot.json")
    doc = json.loads(p.read_text(encoding="utf-8"))
    matches = [x for x in doc["sources"] if x["source_key"] == "milano-combined"]
    if len(matches) != 1:
        raise RuntimeError(f"expected one Milano publication source, got {len(matches)}")
    src = matches[0]
    expected = {
        "authority_key": "milano",
        "population_scope": "listed_and_applicant",
        "reference_date": "2026-09-18",
        "sha256": "8dd6ce95d933f6b892e056bdec5bc78a985bb6485504055cd7cbde0e8cbdad5c",
        "expected_sector_rows": 4208,
        "expected_source_rows": 2611,
    }
    for key, value in expected.items():
        if src.get(key) != value:
            raise RuntimeError(f"publication precondition drift for {key}: {src.get(key)!r} != {value!r}")
    src["sha256"] = COMBINED_SHA
    src["last_source_update"] = "2026-09-18"
    src["last_source_update_basis"] = (
        "Later 18 September 2026 direct operational-source verification after a fail-closed byte-identity change: "
        "two cache-bypassed captures of each official Milano view were byte-identical, and the reviewed parser boundary "
        "remained structurally stable at 4,208 sector rows / 2,611 observations."
    )
    src["notes"] = (
        f"The mutable combined operational table was re-verified later on 18 September 2026 at 969,548 bytes "
        f"(SHA-256 {COMBINED_SHA}). Identity membership remains 2,611 observations with no additions or removals "
        "against the live boundary; ten retained pending identities are now source-explicitly listed with listing date "
        "18 September 2026 and expiry date 18 September 2027, yielding 948 listed, 516 renewal/update in progress and "
        f"1,147 pending. The registered-only sibling was independently stable at 561,860 bytes (SHA-256 {REGISTERED_SHA}) "
        "and its 1,464 identities exactly equal the combined non-pending identity set. No legal effect is inferred beyond "
        f"the source-published status wording. See {EVIDENCE_DOC}."
    )
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_inventory() -> None:
    p = Path("data/source_registry/source_series_inventory.csv")
    lines = p.read_text(encoding="utf-8").splitlines()
    indexes = [i for i, line in enumerate(lines) if line.startswith("milano-combined,")]
    if len(indexes) != 1:
        raise RuntimeError(f"expected one Milano inventory line, got {len(indexes)}")
    old = next(csv.reader([lines[indexes[0]]]))
    if len(old) != 10 or old[0] != "milano-combined" or old[8] != "2026-09-18":
        raise RuntimeError(f"unexpected Milano inventory row: {old!r}")
    row = old[:9] + [
        f"Official mutable combined table re-verified later on 18 September 2026: repeated captures were byte-identical "
        f"at SHA-256 {COMBINED_SHA} (969,548 bytes), with the same 4,208 sector rows and 2,611 logical observations. "
        "No identities were added or removed; ten retained pending identities are now source-explicitly listed, giving "
        "948 listed / 516 renewal-update / 1,147 pending. The registered-only sibling was independently byte-identical at "
        f"SHA-256 {REGISTERED_SHA} (561,860 bytes), with 1,464 identities exactly matching the combined non-pending set. "
        f"See {EVIDENCE_DOC}."
    ]
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(row)
    lines[indexes[0]] = buf.getvalue()
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_coverage() -> None:
    p = Path("data/monitoring/national_coverage.json")
    doc = json.loads(p.read_text(encoding="utf-8"))
    matches = [x for x in doc["authorities"] if x["authority_key"] == "milano"]
    if len(matches) != 1:
        raise RuntimeError(f"expected one Milano coverage authority, got {len(matches)}")
    entry = matches[0]
    if entry.get("latest_source_reference_date") != "2026-09-18":
        raise RuntimeError("Milano coverage reference date drift")
    for key in ("last_successful_source_check_at", "last_attempted_source_check_at", "last_content_change_at"):
        entry[key] = VERIFIED_AT
    entry["last_successful_investigation_on"] = "2026-09-18"
    entry["monitoring_status"] = "CURRENT"
    for key in ("completion_evidence", "evidence"):
        if EVIDENCE_DOC not in entry[key]:
            entry[key].append(EVIDENCE_DOC)
    for sha in (COMBINED_SHA, REGISTERED_SHA):
        if sha not in entry["known_content_sha256"]:
            entry["known_content_sha256"].append(sha)
    history = doc.setdefault("check_history", [])
    item = {
        "authority_key": "milano",
        "at": VERIFIED_AT,
        "evidence": EVIDENCE_DOC,
        "error": None,
        "content_changed": True,
        "content_sha256": COMBINED_SHA,
    }
    if not any(x.get("authority_key") == "milano" and x.get("content_sha256") == COMBINED_SHA for x in history):
        history.append(item)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_public_assertions() -> None:
    path = ".github/workflows/public-pages.yml"
    replace_once(path, "assert sum(r['source_status'] == 'listed' for r in milano_records) == 938", "assert sum(r['source_status'] == 'listed' for r in milano_records) == 948")
    replace_once(path, "assert sum(r['source_status'] == 'pending' for r in milano_records) == 1157", "assert sum(r['source_status'] == 'pending' for r in milano_records) == 1147")
    replace_once(path, "assert sum(bool(r['application_date']) for r in milano_records) == 1157", "assert sum(bool(r['application_date']) for r in milano_records) == 1147")
    replace_once(path, "assert sum(bool(r['observed_listing_date']) for r in milano_records) == 938", "assert sum(bool(r['observed_listing_date']) for r in milano_records) == 948")
    replace_once(path, "assert sum(bool(r['observed_expiry_date']) for r in milano_records) == 938", "assert sum(bool(r['observed_expiry_date']) for r in milano_records) == 948")
    anchor = "          assert all(current_milano[k]['source_status'] == 'renewal_update_in_progress' and not current_milano[k]['observed_listing_date'] and not current_milano[k]['observed_expiry_date'] for k in ('00936150150','13072070157'))\n"
    ids = ",".join(repr(x) for x in TRANSITION_IDS)
    insertion = anchor + (
        f"          assert all(current_milano[k]['source_status'] == 'listed' and not current_milano[k]['application_date'] "
        f"and current_milano[k]['observed_listing_date'] == '2026-09-18' and current_milano[k]['observed_expiry_date'] == '2027-09-18' for k in ({ids}))\n"
    )
    replace_once(path, anchor, insertion)


def update_browser_assertions() -> None:
    path = "tests/public_portal_browser.cjs"
    replace_once(path, "assert.deepEqual(statusCounts(milano),{listed:938,pending:1157,renewal_update_in_progress:516});", "assert.deepEqual(statusCounts(milano),{listed:948,pending:1147,renewal_update_in_progress:516});")
    replace_once(path, "assert.equal(milano.filter(r=>r.application_date!=='').length,1157);", "assert.equal(milano.filter(r=>r.application_date!=='').length,1147);")
    replace_once(path, "assert.equal(milano.filter(r=>r.observed_listing_date!=='').length,938);", "assert.equal(milano.filter(r=>r.observed_listing_date!=='').length,948);")
    replace_once(path, "assert.equal(milano.filter(r=>r.observed_expiry_date!=='').length,938);", "assert.equal(milano.filter(r=>r.observed_expiry_date!=='').length,948);")
    anchor = "      for(const k of ['00936150150','13072070157']){assert.equal(currentMilano[k].source_status,'renewal_update_in_progress');assert.equal(currentMilano[k].observed_listing_date,'');assert.equal(currentMilano[k].observed_expiry_date,'');}\n"
    ids = ",".join(repr(x) for x in TRANSITION_IDS)
    insertion = anchor + (
        f"      for(const k of [{ids}]){{assert.equal(currentMilano[k].source_status,'listed');assert.equal(currentMilano[k].application_date,'');assert.equal(currentMilano[k].observed_listing_date,'2026-09-18');assert.equal(currentMilano[k].observed_expiry_date,'2027-09-18');}}\n"
    )
    replace_once(path, anchor, insertion)


def write_evidence() -> None:
    p = Path(EVIDENCE_DOC)
    if p.exists():
        raise RuntimeError(f"evidence doc already exists: {EVIDENCE_DOC}")
    p.write_text(
        f"""# Milano source transition — later 18 September 2026 boundary (`b929`)

## Scope

A national fail-closed publication build detected that the official mutable Milano combined White List table no longer matched the approved same-day SHA-256 `8dd6ce95d933f6b892e056bdec5bc78a985bb6485504055cd7cbde0e8cbdad5c`. This review approves only the newly observed official-source boundary. It does not infer any legal effect from a source status transition.

## Independent source captures

Two cache-bypassed captures of `https://whitelist.prefmi.it/elenco/elenco.php` were byte-identical at **969,548 bytes**, SHA-256 `{COMBINED_SHA}`. Two independent captures of the official registered-only sibling, `https://whitelist.prefmi.it/elenco/elenco_iscritte.php`, were also byte-identical at **561,860 bytes**, SHA-256 `{REGISTERED_SHA}`.

The combined source remains structurally stable at **10 tables, 4,208 sector rows, 2,611 logical observations and 2,611 strict identifiers**. The reviewed status distribution is **948 listed, 516 renewal/update in progress and 1,147 pending**. There is still one nonblank source note. The registered-only sibling contains **1,464 logical identities**; its identity set exactly equals the 1,464 non-pending identities in the combined source, with no missing or extra identifiers.

## Exact semantic transition from the live public boundary

Comparison with the live 61,591-record public registry found **zero Milano additions, zero removals and ten retained-identity changes**. Each of the following identities moves from `pending` to a source-explicit dated listed row, retaining the same statutory section membership. In every case the current source publishes listing date **18 September 2026** and expiry date **18 September 2027**, and the former application date is no longer represented as the current status field:

- `00772460150` — GIUSEPPE BOSISIO SRL — section 4; previous application date 27 February 2025.
- `03998810612` — MM COSTRUZIONI DI KHALIFA WALID — section 10; previous application date 25 March 2026.
- `06363290963` — MARAZZI ANGELO SRL — sections 1 and 5; previous application date 27 November 2023.
- `06895800966` — MAE ambiente s.r.l. — section 10; previous application date 25 March 2026.
- `07299620158` — Società Gas Metano SGM Impianti Srl — sections 1, 3 and 5; previous application date 27 May 2022.
- `07883430964` — GLOBAL SENDING SRL — section 6; previous application date 16 August 2023.
- `10899610967` — M.G. INSTALLAZIONI S.R.L.S. — section 3; previous application date 23 March 2026.
- `11328240152` — MAGI S.R.L. — section 4; previous application date 6 March 2026.
- `11350850969` — MAFERR SOCIETA' A RESPONSABILITA' LIMITATA — section 4; previous application date 26 November 2025.
- `13102060152` — GLI SPECIALISTI DEL VERDE SRL — sections 3 and 5; previous application date 9 March 2026.

No identity is treated as revoked, denied, cancelled or otherwise legally changed merely because of a mutable-view transition. The repository records only the source-published current status and dates.

`durable_evidence_verified` remains false for Milano pending the separately governed hosted-evidence verification; this source-transition approval concerns the official-source observation boundary only.
""",
        encoding="utf-8",
    )


def main() -> None:
    update_parser()
    update_publication()
    update_inventory()
    update_coverage()
    update_public_assertions()
    update_browser_assertions()
    write_evidence()


if __name__ == "__main__":
    main()

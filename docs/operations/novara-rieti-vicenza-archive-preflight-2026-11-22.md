# Exact archived candidates — Novara, Rieti and Vicenza (22 November 2026)

## Evidence and scope

A read-only preflight uses the existing protected \`Transform reviewed captures into private observations\` workflow, on its existing \`evidence-archive\` environment and R2 read-only primitive. No new workflow, credential, scheduled task, writer, approval or publication. The six XLSX pins below were read from \`robot-state@2890d347a1dd58a5abe4068a46ed8994ca5f6f54\`, last checked 21 November 2026 at 12:56–13:04 UTC. The robot reports for each item \`role=candidate\`, equal \`sha256\` / \`archived_sha256\`, a byte length and an associated capture. **These are robot metadata claims until independently rehashed against retrieved R2 bytes.** No SourceSeries binding or public-edition status follows from them.

| Authority | Logical population (provisional) | Immutable robot SHA-256 | Reported bytes | Archive/file clue |
|---|---|---|---:|---|
| Novara | listed | \`27a4514dcb0ddb77786c64faf186b7b855d9f616389ec8c3d4bec504bea771a2\` | 37,187 | \`imprese-iscritte-white-list-330.xlsx\` |
| Novara | applicant | \`ef0486870ddb136fdf2e876a563e1b3c91e814bfcaf27a1d3a9baf10dd76cdcf\` | 32,038 | \`white-list-richieste-da-evadere-454.xlsx\` |
| Rieti | listed | \`09386dcff207a094cfd796b9f040966d232dcd8967b293a8b5d66b99a45114f4\` | 50,161 | \`iscritti-new_0.xlsx\` |
| Rieti | applicant | \`e229ded9a6098d7f5ffea5ad6599cfdf46f146655676fe5a2288f3c79dca4a75\` | 46,244 | \`richiedenti-iscrizione-new_0.xlsx\` |
| Vicenza | listed | \`f1af1fe0a99c8fafcf05537721b39a80c2072a4ea524f2c61b4b9f5466c43f50\` | 68,748 | \`antimafia-white_list-imprese_iscritte_1.xlsx\` |
| Vicenza | applicant | \`88c10b8aee68ec4359f33572dc72d7222195684f7a5b0ae392586d29c3975c9d\` | 11,101 | \`antimafia-white-list-imprese-richiedenti_1.xlsx\` |

The Novara robot also reports parallel **PDF** versions for listed/applicants with different SHAs, not yet established equivalent to these XLSX files. Neither 330/454 nor earlier 324/448 filename labels are validated row counts. HTTP Last-Modified dates for Novara (20 November), Rieti (16 November) and Vicenza (18 November) are **not document-internal source reference dates**.

## Production acceptance boundary

The new bounded workbook audit independently calls the existing content-addressed \`read_digest_verified\` for all six exact digests, verifies exact byte lengths, and counts the physical worksheets, row shapes, cell shapes, hidden sheets and formulas **without exposing any source values, sheet names or individual locators**. It explicitly returns \`source_edition_approved=false\`, \`privacy_approved=false\` and \`public_release_eligible=false\`. Per-source failures retain only an exception **type** and do not relabel independent worker failures as successful. A pass proves immutable original-byte readback and initial workbook structural QA only; it cannot validate true logical row counts, status/sector mapping, provenance, document date, complete record digests, legal events or privacy.

For actual public expansion, independently establish the latest official edition and authority/register attribution, reconcile each complete population's physical records, compare Novara PDF/XLSX alternatives and prior archived revisions, review source-status/sector and personal-data edge cases, then pass the finite reviewed intent, CI, serial selector and sole publisher with five live SHA/size readbacks. Any missing original, unexpected workbook layout or ambiguity remains review required, not a source approved for publication. Preserve existing 74-authority release and rollback.

This is incremental **source-qualification work** on three previously unpublished authorities, not three added authorities or a ready candidate release.


## First protected readback and strict follow-up (22 November 2026, source-only)

The actual existing protected worker [run #44962065577](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/44962065577), shard 0, independently retrieved and SHA/size-verified **all six** R2 originals. The first structural pass validated the two Rieti XLSX workbooks: listed worksheet **274 physical rows / 13 columns** (266 multi-cell rows, 258 formulas), applicant worksheet **296 physical rows / 13 columns** (279 multi-cell rows, no formula cells). These are physical worksheet rows including non-record material, **not** 274/296 approved firms. The observed 16-character cell-shape counts (64/63 respectively) are privacy-screening clues, not proof of personal or legal identity. All other four original bytes were intact, but their workbook structural audit returned a redacted \`ValueError\`, so only **2/6** structures passed and the standalone audit exited with code 1. The GHA step's continuing-on-error is not success of that audit or of the full worker (which completed \`failure\` for distinct independent reasons).

This follow-up supports XLSX producers whose dimension hints are **absent**, but it still enforces exact SHA/byte length, byte-size, sheet/row/column/cell bounds on the **physically traversed cells**, declared-dimension bounds when present, and rejects contradictions, unknown sheet types and empty/one-cell-only sheets. All safely reportable failure reasons are mapped to a fixed vocabulary, while unexpected library errors are redacted. A new CI/production run is necessary before claiming any additional workbook structurally accepted; no potential date, firm count, source status, sector mapping, privacy result or public release is thereby approved.


## Finite coordinate diagnostic for quarantined worksheet declarations (proposed)

For the four Novara/Vicenza sources rejected by the original strict workbook
scanner as \`declared_dimensions_out_of_bounds\`, the same existing protected,
read-only preflight can now report a **diagnostic-only** comparison between
declared worksheet dimensions and bounded encoded XML cell/row marker counts
and maxima. It never logs worksheet titles, private source strings, individual
cell coordinates, original document bytes or archive paths. Only exact
SHA-256/size verified R2 originals enter this diagnostic.

The XML inspection has separate finite constraints (24 MB per worksheet,
48 MB total declared uncompressed XML, 600,000 cell elements and 150,000 row
elements per part), rejects document type declarations, and reports controlled
reason codes on failure. This does **not** increase the original production
acceptance limits of 50,000 rows, 120 columns and 500,000 physically scanned
cells, nor does a coordinate marker prove a nonempty business record. The
independent counters \`source_bytes_verified\` and \`originals_verified\` now
separate authenticated original-byte readbacks from accepted structural audits.

**Acceptance remains blocked** for all four until source-specific physical
extent/format QA, complete listed/applicant reconciliation, sector/status,
official edition date, source identity and privacy checks succeed. This is
code proposed for review; no claim of successful production diagnostics,
approved edition or released authority follows until exact-head CI and
protected runtime readback are verified.


## Production geometry baseline and next diagnostic gate — 22 November 2026

The previous diagnostic was **actually verified in production** by protected
[run #44973521337](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/44973521337),
shard 0/job 137058266684, on merged main \`9db184f01f4ec0e1bdeb96722412809fe5b3b67e\`.
Exact R2 SHA/size readbacks were **6/6**; strict structural audits remained
**2/6** (Rieti both populations only), with Novara/Vicenza **4/4** retained as
\`declared_dimensions_out_of_bounds\`. This is not edition approval or a
globally successful transform run.

- Novara listed: declared 385 rows × 1,024 columns; primary XML part 385
  encoded row markers/2,695 cell markers, maximum encoded coordinate 385 × 7.
  A separate 10 × 8, 80-cell XML part also exists.
- Novara applicants: declared 242 × 1,024; primary part 242 rows/1,694 cells,
  maximum coordinate 242 × 7.
- Vicenza listed: declared 1,048,576 × 10; 1,279 row markers/8,746 cell
  markers, with an encoded coordinate reaching row 1,048,576.
- Vicenza applicants: declared 1,048,576 × 6; 189 row markers/320 cell
  markers, also reaching the terminal worksheet row.

The next revision **only proposes a diagnostic** to distinguish cell/row
geometry from potential XML payload markers. For every bounded worksheet part,
it counts how many cell elements exceed the existing 50,000-row/120-column
acceptance envelope, how many contain an XLSX value, formula or inline-string
*element marker* (not actual approved or necessarily nonempty content), how
many do not, how many contain formula markers, and the maximum row/column
bearing those markers. Missing cell coordinates are counted separately, never
assumed to fall within the permitted region. All source values and individual
locations remain unobserved/unlogged; parsing remains bounded and DTDs remain
prohibited. These marker counters can help distinguish empty styled terminal
cells from potentially substantive far-row content, **not** prove that a row
may be ignored or that an edition is ready.

Production acceptance of these **new** counters remains pending until
exact-head CI, serial merge, and independent protected run readback. The
original four structural quarantines and full edition/date/status/sector,
identity and privacy gates stay in force. No source/parser binding, finite
publication intent, selector, release, historical capture or storage privilege
is changed. Work on the independent current-edition delta continues; a
diagnostic does not reduce any publicly selected lag.

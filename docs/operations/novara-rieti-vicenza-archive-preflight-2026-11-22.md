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

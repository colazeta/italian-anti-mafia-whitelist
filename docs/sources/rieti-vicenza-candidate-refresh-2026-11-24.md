# Rieti and Vicenza: exact candidate refresh, 24 November 2026

The current robot-state `d59c67677586b0b6cb373d69bcdcb1713fc0d1bd` (full state blob
`77c9d4c6a1b09419916861c5eba27c7d00a9c56f`) associates the following XLSX resource
and archived SHA-256 values; both digests agree for each resource. These are
candidate populations, not approved bindings or edition dates.

| Authority | Candidate population | SHA-256 | Bytes |
| --- | --- | --- | ---: |
| Rieti | listed | 9ca5fcf9be4e7447c197f3dd94ba5b7f4a8b7656853aca0a7f2837159a4892f7 | 50306 |
| Rieti | applicant | 8eed8bfc3b094c3750a5410063e9142365945e1a56a939177849e07f51c55b03 | 46364 |
| Vicenza | listed | f1af1fe0a99c8fafcf05537721b39a80c2072a4ea524f2c61b4b9f5466c43f50 | 68748 |
| Vicenza | applicant | 624d3b2214b3afae309d1f12787dc4957093d96e7bf0ccf3ff5c952ceb7385f4 | 14695 |

The [Rieti official landing](https://prefettura.interno.gov.it/it/prefetture/rieti/evidenza/white-list)
identifies both populations; the prior direct check returned 403. Both selected
candidate resources have HTTP Last-Modified 21 November 2026; neither this nor
the capture timestamp is an edition date. The [Vicenza landing](https://prefettura.interno.gov.it/it/prefetture/vicenza/evidenza/white-list)
was previously corroborated as updated on 23 November. The listed resource is
unchanged, and the applicant resource has a new digest and HTTP Last-Modified
23 November. These clues do not prove the document reference dates.

The earlier Rieti pair (09386dcf / e229ded9) and earlier Vicenza applicant
(88c10b8a) remain archived, with prior protected receipts retained in #225.
No old physical count or review outcome is transferred to the new bytes.
The existing bounded protected probe now checks the newer exact pairs; Novara
is unchanged. It retains all original dimension and XML diagnostic bounds,
privacy redaction, and fail-closed eligibility. No new workflow, privileges,
source binding, publication intent or selector changes. Both populations remain
acquisition_or_review_required until exact readback, independent content/edition
and privacy review, and appropriate parser acceptance.

Lecce independent lane: protected job 138291569921 on #357 verified 2/2 originals
and 2/2 physical profiles. Both populations contain the 19/11/2026 marker on
every page (83 listed / 9 applicant). This is documentary corroboration, not
edition approval. Listed: 2,220 physical rows, 1,815 data-shaped, 861 exact tuple
groups (not firms), one unclassified physical row, three unreviewed status
clues, 27 data-shaped rows without an identifier syntax match, four malformed
nonblank date rows and one blank-date row. Applicants: 95 physical rows, 82
data-shaped and one without identifier syntax. All approval flags are false.
Do not silently reuse the September positional repair or infer administrative
events. The official-date and privacy reviews remain open.

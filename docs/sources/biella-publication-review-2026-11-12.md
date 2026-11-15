# Biella: reviewed 12 November 2026 source update

The official embedded page, not the older dedicated applicant page, contains both
populations: https://prefettura.interno.gov.it/it/prefetture/biella/evidenza/white-list.
It explicitly states **Giovedì 12 Novembre 2026, ore 10:49**. This is a page-update
and source-reference date; it is not a company decision or legal-effect date.

The selected original is the 204,517-byte HTML with SHA-256
`2f12c48f90ac54c3dc8f7039ede87377b98ed13e1adabfb81d0456f0d889b53a`.
Both logical SourceSeries must verify their own authentic capture provenance for
the same original. The public candidate uses **raw SHA approval**: if current
wrapper bytes change it fails, rather than silently using an unarchived wrapper.
The reviewed semantic digests are additional review invariants in `biella_review`.

| Population | Physical rows | Public observations | Source statuses | Structured identifiers | Raw-only identifiers | Blank source dates |
|---|---:|---:|---|---:|---:|---|
| listed | 240 sector rows | 132 | 108 listed; 24 renewal/update | 92 | 40 | 1 expiry |
| applicant | 111 application rows | 111 | 91 listed; 16 pending; 4 renewal/update | 109 | 2 | 1 application |

The existing physical family v2 is reused. Every nonempty physical row is
classified, including strict preamble/section/activity/header rows. Unknown widths
or text fail closed. The 108 listed-sector repetitions are grouped only under the
family's existing identity/date/status agreement. Conflicting dates remain separate
observations. The applicant table has 110 family-normalised source identities in
111 observations: these are retained, not canonical entities or discarded duplicates.
All raw identifiers and blank dates remain raw/blank, with no inferred correction.

The exact selected public baseline has 130 listed-source and 109 applicant-source
observations. Its malformed/raw-only identifier counts were already 40 and 2;
these do not represent a newly introduced identifier loss. A preliminary direct
page comparison found no previously observed textual name/raw-identifier key
absent in the new tables; common keys contain explicit source status/date/activity
changes. Such textual comparisons are review aids, not canonical identity or
inferred administrative events.

The candidate is **+4 documentary presences**, 74,483 → **74,487**, retaining
74/106 Prefectures, 77 registers and 142 SourceSeries. Both Biella source dates
move from 26 August to 12 November: an official-update gap of **78 days → 0 days**.
This does not make the other authorities current.

Only these two scopes are newly parsed. The other **140 scopes**, including the
five previously reacquired legacy scopes, are composed from the selected five-file
SHA-verified public derivative. Ferrara reconstruction receives a full existing
record/report digest binding alongside the unchanged Pordenone binding. A small
binding collection selects exactly one complete source descriptor; it cannot
transfer approval across sources. The already explicit physical-parser identity
mapping is accepted consistently for preserved Cosenza/Ferrara provenance, while
unknown parser identities still fail. Original record fields, parser versions,
source/check dates and reports remain exact outside Biella.

Acceptance remains separate: immutable R2 original/capture readback; full physical
and semantic source QA; CI/PostgreSQL; exact zero-change outside-scope row **and
report** audit; public contract/privacy; desktop/mobile and official-link checks;
immutable candidate release; selector PR and regenerated national monitoring;
candidate build materialisation of the robot view from the selected-release ledger;
sole **Public retro portal** deployment; all five live SHA/size readbacks. A source
profile, successful build or candidate tag alone is not publication. The old
selected release remains rollback. No canonical-model or independent-recovery
completion is claimed.

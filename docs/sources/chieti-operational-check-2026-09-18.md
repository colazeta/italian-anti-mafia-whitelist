# Chieti White List operational check — 18 September 2026

The Prefettura di Chieti official White List surface was revalidated on 18 September 2026. The current registered-company page exposes **Elenco Iscritti White List - Agg. 18 Settembre 2026** and the current applicant page exposes **Elenco Richiedenti Iscrizione in White List - Agg. 18 Settembre 2026**. Both are legacy Word (`.doc`) attachments, parsed through `antiword` table output rather than inferred from rendered prose.

Two independent cache-bypassed GETs of each current attachment were byte-identical: registered companies `09c9b3ae1b1f4145c2a3795738a8d80d872c9816752cedb31b34cd730d801ddd`; applicants `2628230c417cf7b961d4a22490ba04f1b548c512782bd19a211890e11df54dc1`.

The registered attachment contains 1,352 activity-sector rows across ten headings. Exact repeated observations across sectors are grouped conservatively into **759 observations**: 544 `listed`, 204 `renewal_update_in_progress`, 10 `expired_observed`, and one `cancellation_related`. Structured identifier coverage is 731/759. Seven grouped observations retain non-normalised listing-date typography and 12 retain non-normalised expiry-date typography. One registered sector row has a blank company-name cell but an explicit office and identifier; it is retained without inferential filling. Legacy document metadata contains a stale Teramo template title; source identity rests on the Chieti official pages, current attachment links and table content.

The applicant attachment contains **177 observations**, all retained: 169 `pending`, seven `other_or_unknown` for explicit archived or transferred-competence outcomes, and one `rejected_or_denied` for the explicit interdittiva outcome. Structured identifier coverage is 173/177. Five rows have malformed or missing application dates and preserve their raw source values.

Publication is byte-pinned (`raw_sha256`) and fail-closed on activity headings, row/observation denominators, applicant outcome vocabulary, status distributions and identifier coverage. Both listed and applicant populations are positively evidenced.

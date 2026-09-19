# Imperia White List operational check — 19 September 2026

## Official publication surface

The current official Prefettura di Imperia White List landing page positively exposes two distinct current populations: **ELENCO DELLE DITTE ISCRITTE WL** and **ELENCO DITTE CHE HANNO PRESENTATO ISTANZA DI ISCRIZIONE**. The landing metadata states **Ultimo aggiornamento: 18 September 2026, 10:54**. This is positive population evidence; no applicant population is inferred from search failure or absence. The publication configuration preserves 18 September as the explicit landing update/reference boundary only and does not promote it to a company decision or legal-effect date.

## Content-addressed evidence

Two independent cache-bypassed GETs for each current attachment were byte-identical. The listed XLSX is **86,337 bytes**, SHA-256 `9716cf0571946f5e39d90b177c41e7919957eb88adb71cf22fd928b73c615a3f`; the applicant legacy Word document is **635,392 bytes**, SHA-256 `e1c93ece7e919e1b3f7c6cf2cd399e7585bcef5e7713876b0a9662de642b60f9`. The applicant file's HTTP Last-Modified predates the current landing update and is retained only as transport metadata, not as a substantive edition date. Publication remains fail-closed on the exact approved hashes.

## Reviewed parser boundary

The listed workbook has ten White List section sheets plus legend/empty support sheets and **246 company-section rows**. Rows are grouped only where source-visible company identity, legal/secondary offices, source identifier, raw/normalised dates and update/status evidence agree, yielding **142 observations: 105 listed and 37 renewal/update in progress**. Structured identifier coverage is **131/142**. Source listing-date tokens `07/07/206` and `06/07/206` are retained raw with normalised dates blank; no repair is inferred.

The applicant legacy Word table is parsed through `antiword` into one frozen seven-column table with **337 physical rows**: 68 repeated headers, 13 blank rows, 125 activity-continuation rows and **131 logical observations**. Status is assigned only from positive source evidence: **117 listed** where the source explicitly says `Iscritta ...`, **6 pending** from exact `In corso`, **5 cancellation-related** from explicit cancellation wording, and **3 other/unknown** where the outcome is blank or a bare unlabelled date. Structured identifier coverage is **126/131**. Two malformed application-date tokens (`25/0720522`, `10/1\0/2024`) remain raw and unnormalised. All 117 explicit subsequent-enrolment outcome dates remain source-derived and parseable.

The resulting Imperia candidate contains **273 observations** with **257 structured identifiers**. The two populations share one ordinary provincial register; they are separate source series, not separate legal registers.

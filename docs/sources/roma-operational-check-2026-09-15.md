# Roma White List operational source check — 2026-09-15

## Official publication surfaces

The Prefettura di Roma exposes the two required populations on separate official pages:

- listed companies: `https://prefettura.interno.gov.it/it/prefetture/roma/white-list-elenco-imprese-iscritte`
- applicant companies: `https://prefettura.interno.gov.it/it/prefetture/roma/white-list-elenco-imprese-richiedenti-iscrizione`

Each page exposed exactly one PDF attachment during the reviewed capture. No population or publication state is inferred from search failure.

## Byte-pinned capture

The reviewed listed attachment is:

`https://prefettura.interno.gov.it/sites/default/files/57/2026-09/elenco-imprese-iscritte-alla-white-list-aggiornato-alla-data-di-pubblicazione.pdf`

- SHA-256: `8a2bbdb210757a8e7bf1da74db4bd7440c4fc45b3198b09e225c0aee2e6ef4af`
- bytes: 498,221
- pages: 168
- PDF footer date: 14/09/2026
- PDF footer time observed in the reviewed layout: 16:28:58

The reviewed applicant attachment is:

`https://prefettura.interno.gov.it/sites/default/files/57/2026-09/elenco-imprese-richiedenti-iscrizione-alla-white-list-aggiornato-alla-data-di-pubblicazione.pdf`

- SHA-256: `9bf34641f92b7480492646f0ab442b47305438a06547e1739dafd324c2b1b32a`
- bytes: 405,505
- pages: 142
- PDF footer date: 14/09/2026
- PDF footer time observed in the reviewed layout: 16:29:37

Independent retrievals during this review produced the same byte hashes for both PDFs. The parser uses 2026-09-14 as the snapshot reference date because that date is printed internally on every reviewed PDF page. It is not treated as an inferred legal publication date for the web page.

## Parser family and record boundaries

The PDFs are positioned-text tables rather than reliably extractable PDF tables. `pdfplumber.extract_tables()` does not provide the source rows. The reviewed parser therefore belongs to the positioned-PDF family and locates record starts from the stable alignment between the company-name column and the source C.F./P.I. column. Row boundaries do not depend on Italian tax-identifier validity: the source contains positive identifiers of several lengths and foreign/custom identifiers, all of which remain verbatim in `identifier_field_raw`. Only identifiers already accepted by the repository-wide conservative identifier normaliser are exposed in the normalised identifier array.

The first page contains source legend/header rows that share the table geometry. They are excluded only through reviewed literal header/legend identifiers (`SEZIONE` and the two table-heading identifiers), not through fuzzy row dropping.

## Reviewed denominators and statuses

The reviewed listed PDF yields exactly **2,169 company observations**:

- 1,215 `listed`
- 954 `renewal_update_in_progress`

Update status is assigned only when the source note is one of the reviewed explicit update formulations. The source includes typography variants such as `AGGIONAMENTO IN CORSO`, `AGGIORNAMENTO IN CORO`, `AGIORNAMENTO IN CORSO`, `IMPRESA IN FASE DI AGGIORNAMENTO` and equivalent explicit variants; these are preserved verbatim in provenance. Administrative/liquidation/control notes remain listed observations and are not converted into a different legal status without source-positive support.

The reviewed applicant PDF yields exactly **2,259 company observations**:

- 2,256 `pending`, from positive membership in the official applicant series with no contrary source outcome
- 3 `renewal_update_in_progress`, each carrying the explicit source note `AGGIORNAMENTO IN CORSO`

Total candidate Roma public-source observations: **4,428**.

## Missing and malformed source dates

No dates are repaired by inference.

Listed series:

- 9 positive company rows have no listing date, protocol or expiry date in the reviewed source geometry; the observations are retained with those fields empty.
- two expiry strings are malformed in the source and remain unparsed: `28/01/205` and `27/07/202`.

Applicant series:

- 20 positive company rows have no application date in the reviewed source geometry; the observations are retained with the date empty.
- two application-date strings are malformed in the source and remain unparsed: `10/12/215` and `23/04/201`.

The semantic tests freeze the reviewed malformed-date sets and the identifiers of the positive rows with missing date fields, so a future unreviewed change fails closed.

## Integration boundary

This review validates official-source discovery, content-addressed capture, parser semantics and the candidate public-source observation layer only. It does **not** establish canonical hosted-database integration or independent durable-evidence storage; those remain separate governance gates and must not be promoted implicitly.

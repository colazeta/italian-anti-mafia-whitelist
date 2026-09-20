# Pordenone operational source check — 20 September 2026

## Current official surface

The current Pordenone Prefecture White List publication surface was verified on 20 September 2026 against the official `prefettura.interno.gov.it` host.

Primary publication page:

- https://prefettura.interno.gov.it/it/prefetture/pordenone/white-list-elenco-ditte-iscritte

The official page positively exposes eleven section attachments. Sections I–X are activity-sector lists of entered companies; Section XI is explicitly labelled `elenco imprese richiedenti`. This is positive evidence for both listed and applicant populations and does not rely on search absence or inferred publication status. The official page metadata observed during discovery reports an update on 1 September 2026.

A GitHub-hosted source probe fetched the publication page with HTTP 200, discovered exactly eleven official PDF attachments, then captured every attachment twice independently with cache bypass. Both captures of every resource were byte-identical. The landing response itself was 98,893 bytes with SHA-256 `e42ec34252960db9851b82aad1ef1544004620bf7d2d1e7c06ed6bfd4328801f`.

Failed future searches or fetches must not be interpreted as evidence that a population is absent, empty or unpublished.

## Verified current resources

All byte counts and SHA-256 values below are from two independent byte-identical captures on 20 September 2026.

### Listed — Section I

- label: `Sez. I - estrazione, fornitura e trasporto di terra e materiali inerti`
- URL: https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-i-estrazione-fornitura-etc_0.pdf
- bytes: `198,281`
- SHA-256: `f4e6374e5e03daa25daedd49ada730ae39c6b77437e763e3c0308aa0a0c627de`

### Listed — Section II

- label: `Sez. II - confezionamento, fornitura, etc.`
- URL: https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-ii-confezionamento-fornitura-etc_0.pdf
- bytes: `178,786`
- SHA-256: `62d63a080b3025e2ee2f37c3af1d486f12095be8f83e73cae611e2ca56bf84d5`

### Listed — Section III

- label: `Sez. III - noli a freddo di macchinari`
- URL: https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-iii-noli-a-freddo-di-macchinari.pdf
- bytes: `213,419`
- SHA-256: `2204fe651b733e32fe13f001c97fd2c6a93ccd9a846cc9f4ddd40d4f471e6ce9`

### Listed — Section IV

- label: `Sez. IV - fornitura di ferro lavorato`
- URL: https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-iv-fornitura-di-ferro-lavorato_0.pdf
- bytes: `123,264`
- SHA-256: `55a1edd7bcc52de101536c42091e14e040892cf1122462c36b37a861c48eeb62`

### Listed — Section V

- label: `Sez. V - noli a caldo`
- URL: https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-v-noli-a-caldo_0.pdf
- bytes: `215,658`
- SHA-256: `4fcd95954d20ba19ffcfb11e64a911a637056ba2fd794d47c5d3f19171f77803`

### Listed — Section VI

- label: `Sez. VI - autotrasporti per conto terzi`
- URL: https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-vi-autotrasporti-per-conto-terzi_1.pdf
- bytes: `190,667`
- SHA-256: `62c39abfc260ecacf59b0201867263499643fe5dc36c95500e380fa53deb87aa`

### Listed — Section VII

- label: `Sez. VII - guardiania dei cantieri`
- URL: https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-vii-guardiania-dei-cantieri.pdf
- bytes: `171,259`
- SHA-256: `35c5ef5ddb218e50d1f5a56007f2c1886ac73b6a91c5a13fb37e4b7f4952d2c8`

### Listed — Section VIII

- label: `Sez. VIII - servizi-funerari-e-cimiteriali`
- URL: https://prefettura.interno.gov.it/sites/default/files/74/2026-08/sez-viii-servizi-funerari-e-cimiteriali.pdf
- bytes: `116,387`
- SHA-256: `cac3354a388d87b3f7ee1fef965f7b9968d2fea4dfcbafa776fc175bee5d96b3`

### Listed — Section IX

- label: `Sez. IX ristorazione, mense e catering`
- URL: https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-ix-ristorazione-mense-e-catering.pdf
- bytes: `168,305`
- SHA-256: `a3b7c0b749be947692cb6ebb031e21e6c2e61913f34c1ad9f4741f3a7b9e96fa`

### Listed — Section X

- label: `Sez. X -servizi-ambientali-trasporto-rifiuti-etc.`
- URL: https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-x-servizi-ambientali-trasporto-rifiuti-etc_0.pdf
- bytes: `179,332`
- SHA-256: `af639b5c55ff31893bfd3906876e0c60e1e6614065efae1e5c7871ac62290c0f`

### Applicants — Section XI

- label: `Sez. XI - elenco imprese richiedenti`
- URL: https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-xi-elenco-imprese-richiedenti_edit_0.pdf
- bytes: `193,090`
- SHA-256: `b8875c9392f9c7273c3c773110d90141eada8aebaa538ae1e3115be27bfdaea1`

## Parser boundary to establish

The listed population is physically split across ten activity-sector PDFs. The same company may therefore recur across sections. Parser and integration work must preserve section membership as provenance and must not deduplicate merely on name or identifier. Any eventual grouping across sections requires compatible company identity, source status and date semantics; conflicting evidence must remain separate observations.

Section XI is positively identified by the authority as the applicant population. It must be ingested as applicant evidence rather than inferred from listed-series gaps.

No source-row, logical-observation, identifier-coverage or outcome denominator is approved by this source-surface check. Those values become authoritative only after a fail-closed structural audit and parser validation against these exact content-addressed resources.

## Evidence boundary

This check establishes the current official publication identities and immutable byte identities needed for parser work. It does not infer legal effect from dates, disappearance from a later edition, missing rows, future source drift or failed retrieval. Any source drift must fail closed and be reviewed rather than absorbed automatically.

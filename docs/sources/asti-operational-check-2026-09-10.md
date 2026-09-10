# Asti White List operational check — 10 September 2026

## Official current surface

The official Prefettura di Asti White List page was verified on 10 September 2026: https://prefettura.interno.gov.it/it/prefetture/asti/white-list-provinciali. It explicitly labels both `Elenco imprese iscritte` and `Elenco imprese richiedenti l'iscrizione` as `Aggiornato al 03/08/2026`; the page itself reports its latest update as 3 August 2026. This is positive current-edition evidence for both ordinary White List populations. The September directory component in the attachment URLs is not treated as publication-date evidence.

## Byte-pinned resources

Registered-company resource: `https://prefettura.interno.gov.it/sites/default/files/26/2026-09/ditte-iscritte.pdf`, SHA-256 `8c26313c57588745e92600961e7071d4ff2246ab86555e39500f17f59c41c128`, 39 pages.

Applicant resource: `https://prefettura.interno.gov.it/sites/default/files/26/2026-09/ditte_in_istruttoria.pdf`, SHA-256 `ae5d69a85541dae61ffd67f4983a78831f2a97d096bd752aeb8b93c9a88943a5`, 6 pages.

## Parser boundary and validated output

The registered-company PDF is organised by Sections I-X. `asti_listed` uses ruled-table geometry and the position of the primary registration/renewal date. The audited edition contains 521 sector observations, conservatively grouped into 284 public source observations. One CEIT SRL row has no listing date and explicitly reports `In istruttoria`; it remains pending. Seven malformed expiry values remain raw and are not reconstructed.

The applicant PDF yields 17 source observations. Two application dates are blank and remain blank. The ten-digit JOKKO identifier `0141215742` remains raw and is not padded. Source-explicit outcomes map conservatively: four `Iscritta` observations to listed, twelve `In istruttoria` observations to pending, and one `Non iscritta` observation to `other_or_unknown`.

The combined Asti public contribution is 301 observations: 287 listed, 13 pending and 1 other/unknown.

## Publication gate

Publication pins the exact two resource SHA-256 values and the 521/284/17 denominators. Byte drift, page/layout drift, changed denominators, loss of the explicit pending exception or new invalid non-blank applicant dates fail closed. Canonical hosted-database integration and independent durable-evidence verification remain separate under issue #16 and are not claimed complete here.

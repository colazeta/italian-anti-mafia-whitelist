# Genova White List operational check — 2026-09-12

## Current official publication

The current official Prefettura di Genova White List page was directly resolved at:

- https://prefettura.interno.gov.it/it/prefetture/genova/elenco-imprese-iscritte-white-list

The page positively exposes two distinct current populations, both referenced to 10 September 2026:

- registered / renewal population: `wl-10-09-26.pdf`;
- applicant population: `sez-richiedenti-10-09-26.pdf`.

No population or publication state is inferred from search failure. Both resources were independently downloaded twice during the expansion work and the repeated bytes matched.

## Content identity and parser boundary

| Population | Pages | SHA-256 | Public observations |
| --- | ---: | --- | ---: |
| listed / renewal | 114 | `baf72de8d1f28943a8e9ec2bdd6e95213eacd0058cd6799a04e233c06d9e5403` | 652 |
| applicant | 20 | `13ecfd8bea8616deea76349cd7592fd046d09f45e2b522c11dda1f084a4420a7` | 110 |

The byte-pinned parser validation yields 762 observations in total: 528 `listed`, 124 `renewal_update_in_progress`, and 110 applicant `pending`.

## Reviewed source-layout exceptions

The parser remains fail-closed. It accepts ordinary Roman-numeral `Sez.` section tokens and only a finite set of source-layout exceptions verified against the pinned PDFs. These include the listed page-47 FISIA ITALIMPIANTI extraction, blank or mistyped section cells whose section membership remains visible in the same official page text, the six applicant identities split across the two page-7 extraction tables, and the incomplete first applicant row on page 9 for EDILQUADRIFOGLIO SRL.

The page-7 identifiers are frozen from the official page text: CRESTA & DELFINO SRL `01345600991`; CUNEO LUIGI `01067080992`; CURZI LUIGI - AUTOTRASPORTI C/TERZI `03185270109`; DAMA SRL `02830520991`; DASSORI SRL `02665830994`; DE BREEZE SRL `03047520998`.

Malformed official identifiers are retained raw and are not repaired. In particular PARODI PAOLO, PIROMALLI ANTONINO srl, ROSSI ROBERTO and TRAVERSO SERGIO do not receive inferred canonical identifiers. Likewise the official date strings `26//09/2023` for GENOVARENT SRL and `16/072026` for LO SCACCIA PENSIERI SRL are retained in raw source fields while the corresponding canonical date is left blank.

## Validation state

The current parser was revalidated on 12 September 2026 against both exact official resources. The gate freezes the two hashes, page counts, 652/110 denominators, 528/124/110 status distribution, all six page-7 identities and dates/sections, the EDILQUADRIFOGLIO reconstruction, the FISIA row, malformed-identifier non-repair and invalid-date non-repair.

Canonical hosted-database integration and independent durable-evidence verification remain separate infrastructure work governed by the repository evidence-storage workstream; they are not treated as prerequisites for source-backed public observations.

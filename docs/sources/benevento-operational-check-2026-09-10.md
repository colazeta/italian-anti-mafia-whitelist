# Benevento — operational source check — 10 September 2026

## Current official populations

The Prefettura di Benevento publishes two explicit current White List populations. The listed-company page links **Elenco delle imprese iscritte al giorno 31 agosto 2026**; the applicant page links **Elenco imprese richiedenti iscrizione al giorno 31 agosto 2026**. Both landing pages were checked on 10 September 2026 and were updated by the Prefecture on 1 September 2026.

Approved byte identities are `a0e260f748d3447cf17378e15e3466ec93ca72b7da1f6a7b1e1144c11ba28c01` for the 64-page listed PDF and `7e7333af70cef53e10e8c9d269cb6d5a70a88f33871630606b6cd06b1c2f5cac` for the 16-page applicant PDF. Official URLs are pinned in `data/publication/multi_prefecture_pilot.json`.

## Parser boundary

Generic PDF table extraction is not a safe row boundary for these editions: the applicant PDF contains visually distinct observations that are collapsed into single extracted rows. The approved parser uses ruled-table geometry and the source primary-date column as row anchors, then reads fields only inside their fixed source column bands. Date-like metadata outside the table cannot establish a company observation. It fails closed on an unexpected page count, ambiguous row anchors, missing name/office, invalid primary dates or an unexpected final observation count.

Validation of the byte-pinned editions yields **734 listed observations** and **204 applicant observations**. All 938 have non-empty source names, registered offices and activity cells. The listed source has 732 non-empty raw identifier cells and 718 conservatively normalised identifiers; the applicant source has 203 and 194 respectively. Empty or non-canonical identifiers are not reconstructed. One listed expiry value is malformed in the source representation; normalised expiry remains blank and the raw variant is retained.

## Status semantics

Population membership is positive source evidence. Listed-source rows are `listed`; applicant-source rows are `pending`. Free text is not used to invent a legal outcome. The listed source's explicit update column is retained as source text and is kept distinct from the activity/section column.

## Remaining infrastructure boundary

This expansion validates public source observations and public export only. Hosted canonical-database integration and independent durable-evidence recovery remain governed under issue #16.

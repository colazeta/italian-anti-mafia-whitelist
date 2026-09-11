# Bergamo operational source check — 11 September 2026

## Current official publication

The current official Prefettura di Bergamo White List page was re-resolved on 11 September 2026. It exposes two separate current populations labelled **ELENCO RICHIEDENTI ISCRIZIONE** and **ELENCO ISCRITTE**. The official page reports **Ultimo aggiornamento: 27 August 2026**.

- Official page: `https://prefettura.interno.gov.it/it/prefetture/bergamo/evidenza/white-list`.
- Applicant resource: `https://prefettura.interno.gov.it/sites/default/files/20/2026-08/elenco-richiedenti-iscrizione.pdf` — SHA-256 `65f3db950b3c75f073edc2eaba47cebee9771b706b6c6dcbae21ef881a523ce6`.
- Listed resource: `https://prefettura.interno.gov.it/sites/default/files/20/2026-08/elenco-iscritte.pdf` — SHA-256 `b5f6229d4aac3674bcaf68895f93f5f5c60848a1bb6ab78b2e3d98a6c89ecaef`.

The two PDF identities have been independently re-fetched from GitHub-hosted runners and are treated as byte-pinned current editions. A failed fetch from a different execution environment is not evidence of non-publication or incompleteness.

## Reviewed population boundaries

Both publications are borderless PDF tables with a stable 42.5-point logical row lattice. Independent geometry, column-band and value audits freeze the following source denominators:

- **1,434 listed-population observations** across 131 pages: page 1 contains 9 logical rows, pages 2–130 contain 11 each, and page 131 contains 6;
- **612 applicant observations** across 56 pages: page 1 contains 10 logical rows, pages 2–55 contain 11 each, and page 56 contains 8.

The applicant publication positively identifies the population as companies requesting registration, so all 612 observations map to `pending` without inferring an outcome from missing row-level text.

The listed publication contains `Data Iscr.`, `Scad.` and `Data Aggiornamento in corso` columns. The Prefettura's official explanatory text states that companies whose renewal checks continue beyond the previous annual validity are shown in the list as “in aggiornamento”. On the byte-pinned edition, **808** rows contain a source date in the `Data Aggiornamento in corso` column and map to `renewal_update_in_progress`; the remaining **626** rows map to `listed`.

## Conservative extraction and provenance

The parser derives values only from the reviewed source column bands. It does not use fuzzy legal-entity matching or reconstruct malformed identifiers. Strict identifier normalisation accepts only already-complete 11-digit numeric or 16-character alphanumeric tokens found inside the raw identifier field; the complete raw field remains preserved.

The audits identify **555/612 applicant observations** and **1,425/1,434 listed observations** with at least one strict identifier token. Twenty-two listed observations contain more than one complete strict token and retain all such tokens. Source formatting such as split 16-character tax codes, descriptive text inside the identifier band, short numeric values, dates appearing in the identifier band, and other noncanonical raw strings is not repaired.

All listed registration and expiry dates are valid `DD/MM/YYYY` source dates. The listed `Data Aggiornamento in corso` field contains 808 valid dates and 626 blanks. The applicant application-date field contains 600 valid dates and 12 reviewed blanks, at exact frozen coordinates. No malformed or calendar-invalid date is repaired or silently discarded.

One applicant row (`COBO S.R.L.`, page 11 row 9) and one listed row (`ZANETTI ARTURO & C. S.R.L.`, page 130 row 9) have no recoverable activity value in the reviewed source band. Their activity remains blank rather than inferred. Any additional blank activity, unexpected blank mandatory date, changed row denominator, changed page geometry, unreviewed activity prefix, or new date typography fails closed.

## Publication boundary

The public archive publishes these source-backed observations without asserting national legal-entity deduplication. Canonical hosted-database integration and independent durable-evidence verification remain separately governed under issue #16 and are not implied by this public-source validation.

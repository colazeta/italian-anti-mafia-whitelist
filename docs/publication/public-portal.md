> Public-language revision: see [the before/after audit](public-language-audit.md).
> The registry contract and approved company attributes below are preserved.
> Navigation now uses Registro / Prefetture / Storico / Aggiornamenti / Metodo e fonti,
> with Qualità dei dati secondary. Page-update dates are distinct from edition dates;
> source-discovery history does not assert permanent archival custody.

# Public retro portal

## Purpose

The public portal is the primary public-interest interface for the White List archive. It reuses the restrained late-1990s/early-2000s management-system visual language of the Dataset Explorer, but its main purpose is practical consultation: users should be able to search the published White List population and inspect the attributes and provenance behind each source observation.

The publication principle is **public-first, audit-transparent**. The register is the main interface; methodology, validation, source provenance and implementation audit remain accessible as a second level of depth.

## Public contract v3

The register is now multi-Prefecture. The first pilot covers:

- Cosenza — ordinary White List;
- Parma — ordinary operational White List table;
- Pistoia — ordinary White List, listed and applicant populations;
- Bologna — ordinary provincial White List and distinct post-earthquake White List, each with listed and applicant populations.

The public record contract exposes, when present in the source:

- operator / legal name;
- publishing Prefecture / authority;
- register identity;
- source population scope;
- edition/reference date;
- registered office;
- secondary office;
- CF / VAT / other identifier field as published and parsed;
- requested White List activities / sectors;
- source status;
- source-specific procedural or listing dates;
- observed nominal expiry date;
- raw source outcome/annotation;
- deterministic public record locator;
- official source page and resource URL;
- exact capture SHA-256 and parser identity.

The default register view is `listed`. Other procedural states remain available through filters because they are part of the official publications and are useful for understanding the register lifecycle.

## Source-specific adaptation, common public contract

The Prefectures do not publish a common physical schema. The public builder therefore uses source-specific adapters while preserving a stable public contract.

Examples from the first pilot:

- Cosenza publishes a combined listed/applicant PDF and a long dated snapshot history;
- Parma's current official listed/applicant resources expose effectively the same operational table, so the pilot ingests it once and derives source status from the outcome rather than duplicating the population;
- Pistoia publishes separate sector-organised listed and applicant PDFs;
- Bologna exposes more than one register under the same Prefecture and changes table shape between pages, so the parser locates date-bearing columns semantically rather than depending on one fixed physical column index.

Parser diagnostics are part of the deploy gate. A source is not published if its approved SHA changes unexpectedly, a known source-row invariant fails, or a parser drops a date-bearing row.

## Source observation vs canonical legal entity

The current national pilot is source-backed. Its unit is a public observation from an approved current source edition, grouped only where a source repeats the same observation solely because of sector organisation.

The public export does **not** assert that all rows across Prefectures are already a nationally deduplicated `LegalEntity`. The conceptual model remains:

```text
LegalEntity
    ↕
WhiteListRelationship
    ↕
WhiteListRegister
    ↕
PublicAuthority
```

The entity-centric layer can be added when resolution evidence supports it, without losing the source-observation trail.

## Prefecture directory

The public site includes a dedicated `Prefetture` view generated from the Ministry of the Interior national White List index.

For every authority/jurisdiction it shows:

- mapping status;
- whether the project has already mapped a primary source;
- number and model of source series when available;
- public registers already exposed by this project;
- **last project check** — when the project verified/mapped the source;
- **last source update** — the update/reference date explicitly supported by the official source when recorded;
- official source link.

The statuses are deliberately distinct:

- `Dati pubblicati` — current source-backed records are already in the public register;
- `Fonte mappata` — the primary publication route has been independently mapped, but row-level data are not yet in the public register;
- `Da mappare` — the authority is present in the national index but does not yet have an independently mapped primary source in the project.

Source/canonical key aliases are versioned explicitly. For example, the Ministry national-index URL uses `bolzano`, while the project canonical authority key is `bolzano-bozen`; the crosswalk preserves both identities without falsely showing the source as unmapped.

## Reproducible public build

The register and Prefecture directory are not transcribed by hand.

At deploy time `.github/workflows/public-pages.yml`:

1. reads the versioned approved-source configuration;
2. downloads each official source resource;
3. verifies every SHA-256 before parsing;
4. runs the source-specific versioned adapters;
5. validates source-specific invariants and zero dropped date-bearing rows;
6. builds the unified `registry.json` / `registry.csv`;
7. refreshes the full Prefecture directory from the Ministry national index and joins it to the project mapping inventory through explicit aliases;
8. builds `prefectures.json` / `prefectures.csv`;
9. validates the public artifact and only then deploys GitHub Pages.

A silent upstream replacement therefore fails closed instead of silently exposing unreviewed bytes.

## Geography is non-blocking

Geographic normalisation remains in the project because it can support territorial filtering, maps and research use cases, but it is **not a publication prerequisite**.

The production relationship is:

```text
DOWNLOAD → PARSE → CORE → PUBLICATION
                  ↘
                   GEO ENRICHMENT (optional, incremental)
```

The official source address remains the primary public field. Any derived municipality, street, coordinate or ANNCSU/geocoder result must remain separately labelled with its provenance and precision. New or changed core records can be published before geographic enrichment finishes or even when no enrichment is available.

## Audit transparency

The public interface provides links to:

- repository and Git history;
- parser code;
- architecture documentation;
- validation and gold-standard documentation;
- technical Explorer sources;
- issue tracker;
- source-page/resource URLs and exact capture SHA-256 values.

Internal database UUIDs and curation-only fields are not necessary in the ordinary public register, but the architecture, validation process, source-specific decisions and QA are public.

## Interpretation safeguards

- Source-backed observations are not silently presented as nationally deduplicated companies.
- Official source status is preserved rather than reinterpreted as a new legal decision by this project.
- Sector-only repetition may be grouped for readability only when the grouping contract is explicit.
- `not_found` affects optional address-linkage coverage/yield and is not a returned false match.
- Reviewed Cosenza geographic precision estimates are local benchmark evidence, not national performance claims.
- Candidate geography is never represented as accepted geography.
- Official Prefecture publications control for administrative/legal effects.

## Hosting and updates

The site is static and deployed with GitHub Pages. Source-specific watchers can later promote a newly detected edition into the approved-source configuration after capture/parser checks. Existing historical editions remain immutable and are never overwritten.

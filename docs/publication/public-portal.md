# Public retro portal

## Purpose

The public portal is the primary public-interest interface for the White List archive. It reuses the restrained late-1990s/early-2000s management-system visual language of the Dataset Explorer, but its main purpose is practical consultation: users should be able to search the published White List population and inspect the attributes and provenance behind each source observation.

The publication principle is **public-first, audit-transparent**. The register is the main interface; methodology, validation, source provenance and implementation audit remain accessible as a second level of depth.

## Public contract v2

The public register now exposes source-backed attributes from the latest approved Cosenza edition:

- operator / legal name as published;
- publishing Prefecture;
- edition reference date;
- registered office;
- secondary office when published;
- CF / VAT / other identifier field as published and parsed;
- requested White List activities;
- application date field and parsed dates;
- source status (`listed`, `pending`, renewal/update classes, etc.);
- raw source outcome text;
- observed listing date when parseable from the source wording;
- observed nominal expiry date when parseable;
- deterministic public source-row locator;
- official source page and official resource URL.

The default register view is `listed`, so ordinary visitors first see the observations the source represents as actually listed. Other procedural states remain available through filters because they are also part of the official publication.

## Source observation vs canonical legal entity

The current Cosenza register is source-backed. Its unit is the row/observation in the latest approved source edition, not an asserted nationally deduplicated `LegalEntity` object.

This distinction is intentionally visible. The public register must not silently convert source rows into canonical legal identities before the entity-resolution layer supports that assertion. When the canonical layer is mature, the public UI can add an entity-centric view while retaining the underlying source-observation trail.

## Reproducible public build

The entity register is not transcribed by hand.

At deploy time `.github/workflows/public-pages.yml`:

1. reads the approved source URL and expected capture SHA-256 from `public-site/data/site.json`;
2. downloads the official PDF;
3. verifies its SHA-256 before parsing;
4. runs the versioned Cosenza v2 parser;
5. requires the parsed row count and status distribution to reconcile with the frozen approved baseline;
6. generates `public-site/data/registry.json` and `registry.csv`;
7. runs public-contract and artifact checks;
8. deploys only after all gates pass.

If the Prefecture silently replaces the bytes at the same URL, publication fails rather than silently exposing unreviewed content.

## Audit transparency

The public interface provides links to:

- the repository and Git history;
- parser code;
- architecture documentation;
- validation and gold-standard documentation;
- technical Explorer sources;
- the issue tracker;
- source-page/resource URLs and the exact capture SHA-256 used for the current register.

Internal database UUIDs and curation-only fields are not needed for ordinary register use and are not copied into the public entity export, but the technical architecture and validation process themselves are public.

## Interpretation safeguards

- Source-row counts are labelled as observations/rows, not unique-company counts.
- Official source status is preserved rather than reinterpreted as a new legal decision by this project.
- `not_found` affects address-linkage coverage/yield and is not presented as a returned false match.
- Reviewed Cosenza address precision estimates are explicitly local evidence, not national performance claims.
- Candidate geography is never represented as accepted geography.
- The portal clearly states that official Prefecture publications control for administrative/legal effects.

## Hosting and future updates

The site is static and deployed with GitHub Pages. The planned weekly Cosenza watcher will eventually update the approved source identity only when a new edition is detected, captured, parsed and accepted into the archive. Existing historical editions remain immutable and are never overwritten.

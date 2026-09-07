# Public retro portal

## Purpose

The public portal is a deliberately bounded publication product for the White List archive. It reuses the restrained late-1990s/early-2000s management-system visual language of the private Dataset Explorer while exposing only fields intentionally included in a public export contract.

The public site is **not** a sanitized dump of the private Explorer and must never become one.

## Publication boundary

The deploy workflow uploads only `public-site/`.

Nothing outside that directory is part of the Pages artifact. In particular, the public site must not ingest or copy by default:

- private table bundles;
- curation/reviewer decisions;
- internal source-evidence join files;
- database audit catalogs;
- raw internal identifiers or UUIDs;
- private Dataset Explorer artifacts.

New fields become public only by an explicit change to the public data contract, code review and passing tests.

## Public contract v1

The first release exposes:

- project/publication status;
- national source-discovery coverage aggregates;
- Cosenza latest-edition source-row counts;
- Cosenza historical-edition links;
- capture identity/provenance for the latest frozen Cosenza edition;
- reviewed address-normalisation quality aggregates;
- methodology and source links.

It does **not** yet expose company-level records.

## Interpretation safeguards

- Source-row counts are labelled as observations/rows, not unique-company counts.
- `not_found` affects coverage/yield and is not presented as a returned false match.
- Reviewed Cosenza precision estimates are explicitly local evidence, not national performance claims.
- Candidate geography is never represented as accepted geography.
- The portal clearly states that it is independent and that official sources control for administrative/legal effects.

## Hosting

The site is static and deployed with GitHub Pages through `.github/workflows/public-pages.yml`.

Deployment grants only `contents: read`, `pages: write`, and `id-token: write`. The workflow validates the public artifact boundary before upload.

GitHub Pages must be configured with **Settings → Pages → Build and deployment → Source: GitHub Actions** for the repository before the first deployment can succeed.

## Future integration

The intended next step is to generate `public-site/data/site.json` from a deterministic publication builder rather than maintain it by hand. That builder should consume only explicit allow-listed, source-backed inputs and should run after successful ingest/validation. A weekly Cosenza watcher can then update the public portal only when a new historical edition is accepted into the archive.

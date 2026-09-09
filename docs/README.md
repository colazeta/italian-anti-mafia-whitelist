# Documentation index

This directory is the documentation entry point for the Open Italian Anti-Mafia White List Archive.

## Start here

| Need | Read |
|---|---|
| Understand the project in five minutes | [`../README.md`](../README.md) |
| Find the data that currently exist | [`data-access.md`](data-access.md) and [`../data/catalog.csv`](../data/catalog.csv) |
| Review the current Dataset Explorer checkpoint | [`product/data-explorer-checkpoint.md`](product/data-explorer-checkpoint.md) |
| Understand geography enrichment and the mandatory listed/applicant completeness rule | [`architecture/geography-and-population-coverage.md`](architecture/geography-and-population-coverage.md) |
| Understand original PDF retention and independent parser verification | [`architecture/source-evidence-archive.md`](architecture/source-evidence-archive.md) |
| Understand the independent evidence backup/restore gate | [`architecture/evidence-recovery.md`](architecture/evidence-recovery.md) |
| Understand what GitHub Actions may publish in this public repository | [`architecture/actions-artifact-boundary.md`](architecture/actions-artifact-boundary.md) |
| Regenerate a full source-backed address-review bundle without publishing it through Actions | [`validation/internal-review-handoff.md`](validation/internal-review-handoff.md) |
| Understand parser families and the automatic semantic/canonical pipeline | [`architecture/parser-families-and-semantic-pipeline.md`](architecture/parser-families-and-semantic-pipeline.md) |
| See the current source → semantic → canonical ERD | [`architecture/erd-v0.3-dev.md`](architecture/erd-v0.3-dev.md) |
| Understand the current Cosenza parser and its v1→v2 QA correction | [`architecture/cosenza-parser-v2.md`](architecture/cosenza-parser-v2.md) |
| Understand project rules and what belongs where | [`project-rules.md`](project-rules.md) |
| Understand the frozen/audited baseline ERD | [`architecture/erd-v0.2.md`](architecture/erd-v0.2.md) |
| Understand row-level source-observation persistence | [`architecture/parsed-record-persistence-0.1.1-dev.md`](architecture/parsed-record-persistence-0.1.1-dev.md) |
| Understand canonical fields | [`data-dictionary/canonical-fields.md`](data-dictionary/canonical-fields.md) |
| Understand source discovery and Prefecture heterogeneity | [`sources/`](sources/) |
| Check frozen releases and release notes | [`releases/`](releases/) |
| Contribute a change | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |

## Documentation structure

- `architecture/` — durable design decisions, ERDs, temporal/provenance models, geography, source-population completeness, original-source evidence storage and recovery, Actions/publication boundaries, parser-family routing, semantic projection, parser QA and architecture audits.
- `data-dictionary/` — canonical concepts, fields, controlled vocabularies and mapping semantics.
- `product/` — user-facing checkpoint/browser behaviour and product-level semantic guardrails.
- `sources/` — source-discovery methodology, source-specific research and parser/capture notes.
- `validation/` — review protocols, gold-standard interpretation and trusted regeneration/handoff procedures for internal evidence bundles.
- `releases/` — frozen release notes. Development-state notes must not be presented as released schema versions.
- `data-access.md` — the authoritative human-readable answer to “what data exist and where can I see them?”.
- `project-rules.md` — repository organisation, modelling invariants and change-control rules.

## Documentation maintenance rule

Documentation is part of the implementation contract. A change that alters a data layer, schema meaning, geography enrichment, source-population coverage, source-evidence storage, parser-family binding, record contract, semantic projector, persisted artifact, workflow publication surface, public interface or release state must update the corresponding documentation in the same pull request. The CI governance tests check that required entry-point documents exist, persistent CSV/JSON artifacts under `data/` are represented in the data catalog, and current Actions upload surfaces remain within the reviewed public-artifact allow-list.

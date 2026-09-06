# Documentation index

This directory is the documentation entry point for the Open Italian Anti-Mafia White List Archive.

## Start here

| Need | Read |
|---|---|
| Understand the project in five minutes | [`../README.md`](../README.md) |
| Find the data that currently exist | [`data-access.md`](data-access.md) and [`../data/catalog.csv`](../data/catalog.csv) |
| Review the current Data Explorer checkpoint | [`product/data-explorer-checkpoint.md`](product/data-explorer-checkpoint.md) |
| Understand the current Cosenza parser and its v1→v2 QA correction | [`architecture/cosenza-parser-v2.md`](architecture/cosenza-parser-v2.md) |
| Understand project rules and what belongs where | [`project-rules.md`](project-rules.md) |
| Understand the database and entity model | [`architecture/`](architecture/) |
| Understand row-level source-observation persistence | [`architecture/parsed-record-persistence-0.1.1-dev.md`](architecture/parsed-record-persistence-0.1.1-dev.md) |
| Understand canonical fields | [`data-dictionary/canonical-fields.md`](data-dictionary/canonical-fields.md) |
| Understand source discovery and Prefecture heterogeneity | [`sources/`](sources/) |
| Check frozen releases and release notes | [`releases/`](releases/) |
| Contribute a change | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |

## Documentation structure

- `architecture/` — durable design decisions, ERDs, temporal/provenance models, parser QA and architecture audits.
- `data-dictionary/` — canonical concepts, fields, controlled vocabularies and mapping semantics.
- `product/` — user-facing checkpoint/browser behaviour and product-level semantic guardrails.
- `sources/` — source-discovery methodology, source-specific research and parser/capture notes.
- `releases/` — frozen release notes. Development-state notes must not be presented as released schema versions.
- `data-access.md` — the authoritative human-readable answer to “what data exist and where can I see them?”.
- `project-rules.md` — repository organisation, modelling invariants and change-control rules.

## Documentation maintenance rule

Documentation is part of the implementation contract. A change that alters a data layer, schema meaning, persisted artifact, public interface or release state must update the corresponding documentation in the same pull request. The CI governance test checks that required entry-point documents exist and that persistent CSV/JSON artifacts under `data/` are represented in the data catalog.

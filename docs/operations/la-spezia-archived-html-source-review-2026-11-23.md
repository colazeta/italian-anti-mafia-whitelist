# La Spezia — archived official HTML population pair: bounded source QA

**Review status, 23 November 2026:** source-only preflight verified in protected production on run #45158419353, job #137637297895. The subsequent table-level audit extension awaits its own protected production receipt. **Not** an approved SourceEdition, public dataset, parser contract, population-complete release or privacy decision.

The [national robot cycle #45080425727](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/45080425727) archived two separate official HTML publications:

| Population | Source page | SHA-256 original | Archived bytes | Status |
| --- | --- | --- | ---: | --- |
| listed | [Prefettura della Spezia — ditte iscritte](https://prefettura.interno.gov.it/it/prefetture/spezia/elenco-ditte-iscritte-alla-white-list) | `4b668d585797c537c1d4f7dc27e7f8733dbe568914668829d88f5ad09e02f7c9` | 147,017 | acquired HTML, not approved |
| applicant | [Prefettura della Spezia — richiedenti](https://prefettura.interno.gov.it/it/prefetture/spezia/elenco-ditte-hanno-richiesto-iscrizione-alla-white-list) | `50cc45c03517013084d626a1415ca5bd003579c1594ebc65273cad37cb690f8d` | 83,851 | acquired HTML, not approved |

The publication pages contain sector-grouped tables (listed) and a requested-activity/administrative-outcome table (applicants). **Sector repetitions must not be deduplicated as though they were duplicate source observations**, and a source `Esito` must not be interpreted automatically as a canonical legal-effect event. The publicly displayed page-update time is not, without review, an edition-effective date or proof of byte identity at that time.

## Bounded implementation

`la_spezia_archive_preflight.py` runs **only in the existing protected four-shard transformer**, on shard 0. It reads the two exact R2 SHA-addressed response bodies and independently recomputes full SHA-256 and byte length. Standard-library HTML parsing then provides **aggregate-only** counts for physical tables, rows, row widths, structural header cues and sector-heading hints. The table-level extension reports ordinal-only profiles of each table: its row count, header-shaped rows, `th`-tag rows, row widths and field-label cues. Aggregate sums are verified against the page-wide profile; unbalanced, excessive or nested tables fail closed. This isolates the listed source's 11th table without silently assigning it to a population or sector. Raw HTML, row values, identifiers, addresses, physical row locators and private paths do not appear in output. Oversized, nested or structurally incomplete tables are explicit review failures.

All outcomes leave `source_edition_approved=false`, `official_edition_date_approved=false`, `privacy_approved=false`, `public_release_eligible=false`, `postgresql_writes=0`, `public_promotions=0`. The entire source pair is required for positive integrity results. Test fixtures cover malformed markup, exact byte mismatches, data redaction, repeated run determinism and protected workflow wiring.

## Gates remaining for inclusion

1. **Completed for initial aggregate probe:** protected readback verified both SHA-pinned originals: listed 11 tables/347 physical rows/10 header-shaped rows/337 non-header nonempty rows; applicants 1 table/22 rows/1 header-shaped row/21 non-header nonempty rows. **Next:** examine the table-level receipt for the exact 11th listed table, without inferring which rows are legal entities.
2. Independently reconcile every sector table, header and logical continuation against the archived original. Establish safe identifiers, date fields, requested activities, statuses and blank/ambiguous cells; count source observations by population and sector separately from legal entities.
3. Authenticate any official edition date using explicit source evidence, not page footer, robot timestamp or URL slug. Review data minimisation, sole traders, publication licensing and other privacy considerations.
4. Only after parser version, record contract, source binding and full digests are approved should the existing `expansion_authorities` intent and guarded candidate-release handoff be used. Keep every previously selected authority and all five published asset bytes unchanged outside scope. Only the existing Public retro portal may deploy and verify five live assets.

**Parallel delta lane:** the selected national `public-data-44159882124-1` remains the most recently attested approved release. The newer Catania and Trento source pairs need their own independent documentary QA. This source-only change creates neither a new selected authority nor a fresher publication.

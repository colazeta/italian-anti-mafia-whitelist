# National White List source registry v0.1

Date: 2026-09-06

## Purpose

The source registry is the discovery layer for the national White List archive. Its objective is not merely to enumerate Prefectures, but to identify every distinct public source series through which White List information is published and to record how those series evolve over time.

## Coverage universe

The current territorial baseline contains 106 authority/jurisdiction entries:

- 103 ordinary Prefetture – Uffici Territoriali del Governo;
- the Commissariato del Governo per la Provincia di Bolzano;
- the Commissariato del Governo per la Provincia di Trento;
- the special Valle d'Aosta arrangement.

This is an authority-coverage universe, not a claim that there are exactly 106 source series. An authority may publish several independent White List series.

## Official discovery source

The Ministry of the Interior publishes a national White List index with a row for each territorial jurisdiction and a `Visualizza` link to the corresponding local resource. The project uses that index as a discovery and change-detection source.

The index itself is **not** treated as the authoritative observation of a company's White List status. The evidence chain must continue to the territorial page, document, table or application actually publishing the company record.

## Registry layers

### Authority layer

`territorial_authorities.csv` defines stable project identifiers and territorial/office classification. No unverified local URLs are guessed at this layer.

### Verified landing-page layer

`verified_primary_pages.csv` contains only local White List landing pages whose destination has been independently verified. The first research tranche contains 24 verified pages.

### Publication-profile layer

`pilot_source_profiles.csv` contains ten deliberately heterogeneous sources selected to expose the main structural divergence patterns before national parsing is implemented.

The pilot currently includes at least the following publication models:

- HTML tables with separate listed/applicant populations;
- periodic PDF lists;
- dated snapshot pages with sector-specific attachments;
- rich HTML tables containing procedural annotations;
- landing pages linking to separate list resources;
- a custom White List web application;
- the special Valle d'Aosta publication model.

## Initial empirical findings

The pilot confirms that divergence occurs at more than the field-label level. Territorial publications differ in:

1. **population model** — listed companies, applicants, or combined lists;
2. **sector representation** — section headings, section columns, multiple codes in one value, or sector-specific files;
3. **publication medium** — HTML, PDF, DOCX, spreadsheet-like exports, custom applications;
4. **temporal publication model** — overwritten current list versus retained dated snapshots;
5. **procedure representation** — dedicated status fields, outcome fields, free-text annotations, or list-level context;
6. **document decomposition** — one comprehensive list versus many sector/population files.

This validates the existing database separation between `SourceSeries`, `SourceEdition`, `SourceResource`, `SourceCapture`, `SourceSchemaVersion` and canonical White List facts.

## National-index discovery tool

The module `white_list_archive.acquisition.national_index` parses the Ministry national index and emits:

- jurisdiction name;
- published title;
- resolved destination URL;
- index page from which the destination was observed.

The parser deliberately reads the actual hyperlink behind `Visualizza`; it does not construct a local URL from the jurisdiction name.

## Next registry iteration

The next pass should:

1. resolve and verify the primary landing page for every territorial authority;
2. enumerate all source series exposed from each landing page;
3. classify each series by population and sector scope;
4. record publication formats and whether editions are retained historically;
5. identify the first and latest publicly recoverable edition;
6. fingerprint each distinct source schema;
7. identify historical-site predecessors and archived source resources;
8. only then begin parser implementation by source-schema family.

## Quality rule

A missing direct URL means **not yet resolved**, not “no White List source”. Likewise, absence of a historical snapshot means **not yet found**, not proof that no historical publication existed.

# Cosenza combined-list parser v2

## Why v2 exists

The first curator Data Explorer checkpoint showed that parser v1 was too poor to serve as a national parser-quality baseline. V1 was useful for proving the end-to-end source/capture/ParseRun architecture, but it structured only business name and one 11-digit identifier and treated identifier syntax as part of row detection.

A direct audit against the frozen official PDFs identified two classes of row-detection error in **both** validated snapshots:

- three real rows were missed because their source identifier did not match the expected 11-digit numeric pattern: `GENISE FORTUNATO`, `NICASTRO GIUSEPPE`, `ANDREOLI ELIO`;
- one continuation/alias line, `ABBREVIATAMENTE SMIC S.R.L.`, was incorrectly emitted as an autonomous row because it contained another 11-digit identifier.

The net v1 undercount was therefore two rows per snapshot. V1 remains immutable provenance; it is not rewritten or deleted.

## Corrected counts

| Edition | v1 | v2 | Net correction |
|---|---:|---:|---:|
| 2026-06-28 | 1,325 | 1,327 | +2 |
| 2026-08-03 | 1,332 | 1,334 | +2 |

V2 has 1,313 common observations, 21 added observations and 14 disappeared observations between the two source editions. Appearance/disappearance remains an observational comparison, not an administrative registration/removal inference.

## Parsing method

V2 is **lossless-first** and uses `pdftotext -bbox-layout` word coordinates instead of relying on whitespace text alone.

For the Cosenza schema fingerprint `fbb124c5a43d26bef93316844b3021096060f7ed9d2cc0f8f6081f6df935dc97`, words are assigned to source columns using their PDF x coordinates. Row existence is established by table geometry and row context; formal identifier validity is never required.

The row-start rule requires a business-name cell and registered-office cell together with either:

1. a non-parenthesized application date in the application-date column; or
2. an 11-digit identifier plus application/outcome row context.

This admits malformed or alphanumeric-only source identifiers when the table structure clearly identifies a row while rejecting continuation lines lacking row context.

## Source columns persisted

V2 persists seven source columns for every parsed row:

1. `Ragione sociale`
2. `Sede legale`
3. `Sede secondaria`
4. `Codice fiscale/Partita IVA`
5. `Attività per cui è richiesta l’iscrizione`
6. `Data di presentazione dell’istanza`
7. `Esito`

All raw values are retained. Parsed JSON is supplementary and never replaces the source value.

### Identifier semantics

The source identifier field is explicitly multi-valued. V2 preserves unexpected/malformed values rather than repairing them silently.

Examples of parser annotations:

- 11-digit numeric: candidate `IT_VAT` / `IT_CF`, unless an explicit source `C.F.` hint narrows the candidate;
- 16-character alphanumeric: `IT_CF_CANDIDATE`;
- unexpected numeric length: `UNKNOWN`.

None of these annotations resolve a canonical `LegalEntity`.

### Dates and Esito

Application dates are retained as a list and preserve whether a date was parenthesized in the source.

`Esito` is stored in full as a raw source value. V2 additionally extracts diagnostic observations such as:

- `observed_listing_date` from wording such as `INSERITO NELLE LISTE IN DATA ...`;
- `observed_expiry_date` from wording such as `Scadenza ...`;
- renewal-request and update-in-progress flags.

These remain **source observations**. `observed_listing_date` is not automatically a canonical registration date, and `observed_expiry_date` is not automatically a canonical loss-of-effect date.

## Validated field coverage

| Field | 2026-06-28 | 2026-08-03 |
|---|---:|---:|
| Parsed rows | 1,327 | 1,334 |
| Registered office | 1,327 | 1,334 |
| Identifier field | 1,327 | 1,334 |
| Requested activities | 1,327 | 1,334 |
| Application-date field | 1,327 | 1,334 |
| Outcome | 1,327 | 1,334 |
| Secondary office | 1 | 1 |
| Observed listing date | 452 | 461 |
| Observed nominal expiry | 213 | 215 |

Across both editions V2 persists **2,661 ParsedRecords**, **18,627 SourceFieldValues** and **2,661 unresolved EntityMentions**. Parsing creates zero canonical entities.

## National parser quality rule

The Cosenza checkpoint establishes the minimum quality principle for future Prefecture parsers:

> A parser is not ready for national scale-out merely because it identifies most rows. It must first inventory the source schema, preserve every observable source column, support source cardinality without silent coercion, retain raw evidence, and demonstrate row-level recall/precision against representative edge cases.

A simpler parser can still be retained as an exploratory or historical ParseRun, but it must not silently become the production/canonical ingestion baseline.

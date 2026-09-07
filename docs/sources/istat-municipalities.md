# Istat municipality and statistical-geography crosswalk

## Role

The Istat permanent municipality workbook is the preferred current crosswalk between a municipality name and the administrative/statistical identifiers required by the archive.

It is used **before** ANNCSU civic-access matching:

```text
White List source address
        ↓
municipality resolution against versioned Istat names/codes
        ↓
ISTAT municipality code + cadastral/Belfiore code
        ↓
ANNCSU regional civic-access dataset
        ↓
odonym/civic matching and coordinates
```

The authority that publishes a White List is not assumed to be the municipality of an establishment. The Cosenza register, for example, contains registered offices in many municipalities and also foreign addresses.

## Official current source

Istat publishes a permanent XLSX URL whose content is replaced when the official current municipality list changes:

```text
https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.xlsx
```

Istat's administrative-unit page states that current and date-specific territorial reports are also available through SITUAS. The permanent workbook is therefore the current-state input; SITUAS remains the route for historical reconstruction where the geography valid at an earlier observation date is required.

## Observed version — 2026-02-21

A controlled GitHub-hosted probe on 7 September 2026 observed:

```text
HTTP status      200
Last-Modified    Thu, 26 Feb 2026 16:17:49 GMT
XLSX bytes       1,229,843
XLSX SHA-256     83842076860450f7e482daecea6b7a769f5f93d0bf5b0d48802b44896d7a26d5
data sheet       CODICI al 21_02_2026
municipalities   7,894
```

The provider version is derived from the effective date encoded in the official data-sheet name (`2026-02-21`), not from local capture time or the HTTP `Last-Modified` timestamp.

## Fields retained

The normalised crosswalk preserves the Istat fields needed both for entity resolution and for statistical geography:

- current municipality code, in alphanumeric and numeric form;
- historical municipality-code variants supplied by Istat;
- municipality progressive code;
- official combined, Italian and other-language names;
- cadastral/Belfiore code;
- region code and name;
- statistical supra-municipal unit code, name and type;
- historical province code;
- province vehicle abbreviation;
- geographic division;
- NUTS1/NUTS2/NUTS3 under the 2021 nomenclature;
- NUTS1/NUTS2/NUTS3 under the 2024 nomenclature.

The source workbook currently exposes 27 columns. The acquisition layer fails if one of the required columns disappears instead of silently producing a partial crosswalk.

## Why versioning is mandatory

Administrative codes and territorial structures are not timeless. The current Istat publication explicitly includes code series for different historical province configurations and both NUTS 2021 and NUTS 2024. Territorial reforms can also recode municipalities. Consequently:

- `municipality_scheme_version` must refer to the effective Istat/SITUAS state;
- NUTS assignments must retain their nomenclature/version;
- an address observation from an earlier period must not automatically inherit today's territorial codes when a historical assignment is required.

For current 2026 White List enrichment, the 21 February 2026 current-state crosswalk is the appropriate baseline unless a later Istat version supersedes it before the enrichment run.

## Identifier examples

The crosswalk directly bridges the identifiers used downstream by ANNCSU:

```text
Cosenza
ISTAT municipality code    078045
Belfiore/cadastral code     D086
NUTS3 2024                  ITF61

Rende
ISTAT municipality code    078102
Belfiore/cadastral code     H235
```

These are municipality identities only. They do not imply that every source string beginning with the same municipality name has been successfully matched to a street or civic access.

## Reproducible acquisition

```text
white-list-istat-municipalities-acquire \
  --output-dir artifacts/istat/municipalities
```

For a frozen validation run, the caller can supply the expected XLSX SHA-256. The acquisition command:

1. downloads the official permanent workbook to a temporary file;
2. hashes and validates the XLSX archive;
3. identifies exactly one `CODICI al DD_MM_YYYY` data sheet;
4. validates the required schema and unique municipality/Belfiore identifiers;
5. writes a deterministic UTF-8 CSV crosswalk;
6. hashes both original workbook and normalised CSV;
7. writes a manifest containing source URL, capture time, effective provider version, HTTP metadata, physical file identities, row count and schema.

No municipality-name fuzzy matching occurs in the acquisition layer. Name normalisation and White List address resolution are separate, testable stages.

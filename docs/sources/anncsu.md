# ANNCSU official address-data acquisition

## Role in the archive

ANNCSU (Archivio Nazionale dei Numeri Civici e delle Strade Urbane), maintained by Istat and Agenzia delle Entrate, is the preferred official source for Italian street/civic address enrichment.

ANNCSU is downstream enrichment. It must never overwrite the address string supported by a Prefecture source or the canonical address identity derived from that source.

## Reproducible bulk route

The official bulk endpoint expects the dataset identifier as a **bare query key**:

```text
https://anncsu.open.agenziaentrate.gov.it/age-inspire/opendata/anncsu/getds.php?INDIR_CALA
```

Do not append `=`. A controlled GitHub-hosted runner probe on 7 September 2026 established:

```text
?INDIR_CALA    -> official ZIP response
?INDIR_CALA=   -> HTTP 406: request value INDIR_CALA= invalid
```

The earlier 406 was therefore a query-shape error, not evidence that GitHub-hosted automation was blocked.

## Observed Calabria dataset — 2026-08-03

The production-format probe downloaded and validated the official regional archive:

```text
ZIP bytes       16,411,963
ZIP SHA-256     65136ad879e33bca5e776f526fe77d17bd3b141a434575591873c842e23ef0aa
CSV member      INDIR_CALA_20260803.csv
CSV bytes       114,336,382
CSV SHA-256     7da7624090f4cc096f7981d91e6f820f73450c773bea5343bc1a9f8963431784
encoding        UTF-8 with BOM
separator       ;
rows            1,405,503
```

The provider version is derived from the official member name (`2026-08-03`), not from local capture time.

The acquisition command hashes both ZIP and CSV and writes an explicit manifest containing source URL, capture time, physical file identity, provider version, HTTP metadata, encoding, delimiter and observed field names.

## Required physical fields

The current parser requires the documented ANNCSU address fields:

```text
CODICE_COMUNE
CODICE_ISTAT
PROGRESSIVO_NAZIONALE
CODICE_COMUNALE
ODONIMO
LOCALITA'
DIZIONE_LINGUA1
DIZIONE_LINGUA2
PROGRESSIVO_ACCESSO
CODICE_COMUNALE_ACCESSO
CIVICO
ESPONENTE
SPECIFICITA
METRICO
PROGRESSIVO_SNC
COORD_X_COMUNE
COORD_Y_COMUNE
QUOTA
METODO
```

Additional future fields are tolerated; disappearance of a required field is a schema failure.

## Cosenza diagnostic

For `CODICE_COMUNE = D086` in the 2026-08-03 Calabria dataset:

```text
ANNCSU civic-access rows           23,654
rows with longitude + latitude    23,654
METODO = 3                         22,924
METODO = 5                            730
```

This diagnostic is **not** the number of White List addresses geocoded. It establishes only that ANNCSU has coordinate coverage for its current civic-access rows in the Comune di Cosenza. White List linkage is a separate, audited activity.

## Coordinate semantics

ANNCSU X/Y identify an external civic access in ETRF2000/ETRS89 geographic coordinates. They must not be relabelled generically as `rooftop` coordinates.

The enrichment layer should use a distinct `civic_access` precision and preserve `METODO` as provider evidence. Match confidence measures the confidence of the White List address-to-ANNCSU linkage; it must not be used as a surrogate for ANNCSU's spatial acquisition method or positional accuracy.

## CLI

```text
white-list-anncsu-acquire --dataset INDIR_CALA --output-dir artifacts/anncsu/calabria
```

For a frozen/reproducibility run, the caller can also provide the expected ZIP SHA-256. A mismatch fails rather than silently accepting changed upstream bytes.

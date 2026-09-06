# Data releases

This directory is reserved for **versioned, intentionally released data products**.

It is currently empty of row-level White List data.

The absence of a file here does not mean the project has collected no data. Source-discovery datasets and capture manifests live in the other `data/` layers, while row-level source observations and canonical administrative data are developed in the database/internal archive before dissemination review.

A dataset may enter this directory only when:

1. its semantics and schema are documented;
2. provenance back to source captures is preserved;
3. data-quality checks pass;
4. privacy/reuse/licensing implications have been reviewed;
5. the release is added to `data/catalog.csv`;
6. a release note records version, scope, known limitations and generation revision.

Preferred release formats are CSV for accessibility, Parquet for analytical use and JSON/JSON-LD where structured interchange or linked-data semantics are useful.

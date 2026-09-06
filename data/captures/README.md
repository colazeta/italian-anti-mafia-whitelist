# Capture manifests

This directory stores **metadata manifests and aggregate diagnostics**, not raw White List documents or row-level extracted datasets.

## Policy

- Original public-source bytes are identified by SHA-256.
- Capture manifests preserve URL, HTTP metadata, capture time, byte size, content type and processing lineage.
- Raw PDFs and row-level extracts are not committed to Git.
- GitHub Actions artifacts may be used during development, but are considered ephemeral rather than durable archival storage.
- The intended durable architecture is content-addressed object storage, with the resulting immutable object URI recorded in `source.content_object.storage_uri`.
- Aggregate diff files must preserve the distinction between source-observation events and administrative/legal events.

A future publication layer may expose transformed data according to the repository's dissemination profiles; this directory is not itself a public-data export surface.

# Offline private recovery bundle contract

The existing recovery workflow already verifies selected archived originals and
their capture provenance against an approved independent S3-compatible recovery
store. It must remain the ordinary provider-backed recovery path. The offline
bundle tool addresses a separate gap: verification of an explicitly selected
private package after an authenticated export and a separate provider download.
It does not create a transport, obtain credentials, access a provider or publish
anything.

## Available capabilities and the current transfer prerequisite

The connected Drive file API can upload an absolute local file path as a new raw
file and download it again. That interface alone does not establish that a
particular account or destination is currently accessible or private; verify
those properties before transferring project material.

Existing R2 credentials are available to protected GitHub Actions jobs. They are
not implicitly available to Work or the Drive connector. Existing Drive connector
authorisation is not implicitly available to an Actions runner. Consequently,
the two working integrations do not themselves form an authenticated R2-to-Drive
byte path. An authenticated private export of the exact R2 objects and database
dump into the authorised local workspace remains a prerequisite. Do not place
credentials, signed bearer URLs, originals, dumps or private row extracts in
public logs, issue comments or Actions artifacts to bridge this gap. Do not use
database observation or provenance rows as a file-transport mechanism.

No new infrastructure, credentials or permission changes are introduced by this
tool. If the export channel is unavailable, provider-independent backup remains
blocked even when offline tests pass.

## Explicit selection and trusted pins

Prepare a private JSON plan containing only relative path and file role, for
example:

```json
[
  {"path": "database.dump", "role": "postgres_dump"},
  {"path": "database-verification.json", "role": "postgres_verification"},
  {"path": "originals/document.pdf", "role": "original"},
  {"path": "captures/capture.json", "role": "capture_provenance"}
]
```

The accepted roles are `postgres_dump`, `postgres_verification`, `original`,
`capture_provenance`, `parser_snapshot` and `scope_inventory`. Roles describe
selection purpose; a filename or role does not prove semantic validity. Selection
must account for the intended denominator separately, including all required
originals, capture/check provenance, snapshot lineage and database links. The tool
never discovers additional files in a directory, preventing accidental inclusion
of credentials or unrelated private documents.

Export already retrieved files into a new private package:

```bash
python -m white_list_archive.storage.recovery_bundle export \
  --private-directory /private/verified-export \
  --plan /private/recovery-plan.json \
  --output /private/recovery-package.zip
```

The resulting ZIP contains a versioned manifest and every explicitly selected
file, with SHA-256 and byte size. The command rereads the actual ZIP before
reporting success and emits only aggregate counts, role counts and digests. Retain
both the archive and manifest SHA-256 values in an independently trusted private
checkpoint **before** transferring the package. A hash recovered only from the
downloaded package is not an independent integrity pin.

Upload only through the authenticated private destination, verify its access
state, then download the provider's stored bytes into a new local file. Verify
that download against the pre-transfer pins and optionally copy it into a clean
directory:

```bash
python -m white_list_archive.storage.recovery_bundle verify \
  --archive /private/provider-download.zip \
  --archive-sha256 EXTERNALLY_PINNED_ARCHIVE_SHA256 \
  --manifest-sha256 EXTERNALLY_PINNED_MANIFEST_SHA256 \
  --restore-directory /private/new-clean-directory
```

## Verification boundary

Verification checks both external pins, every selected member's size and SHA-256,
and exact equality between manifest selection and ZIP membership. Duplicate
members, traversal paths, symlinks, unsupported file types, encrypted ZIP members,
unexpected payloads, excessive file counts and excessive uncompressed sizes fail
closed. All checks precede extraction. Existing output packages and restore
directories are refused; restored members are written as new private files and
hashed again. No SQL, parser or executable contained in a member is executed.

The aggregate result deliberately keeps these claims false:

- `independent_backup_verified`: storage and administrative independence require
  separately reviewed responsibility, access and retention evidence;
- `database_restore_verified`: copying a dump is not executing a PostgreSQL restore
  and comparing its logical content;
- `national_completeness_verified`: an explicit selection may be a bounded pilot.

A production database restore must still use the clean PostgreSQL restore gate;
originals and their provenance must still pass the frozen-release recovery gate.
An independently downloaded Cosenza-only package remains a Cosenza-only result.
This contract provides reusable integrity verification without reclassifying the
existing snapshot JSON copy or closing issue #16.

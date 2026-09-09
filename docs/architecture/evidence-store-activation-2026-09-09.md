# R2 evidence-store activation record — 2026-09-09

## Status

**LIVE PROVIDER VERIFICATION PASSED; OPERATIONAL READINESS REMAINS OPEN.**

This record documents the designated private Cloudflare R2 backend for the White List source-evidence archive and the live provider-verification evidence obtained on 2026-09-09. The R2 write/read/idempotence gate has passed. Independent backup/recovery and database promotion remain separate open controls, so issue #16 and the national durable-storage readiness gate remain open.

## Designated backend

- Provider: Cloudflare R2 Object Storage
- Bucket: `italian-anti-mafia-whitelist-evidence`
- Jurisdiction: European Union
- Default storage class: Standard
- S3 signing region used by the application: `auto`
- S3 endpoint pattern: `https://<ACCOUNT_ID>.eu.r2.cloudflarestorage.com`
- Evidence namespace: `sha256/`

No credentials, account identifiers or secret values are recorded in Git.

## Access and immutability controls

Operator-confirmed on 2026-09-09:

- public development URL is not enabled;
- no custom domain is attached to the bucket;
- a Bucket Lock rule applies to prefix `sha256/` with indefinite retention;
- the ingestion credential is an account API token restricted to this bucket with Object Read & Write permissions;
- GitHub environment `evidence-archive` holds runtime configuration and credentials separately from the repository.

The application writes evidence only under content-addressed keys of the form:

```text
sha256/<first-two-hex>/<full-sha256>
```

The indefinite Bucket Lock is the provider-side control preventing deletion or overwrite of evidence objects in that namespace. Application-side conditional creation (`If-None-Match: *`) and post-write full-object SHA-256 verification remain mandatory independent controls.

## Live verification history

### Attempt 1 — compatibility failure, not storage-integrity failure

The first `Private evidence store verification` run on 2026-09-09 passed environment/configuration and credential preflight, reached the designated R2 bucket, uploaded the first frozen Cosenza object, and then failed during the repeated-upload idempotence probe. R2 returned `ObjectLockedByBucketPolicy` for the already protected content-addressed key instead of the generic S3 `412 PreconditionFailed` response assumed by the adapter.

The adapter was corrected without weakening immutability: `ObjectLockedByBucketPolicy` is treated only as a possible existing-object signal and must be followed by a full object retrieval with independent byte-size and SHA-256 verification. A missing or mismatching object still fails; no unconditional overwrite, delete, lock bypass or metadata-only trust was introduced.

### Attempt 2 — passed

Manual workflow run **34327668707** on `main` commit `d8ec8d15d54a19acf32dc9bc3b35db3b9d790326` completed successfully on 2026-09-09.

The live gate verified both frozen Cosenza source documents:

- reference date `2026-06-28`, SHA-256 `565a71d89c4d684b68303949974a6c63410b9432eefe9f3773ac540a4318a07d`, 1,072,912 bytes;
- reference date `2026-08-03`, SHA-256 `0d1ebcdaec25ea5a9f9dc859e2c68bea3ac72ceb988fed4eed4f8ba2ce338202`, 1,077,994 bytes.

For each document the workflow verified the official source bytes against the frozen manifest, exercised the content-addressed R2 archive path, repeated the upload operation under Bucket Lock, retrieved the stored object, and recomputed byte size and SHA-256. The June object already existed because the first run had uploaded it before failing on the repeat-write probe; the second run independently verified that locked object. The August object was created during the successful run and its repeated write was safely handled through the locked-existing-object verification path.

The successful run produced the legacy Actions artifact:

`private-evidence-receipts-34327668707-1`

with artifact digest:

`sha256:8317c89bb193c814b06650ea20634da99dcc0ef06c1c8c80f2f57f168c8ddae3`

That historical artifact contains verification receipts only, not source PDFs or credentials, but the repository is public and the artifact must not be described as a private control surface. Its full runtime receipts include storage/provider coordinates that are unnecessary for public verification. The workflow contract has therefore been tightened: future runs upload only redacted verification records containing content identity, idempotence/full-object-integrity assertions, database-promotion status, verification time, the frozen manifest digest and a digest binding to the reviewed policy record. Provider endpoint, bucket/storage URI, policy locator, source URL and capture metadata are excluded from future uploaded artifacts. The full runtime receipt remains inside the trusted job only.

The successful 2026-09-09 live result itself remains valid: the receipts record successful full-object verification and `database_promoted=false`, because no `EVIDENCE_DATABASE_URL` was configured for this gate. Redaction changes only the future workflow publication boundary; it does not alter the R2 evidence or reclassify the live provider test.

## GitHub environment contract

The `evidence-archive` environment is expected to contain:

| Kind | Name | Expected value/purpose |
| --- | --- | --- |
| Variable | `EVIDENCE_BUCKET` | `italian-anti-mafia-whitelist-evidence` |
| Variable | `EVIDENCE_ENDPOINT` | EU-jurisdiction R2 S3 HTTPS origin |
| Variable | `EVIDENCE_REGION` | `auto` |
| Variable | `EVIDENCE_POLICY_EVIDENCE` | this document's repository-relative path |
| Secret | `EVIDENCE_ACCESS_KEY_ID` | restricted R2 ingestion credential |
| Secret | `EVIDENCE_SECRET_ACCESS_KEY` | restricted R2 ingestion credential |
| Secret, optional | `EVIDENCE_SESSION_TOKEN` | temporary token if applicable |
| Secret, optional | `EVIDENCE_DATABASE_URL` | existing archive database for verified promotion |

The intended value of `EVIDENCE_POLICY_EVIDENCE` is:

```text
docs/architecture/evidence-store-activation-2026-09-09.md
```

## Controls still open

The live R2 provider gate is now verified. The following remain explicit open controls:

1. independent backup/recovery responsibility and a documented restore test;
2. promotion of verified durable locations/status into the existing archive database when a production `EVIDENCE_DATABASE_URL` is designated;
3. any additional provider-level recovery/version controls outside the verified `sha256/` Bucket Lock;
4. periodic re-verification of access, retention and retrieval controls.

Until the applicable remaining controls are closed, issue #16 remains open and national readiness must not be represented as fully verified.

## Change-control rule

Any later change to bucket name, jurisdiction, endpoint, public-access state, lock prefix/retention, credential scope, backup policy or recovery design requires an updated activation record and corresponding documentation change. Secret values must never be committed to Git, public artifacts, issue comments or receipts.

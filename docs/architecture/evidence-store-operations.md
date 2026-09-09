# Private evidence store: operation and activation

## Implementation and limits

`storage/evidence.py` implements the existing source-evidence architecture using
S3-compatible conditional writes. It does not create an account/bucket or claim
that a provider is configured. An R2 backend has now been provisioned; live provider
verification and independent backup/restore evidence remain pending, so national
durable-storage readiness is **not yet VERIFIED**. No original capture manifest or
canonical company identity changes.

Keys are `sha256/<first-two-hex>/<full-sha256>` without filename extensions, so
byte identity does not vary with a renamed file or MIME label. This is the
extensionless form of the architecture's recommended key, not a new identity model.
Local bytes must match both frozen size and SHA-256 before any upload. A conditional
PUT uses `IfNoneMatch="*"`. Only a precondition failure is treated as a possible
existing object; permissions, conflicts (409), network errors and unsupported
operations fail. After either PUT or precondition failure, an independent GET
hashes the full object. HEAD, ETag and user metadata are insufficient evidence.
A 409 is retried by rerunning the operation, never by an unconditional overwrite.

Reference contracts: [Boto3 PutObject](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html)
and [S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html).
Provider compatibility, including enforcement of conditional creation, must be
verified before a store is designated for production. Unsupported conditional
writes are not silently replaced with an unsafe fallback.

## Designate the private backend

Use the existing approved S3-compatible/R2 storage class. Before activation,
record the actual account, bucket, HTTPS endpoint and region in the private
operational configuration. Record a reviewed policy covering:

- private access, no public website or anonymous object access;
- enforced conditional creation and no ingestion-role delete/overwrite privileges;
- no expiration of evidence objects; appropriate retention/versioning or lock;
- independent backup, recovery responsibility and a documented restore test;
- permitted internal retention and separate public redistribution decisions.

The current operator-confirmed R2 configuration and its still-open gates are recorded
in [`evidence-store-activation-2026-09-09.md`](evidence-store-activation-2026-09-09.md).
That record is a configuration/policy locator, not proof that all provider and recovery
controls have passed live verification.

The program requires a policy-evidence locator; this is an explicit operator
attestation, not automated inspection of all backend controls. A successful PUT/GET
alone does not prove permanent preservation or fulfil the national readiness gate.
Keep version recovery/administrative permissions separate from ingestion credentials.
Never put credentials in Git, receipt URLs or chat. Keep environment configuration
and private receipts out of `public-site/` and Dataset Explorer public exports.

Create/configure GitHub environment `evidence-archive` with these exact names:

| Kind | Name | Purpose |
| --- | --- | --- |
| Variable | EVIDENCE_BUCKET | Designated private bucket |
| Variable | EVIDENCE_ENDPOINT | HTTPS S3 API origin, no embedded credentials |
| Variable | EVIDENCE_REGION | Provider signing region |
| Variable | EVIDENCE_POLICY_EVIDENCE | Locator of reviewed retention/access/backup evidence |
| Secret | EVIDENCE_ACCESS_KEY_ID | Restricted ingestion credential |
| Secret | EVIDENCE_SECRET_ACCESS_KEY | Restricted ingestion credential |
| Secret, optional | EVIDENCE_SESSION_TOKEN | Temporary credential token |
| Secret, optional | EVIDENCE_DATABASE_URL | Existing archive database for verified promotion |

No new database is created. Without the database secret, the live workflow can
verify storage but explicitly leaves `database_promoted=false`. National readiness
must not advance on that partial result. Restrict the environment to the protected
main branch. The workflow also checks main and has no schedule/PR secret execution.

## Execute and recover

Install `.[storage,database]`. The `Private evidence store verification` manual
workflow downloads the two exact official URLs in the frozen Cosenza manifests.
If access fails or bytes differ it stops; it never relabels changed bytes as the
old edition. Original manifest files remain immutable. If original URLs disappear,
recover the exact bytes from existing private evidence packages/backups and use
the CLI; verify the same frozen hashes. Do not infer lost bytes from the URL alone.

For local execution, configure the EVIDENCE variables above and standard AWS SDK
credentials (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, optional AWS_SESSION_TOKEN).
The CLI accepts existing files and frozen manifests:

```bash
white-list-evidence-store archive --manifest capture.json --file original.pdf --receipt new-private-receipt.json
white-list-evidence-store retrieve --manifest capture.json --file recovered-copy.pdf
```

Add `--promote` to archive only with EVIDENCE_DATABASE_URL for the designated
existing database. This locks the matching ContentObject, rejects missing or
conflicting metadata/durable locations, retrieves and hashes again, then updates
only storage URI/status in the caller transaction. It never inserts companies,
changes content identity or creates source captures. The private HTTPS storage
locator includes endpoint and bucket to avoid collisions across S3 providers.
The frozen capture still links to the same ContentObject. Existing manifest
import remains idempotent and cannot downgrade durable status.

Receipts bind source URL, capture/reference dates, canonical JSON manifest hash,
content hash, location, policy evidence and verification time. They are private;
CLI refuses to overwrite an existing receipt or recovered file. Preserve live
verification receipts in the designated internal audit record; workflow artifacts
are bounded review copies, not permanent evidence storage. Frozen source manifests
already preserve original acquisition provenance in Git.

If upload succeeds but verification or SQL fails, no database promotion occurs.
The object may already exist; rerun with a new receipt path. If SQL commits but
receipt writing fails, rerun to retrieve/verify and recreate evidence safely.
Never delete original objects to roll back code or overwrite a corrupt key.
A missing/corrupt durable object requires incident recording and restoration from
a known-good backup/version, followed by independent verification. The existing
schema prohibits status downgrade; this implementation preserves that rule and
does not silently reset a missing durable object to ephemeral.

The CLI's retrieve command supplies verified originals to existing parser/Explorer
packaging paths; source-page locators and publication rules remain unchanged.

## Acceptance evidence

Local tests use a protocol double and Boto3 Stubber: they prove application
behaviour, not provider durability. CI additionally exercises promotion and
idempotence against real PostgreSQL constraints with synthetic object transport,
rolling back its synthetic row. The manual workflow is the separate live gate:
both frozen documents, repeated upload, verified recovery, optional real database
promotion. Policy/access/retention/backup verification must also be recorded before
marking the operational prerequisite VERIFIED or closing issue #16.

# Cosenza operational check — 8 September 2026

Recorded at 2026-09-08T16:57:43Z. Mode: EXPANSION_MODE.

## Selection and evidence

The refreshed issue tracker still lists #16 (durable evidence storage) and #20
(source-population gaps). The initial national queue selected Cosenza: it already
has a validated canonical integration and the oldest recorded investigation among
the four public pilots. This is a completion investigation, not a new parser template.

Official landing page:
https://prefettura.interno.gov.it/it/prefetture/cosenza/evidenza/white-list

The retrieval service returned HTTP 403. A separate browser visit displayed
“Access Denied” with reference `18.bc53dd58.1788886483.2b4aefc`.
Neither attempt yielded source content sufficient to identify the current edition.
This is a failed investigation from this execution environment, not evidence that
the source is absent or unavailable to everyone. The earlier GitHub public-link
audit received HTTP 200; that bounded availability probe did not inspect current
edition semantics. No successful source-check timestamp is asserted.

The approved 3 August 2026 combined PDF is independently hash-verified by the
successful main-branch Cosenza pipeline, run 34252881934. This verifies existing
source bytes and the regression baseline, not the absence of a newer edition.
The two frozen capture manifests, parser-v2 history and canonical identities remain
unchanged. No PDF was recaptured just to record this failed page check.

## Remaining production blocker

Issue #16 remains open. `db/schema/045_capture_operational_metadata.sql` and
`persistence/capture_manifest.py` distinguish ephemeral and durable storage;
the current manifests explicitly say `workflow_artifact_ephemeral`.
No object-store endpoint/bucket integration is configured in the acquisition
workflows, and this execution has no configured object-store credentials.
GitHub artifacts therefore cannot satisfy permanent preservation.

The existing approved architecture specifies a dedicated S3-compatible/R2 or
equivalent backend. To resume production completion, provide the designated
private evidence bucket/endpoint and authenticated access, with its retention and
backup policy. Then implement and verify idempotent SHA-256-addressed writes,
independent retrieval verification and durable ContentObject location/status.
Do not move source PDFs into Git, assume public redistribution, or weaken the gate.

## Result and next action

Coverage is BLOCKED, with last completed stage VALIDATED. Existing public export
stays enabled. Monitoring is CHECK_FAILED; last successful source check and last
content-change timestamp remain unknown. The latest approved reference date stays
2026-08-03. National expansion is incomplete; maintenance mode has not started.

Resume Cosenza after the access/storage prerequisites are resolved, inspect the
current landing-page edition, and then close its remaining preservation gates.
No next Prefecture is started while this incomplete cycle is paused on the global
storage prerequisite. Other queue entries are not represented as completed.

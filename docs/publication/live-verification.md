# Live publication verification

The sole Public retro portal publisher verifies the actual live Pages bytes after a successful deployment. `public_snapshot verify-live` reads exactly the five public derivative files from the configured project Pages origin, checks every decoded byte length and SHA-256 against the selected versioned manifest, and logs only file names, hashes, sizes and the release tag. It does not read original PDFs, private storage or database records.

The deployment environment URL must match the existing project origin. Each URL includes the selected release tag and retry number to avoid stale cache reuse. CDN propagation can be retried four times per file with bounded 5/10/15-second pauses; persistent missing, oversized or mismatched data makes the publisher fail. A GitHub release download is never a substitute for the live check. Existing source review, candidate, privacy, browser and pre-deployment integrity gates remain in place.

The check does not change the selector, erase a release or perform an automatic rollback after a failed check. A successful provider deployment alone is insufficient to mark the full publisher run successful. An operator/automation must investigate a mismatch using the selected immutable manifest and retained rollback, without approving changed data merely to make the check pass.

Unit tests cover the closed origin/file surface, complete five-file verification, temporary stale content followed by convergence, and persistent content mismatch without a release fallback. This workflow completes the deployment proof for the Perugia November release while making the same proof repeatable for later approved releases.

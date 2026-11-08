# Durable source-only owner request queue

Issue225 is the request ledger for the two existing exact owner commands. The
worker reads all comment pages (100 per page, at most 100 pages and 1,000 owner
requests). Reaching a limit fails closed instead of pretending the ledger is
complete. Only owner-authored, exact, originally unedited comments on that
non-PR issue qualify. GitHub comments are mutable: `created_at == updated_at` is
required, and the worker never reconstructs an edited command's earlier intent.

There is no workflow-level concurrency. Unrelated comments fail the secret-free
authorisation gate before entering protected concurrency. The protected worker
serialises source operations; any eligible replacement drains the entire ledger,
so GitHub's single pending-run replacement cannot drop a request. The existing
successful ordinary Prefecture robots run wakes recovery through `workflow_run`;
there is no additional schedule, service, credential or privilege grant. Push and
manual preflight paths also drain prior explicit ledger requests; they confer no
new authorisation themselves.

Before writing source facts, each request receives its own private immutable R2
acceptance receipt, including comment identity, creation timestamp, body digest,
exact capture/snapshot pair and frozen code revision. Conditional creation and
bounded readback prohibit replacing an accepted binding. The worker records
completion only after committed independent source readback and read-only QA
whose report is durably retained privately. Repeated commands have separate
request receipts; equivalent input pairs reuse already verified evidence rather
than silently dropping the repeated request or creating duplicate source facts.

An interrupted request resumes using its original code revision. A detached
worktree must contain that actual SHA and it must be an ancestor of the trusted
executing main checkout. The operation executes inside that worktree with its
own source path; passing an old SHA to newer parser code is prohibited. Child
stdout/stderr remain captured, bounded output is validated against a closed
source-only result allowlist, and errors expose no driver messages or rows.
There are no edition, semantic, canonical or publication writes in this route.

Each wake-up bounds new request processing and expensive distinct verification
work to fifty items. Previously completed equivalent requests share independent
readback within that worker, allowing later pending requests to advance on the
next wake-up rather than repeatedly processing the first page. The safe console
report gives expected, verified and pending request counts, bounded remainder,
diagnostic failures and verified private QA reports. Run registration, a pending
job, or an immutable completion receipt alone is insufficient: each wake-up
rechecks the underlying committed rich evidence. A successful source queue
report keeps semantic and publication readiness false. Owner review and the
separate authorised publisher remain necessary downstream.

The operational limitation is the existing daily recovery wake-up: GitHub must
deliver at least one eligible owner/preflight/robots event and provide its normal
runner and protected-environment access. Ledger/API, receipt, ancestry, parser,
readback or QA failures remain visible as incomplete/failing work, not success.

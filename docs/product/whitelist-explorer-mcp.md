# Whitelist Explorer MCP

## Purpose

Whitelist Explorer MCP is the read-only agent interface for the reviewed public
dissemination layer of the Open Italian Anti-Mafia White List Archive.

It does **not** expose the private audit database, internal source observations,
semantic review objects or unpublished canonical entities. It follows the
selected public snapshot in:

\`data/publication/public_snapshot.json\`

and therefore changes data release only when the repository deliberately
promotes a reviewed public snapshot.

## Public endpoint

The deployed service exposes Streamable HTTP at:

\`/mcp\`

and an unauthenticated liveness route at:

\`/health\`

The MCP server uses the official Python MCP SDK 2.x. The production deployment
is stateless for the legacy HTTP leg and is naturally sessionless for the
2026-07-28 MCP protocol.

## Tools

### \`search_registry\`

Search public source-backed observations by:

- company name or other published text;
- exact-looking CF / P.IVA identifier;
- Prefecture;
- source status;
- register name.

The result denominator is observations, not unique legal entities.

### \`get_observation\`

Return one exact public observation from its record locator.

### \`get_prefecture\`

Return national-index/source-mapping metadata plus aggregates for the
observations currently published for that Prefecture.

### \`compare_prefectures\`

Compare up to 20 Prefectures. Counts remain observation counts and the tool
states its denominator explicitly.

### \`date_distribution\`

Build distributions for:

- \`application\` → \`application_date\`;
- \`expiry\` → \`observed_expiry_date\`;
- \`reference\` → \`reference_date\`;
- \`listing\` → \`observed_listing_date\`.

Buckets can be day, month or year. Missing/unusable dates remain explicit rather
than being silently dropped from the denominator.

This supports, among other things, the public-portal analyses of application
dates for observations in istruttoria and expiry dates for observations in
renewal/update states.

### \`get_history\`

Expose the aggregate public history ledger. Edition disappearance remains an
observational fact and is never translated automatically into administrative
removal or cancellation.

### \`get_robot_directory\`

Expose the reviewed public robot/source-mapping directory. This is configuration
metadata and **not** live robot execution health.

### \`get_dataset_metadata\`

Return the selected release identity and current public denominators.

## Snapshot loading and integrity

The service does not read an arbitrary "latest release".

On refresh it:

1. downloads and validates \`public_snapshot.json\`;
2. follows its exact \`release_tag\`;
3. streams and decompresses only the required release assets;
4. verifies each uncompressed asset against the byte count and SHA-256 recorded
   in the reviewed manifest;
5. builds an ephemeral SQLite query index from \`registry.csv\`;
6. atomically switches to the new verified cache.

If GitHub is temporarily unavailable after at least one successful refresh, the
service keeps serving the last locally verified snapshot and discloses the
refresh error in provenance metadata. It never silently substitutes another
release.

## Interpretation invariants

Every consumer must preserve these rules:

- public rows are source-backed observations, not a nationally deduplicated
  company register;
- source status is not an independent certification of current legal status;
- a nominal expiry date is not automatic loss of legal effect;
- disappearance across editions is not automatic administrative removal;
- requested activities must not be promoted to listed relationship sectors
  without separate evidence;
- a mapped/discovered Prefecture is not the same as a Prefecture with published
  row-level observations in the selected snapshot;
- missing dates remain missing.

## Local run

\`\`\`bash
python -m pip install -e '.[mcp]'
PORT=10000 white-list-public-mcp
\`\`\`

Then connect an MCP client to:

\`http://127.0.0.1:10000/mcp\`

The first data-bearing tool call may build the local snapshot cache. Protocol
discovery and the health route do not require that download.

## Deployment

The production service is intended to run as a small Python web service from the
same repository. No PostgreSQL service is required: the MCP layer consumes only
reviewed public release derivatives and builds a disposable SQLite index.

Recommended Render configuration:

- runtime: Python;
- region: Frankfurt;
- build: \`python -m pip install -e '.[mcp]'\`;
- start: \`white-list-public-mcp\`;
- branch: the reviewed deployment branch;
- auto-deploy: enabled.

The server is read-only and serves public data. TLS and the public Host header
are terminated/controlled by the hosting reverse proxy.

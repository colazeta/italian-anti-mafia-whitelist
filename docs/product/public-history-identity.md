# Public history: data editions versus technical captures

## Problem and decision

The immutable public history ledger records approved source-document/parser versions,
not necessarily distinct publications of data. Some dynamic HTML pages produce a
different SHA-256 value on every approved capture even though the reviewed source
reference date and extracted records are unchanged. Counting each digest as a
separate user-facing edition inflated the Prefecture history and made comparisons
for same-date series appear unavailable.

**The ledger remains append-preserving.** It retains edition identities, exact
document digests, all evidence references, checks and approved comparisons.
The public **Storico** view derives a separate, read-only grouping. Neither a
document capture nor a successful robot check automatically establishes that a
new source-data edition was published.

## User-facing edition identity

One distinct *data edition* is grouped by:

1. authority, register, population scope and exact source-series identity;
2. the original source-declared reference-date field, including its unknown state;
3. the whole-edition normalised data fingerprint, when available.

A new digest for an otherwise identical source/data edition adds a documented
file version, not an extra row of historical data. The counter of successful
checks is preserved separately and linked back to the ledger's original
edition IDs.

**Fail-safe fallback:** if a whole-edition data fingerprint is missing, the
document SHA-256 plus parser signature is used instead. Equal counts,
similar-looking dates or the same URL are never sufficient to deduplicate
content. In particular, differently fingerprinted datasets on the same
source-declared date remain separate, unordered variants. Their source
chronology is not inferred from content hashes or portal update times.

A later source-declared date stays a distinct dated edition even when the
underlying data are unchanged. Parser-only repetitions with equal
whole-edition fingerprints are not treated as new official editions.
Archive version identities remain retrievable for any detailed audit.

## Read-model fields

For each displayed edition the browser computes, without changing the
closed publication contract:

- **edizioni di dati distinte**: the number of user-facing groups;
- **versioni documentali**: the number of distinct original document digests
  across all underlying ledger snapshots;
- **controlli registrati**: the number of successful verification/capture
  records associated with those original IDs;
- **ultima verifica**: the latest corresponding UTC check timestamp, used to
  choose a deterministic representative official-source link.

A source URL is a pointer to the official service, not a guarantee that
its present bytes still match a previously captured digest. The immutable
SHA-256 evidence stays in the archived source layer.

## Delta and uncertainty

Comparisons remain restricted to the same compatible source series and
parser; no addition/removal is inferred from an aggregate delta alone.
Original approved comparisons may refer to any of the underlying capture
IDs, so the reader resolves those IDs through its grouping rather than
discarding the comparisons.

A source-declared date shared by **different** data fingerprints remains
ambiguous for chronological ordering. Unknown dates remain unknown.
A genuine publication of unchanged data on a later declared date is not
discarded. File version counts and check counts are not interchangeable
with the number of content editions.

## Regression coverage

- Node history tests anchor the 26 August 2026 Biella duplicate-content case,
  plus unequal-content, unknown-fingerprint and comparison-lineage cases.
- Browser tests confirm a repeated capture does not create a new visible
  edition or suppress an existing, approved observational delta.
- The append-preserving aggregate history ledger is neither rewritten nor compacted by this
  presentation correction.

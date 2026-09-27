# Potenza source reconciliation — 27 September 2026

Two independent reads of the configured official combined JSON endpoint produced
438,877 identical bytes, SHA-256
`69317d249f8968b5a4a39811a78bb47f53fae03b593c1fc1aea4e1c52ca4909b`.
The existing version-2 parser accepts the unchanged schema without relaxation:
1,036 observations, 218 listed, 378 pending and 440 renewal/update in progress.
The six additional listed observations relative to the approved 22 September
boundary are offset by six fewer renewal observations; identities/counts are stable.

The currently published derivative still refers to 21 September. Against that
separate baseline, source IDs 1112, 30, 535, 557, 574 and 925 move from renewal to
listed, with expiry values respectively 2027-07-15, 2027-07-11, 2027-06-21,
2027-09-19, 2027-03-26 and 2027-04-07. IDs 715 and 884 move from listed to renewal;
those two changes were already documented in the 22 September review. No source
IDs are added or removed. Other projected content remains unchanged, apart from
capture/reference/locator lineage. None of these comparisons infers legal effect.

The 27 September reference is an **observation boundary**, not an asserted source
publication timestamp. With this reference, the approved semantic SHA-256 is
`8a4191ef20a28b965311601655ae312b79b95deed4f0f3636f594c835b06c198`.
Changing the reference intentionally changes the semantic digest because reference
and locator fields belong to the current legacy comparison contract.

Production publication still requires matching selected input bytes/semantics and
the full public gates. The independent protected capture workflow preserves source
bytes/provenance before any later promotion; database and observation persistence
are reported separately. An updated configuration is not itself a deployed dataset.

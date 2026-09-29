# Public navigation and filter consistency — 29 September 2026

Baseline: `main@5a7e300b9e56e4d1cc53f8d666051f7c4391a21a` and the selected
public derivative release `public-data-36342687206-1`.

The published interface reproduced a misleading empty result: select
`Cancellazione / cessazione`, then Agrigento. The selected status disappeared
from the options because its count was zero. The browser displayed `Iscritte
(855)` while the actual filter still selected cancellations and returned no rows.
All status options now remain present with their current count, including zero.
Changing the authority or register never silently changes the selected status.

The filter controls group each label with its input at every viewport size.
`Azzera filtri` clears the query, authority, register and latest-edition filter,
restores the documented default `Iscritte`, returns to page one and focuses
search. The chosen number of rows per page is retained. Empty searches explain
their scope and do not imply absence from official lists. Download links explicitly
refer to the entire approved register, regardless of the current filters.

Registry and authority-directory pagination share one implementation. Controls
appear above and below results. After changing page, focus and scroll return to
the result heading below the sticky menu, including on narrow mobile screens.
Filter redraws preserve the active control. Result counts are announced through
the status region, without announcing the entire rebuilt company table.

Explicit section navigation adds browser-history entries; initial/invalid routes
are normalised without adding a duplicate entry. Back and Forward restore the
section and its in-memory filters. Escape only restores detail focus when a
detail dialog was actually open.

The existing browser gate exercises the real approved snapshot at 1440, 768,
390 and 320 pixels, including the zero-count status regression, reset, pagination,
empty authority search, Back/Forward and focus handling. It still verifies
independent loading, failed requests, source details and absence of outer
horizontal overflow. CI and deployed-browser evidence belong in the integration
checkpoint; this document alone does not establish successful deployment.

The five pinned public data files, source interpretations, default status semantics
and publication selector are unchanged. This is a presentation correction and
does not establish new acquisition, archive coverage or administrative facts.
The large registry payload remains a separate performance limitation; these
changes do not claim to reduce its transfer size.

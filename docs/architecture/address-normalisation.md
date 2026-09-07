# Source-address resolver research — superseded

This branch explored deterministic `municipality -> odonym -> civic` parsing before official ANNCSU linkage.

The approach is intentionally **not** part of `main` and should not be treated as the production path. The project has since adopted a simpler provider-agnostic address-normalisation design in which a geocoding provider (initially Nominatim-compatible) returns a structured address and coordinates, while ANNCSU/Istat remain optional validation/enrichment layers.

This branch is retained only as research history. No production pipeline should depend on it.
